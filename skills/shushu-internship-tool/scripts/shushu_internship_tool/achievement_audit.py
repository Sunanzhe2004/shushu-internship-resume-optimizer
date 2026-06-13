from __future__ import annotations

import argparse
import html
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .common import ensure_dir, load_json, markdown_table, normalize_list, write_json, write_text
from .doc_knowledge import build_knowledge_base, extract_terms, load_documents, query_knowledge
from .model_extract import load_structured_extract


EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    "dist",
    "build",
}

LANGUAGE_SUFFIXES = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".go": "Go",
    ".sql": "SQL",
    ".md": "Markdown",
    ".yml": "YAML",
    ".yaml": "YAML",
}

ALLOWED_SOURCE_TYPES = {"code_repo", "project_summary", "business_docs"}
SECTION_ITEM_RE = re.compile(r"^\s*(\d+)[\.\u3001]\s*(.+)$")
HEADING_RE = re.compile(r"^\s*#{2,4}\s*(.+?)\s*$")
PROJECT_HEADING_RE = re.compile(r"^(?:项目|专题|方向)\s*[一二三四五六七八九十0-9]+[\s:：]*(.+)$")
METRIC_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("F1", re.compile(r"\bF1\s*[:：]?\s*(\d+(?:\.\d+)?%)", re.IGNORECASE)),
    ("Recall", re.compile(r"\bRecall\s*[:：]?\s*(\d+(?:\.\d+)?%)", re.IGNORECASE)),
    ("Precision", re.compile(r"\bPrecision\s*[:：]?\s*(\d+(?:\.\d+)?%)", re.IGNORECASE)),
    ("减少", re.compile(r"(减少(?:约)?\s*\d+(?:\.\d+)?%\s*[^，。；;\n]*)")),
    ("时长", re.compile(r"(\d+(?:\.\d+)?\s*(?:ms|s|分钟|小时|天))", re.IGNORECASE)),
]
GENERIC_METRIC_RE = re.compile(r"\d+(?:\.\d+)?%\b|\d+(?:\.\d+)?\s*(?:ms|s|分钟|小时|天)", re.IGNORECASE)
LOW_VALUE_WORKLOAD_RE = re.compile(
    r"(?i)(?:read|scan|process|review|读取|扫描|处理|梳理).{0,12}\d+\s*(?:个|份|条|files?|repos?|文件|仓库)",
    re.IGNORECASE,
)
VALUE_SIGNAL_RE = re.compile(
    r"(?i)(?:减少|降低|提升|优化|节省|支持|避免|拦截|过滤|定位|归因|恢复|稳定|吞吐|准确率|召回率|一致率|F1|Recall|Precision|成本|效率|误判|耗时|延迟|成功率)",
    re.IGNORECASE,
)

AI_SUMMARY_MARKERS = {
    "一句话定位",
    "核心问题",
    "项目描述",
    "核心职责",
    "STAR 法则",
    "技术栈",
    "数据闭环",
}
OVERCLAIM_MARKERS = {
    "独立设计并实现",
    "完全替代",
    "全流程",
    "全链路",
    "闭环",
    "显著提升",
    "大幅提升",
}
SUMMARY_NOISE_PREFIXES = (
    "核心职责",
    "技术栈",
    "项目描述",
    "一句话定位",
    "业务背景",
    "实习背景",
    "核心问题",
    "项目目标",
    "当前工作主要聚焦",
    "我的工作定位",
    "关键迭代过程",
    "当前阶段结果",
)
NON_ACHIEVEMENT_SECTIONS = {
    "一句话定位",
    "业务背景",
    "我的工作定位",
    "这个项目要解决的核心问题",
    "项目目标",
    "关键迭代过程",
    "当前阶段结果",
    "我在项目中的角色",
    "技术栈",
    "适合后续继续补充的数据",
}
LEGACY_TITLE_ALIASES: dict[str, str] = {}
GENERIC_HEADING_LABELS = {
    "核心工作",
    "主要工作",
    "关键工作",
    "核心方案",
    "工作内容",
    "项目内容",
    "项目经历",
    "项目经验",
}
TITLE_INTENT_RULES: list[tuple[str, tuple[str, ...]]] = []
TITLE_VERB_PREFIX_RE = re.compile(r"^(?:负责|设计|搭建|构建|实现|优化|推进|完善|补充|建立|沉淀|基于|通过|围绕|针对|将|把)")
TITLE_SPLIT_RE = re.compile(r"[，。；;：:\n]")


def collect_repo_files(repo: Path, max_files: int = 2000) -> list[Path]:
    files: list[Path] = []
    for root, dirs, filenames in os.walk(repo):
        dirs[:] = [name for name in dirs if name.lower() not in EXCLUDED_DIRS]
        for filename in sorted(filenames):
            rel = (Path(root) / filename).relative_to(repo)
            if any(part.lower() in EXCLUDED_DIRS for part in rel.parts):
                continue
            files.append(rel)
            if len(files) >= max_files:
                return files
    return files


def parse_sources(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [dict(item) for item in payload]
    if isinstance(payload, dict) and isinstance(payload.get("sources"), list):
        return [dict(item) for item in payload["sources"]]
    raise ValueError("source JSON must be a list or an object with a 'sources' list")


def validate_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(sources, start=1):
        source_type = str(raw.get("source_type", "")).strip()
        if source_type not in ALLOWED_SOURCE_TYPES:
            raise ValueError(f"source #{index} has invalid source_type: {source_type}")
        path_or_text = str(raw.get("path_or_text", "")).strip()
        if not path_or_text:
            raise ValueError(f"source #{index} is missing path_or_text")
        normalized.append(
            {
                "source_type": source_type,
                "path_or_text": path_or_text,
                "title": str(raw.get("title") or Path(path_or_text).name or source_type).strip(),
                "knowledge_mode": raw.get("knowledge_mode"),
                "structured_extract_path": str(raw.get("structured_extract_path") or "").strip() or None,
                "structured_extract": raw.get("structured_extract"),
            }
        )
    return normalized


def build_source_bundle(path_or_text: str, source_type: str, title: str | None = None) -> dict[str, Any]:
    path = Path(path_or_text)
    return {"source_type": source_type, "path_or_text": path_or_text, "title": title or path.name or source_type}


def sentence_candidates(text: str) -> list[str]:
    return [item.strip(" -\t") for item in re.split(r"[。！？；;\n]", text) if len(item.strip(" -\t")) >= 8]


def clean_summary_line(text: str, title: str = "") -> str:
    value = " ".join(str(text).replace("\n", " ").split()).strip(" -:：")
    value = re.sub(r"^#+\s*", "", value)
    value = re.sub(r"^\d+[.)、]\s*", "", value)
    value = value.strip(" -:：")
    if not value:
        return ""
    if any(value.startswith(prefix) for prefix in SUMMARY_NOISE_PREFIXES):
        return ""
    if title and value == title:
        return ""
    if title and value.startswith(f"{title}："):
        value = value[len(title) + 1 :].strip()
    if title and value.startswith(f"{title}:"):
        value = value[len(title) + 1 :].strip()
    if value in {"错误标签自动化归因", "无效数据检测体系设计（P-E-R 流水线）", "LLM-as-Judge 评估 Prompt 工程"}:
        return ""
    return value


def split_summary_block(text: str, title: str = "") -> list[str]:
    lines: list[str] = []
    for raw_line in text.splitlines():
        cleaned = clean_summary_line(raw_line, title=title)
        if not cleaned:
            continue
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9\s/().+-]{2,}", cleaned):
            continue
        if cleaned not in lines:
            lines.append(cleaned)
    return lines


def is_metric_heavy_line(text: str) -> bool:
    metrics = extract_metrics(text)
    if metrics:
        return True
    lowered = text.lower()
    return any(keyword in lowered for keyword in ("f1", "recall", "precision", "一致率", "召回率", "准确率", "%", "30s"))


def choose_scope_line(title: str, lines: list[str]) -> str:
    preferred = ("设计", "搭建", "构建", "实现", "优化", "迭代", "负责", "推进", "支持", "接入", "过滤", "识别", "归因")
    for keyword in preferred:
        for line in lines:
            if keyword in line and not is_metric_heavy_line(line):
                return line
    for line in lines:
        if not is_metric_heavy_line(line):
            return line
    return title or "待补任务描述"


def choose_action_lines(lines: list[str], task: str, metrics: list[str], limit: int = 3) -> list[str]:
    actions: list[str] = []
    for line in lines:
        if line == task:
            continue
        if any(metric in line for metric in metrics):
            continue
        if is_low_value_workload_text(line):
            continue
        if line not in actions:
            actions.append(line)
        if len(actions) >= limit:
            break
    return actions


def choose_interview_explain(title: str, business_context: str, task: str, actions: list[str], outcome: str) -> str:
    scope = task or title
    if outcome and outcome != scope:
        return f"{scope}，核心结果是{outcome}"
    if actions:
        return f"{scope}，具体包括{actions[0]}"
    if business_context:
        return f"{scope}，这块工作服务于{business_context}"
    return scope


def build_resume_seed(title: str, task: str, actions: list[str], outcome: str) -> str:
    scope = task or title
    if outcome and outcome != scope:
        return f"{title}：{scope}，结果达到{outcome}"
    if actions:
        return f"{title}：{scope}"
    return title


def best_metric_from_texts(metrics: list[str], texts: list[str]) -> str:
    if metrics:
        priority = ("F1", "Recall", "Precision", "一致率", "准确率", "召回率", "误判率", "减少", "降低", "提升")
        for keyword in priority:
            for metric in metrics:
                if keyword.lower() in metric.lower():
                    return metric
        return metrics[0]
    merged = " ".join(texts)
    extracted = extract_metrics(merged)
    return extracted[0] if extracted else ""


def choose_business_value(title: str, actions: list[str], business_context: str) -> str:
    if "异步评估服务" in title:
        return "支撑采集端与评估端解耦，并让评估流程可以服务化运行"
    if "自动评估" in title or "判定优化" in title:
        return "减少无效数据对评估结果的干扰，并提升任务完成判断稳定性"
    if "错误标签" in title or "归因" in title:
        return "支撑失败 case 归因和高频问题定位，方便后续策略迭代"
    preferred = ("降低", "减少", "提升", "支持", "区分", "过滤", "定位", "解释", "自动化")
    for keyword in preferred:
        for action in actions:
            if keyword in action:
                return action
    if business_context:
        snippets = sentence_candidates(business_context)
        if snippets:
            return snippets[0]
    return title


def build_interview_safe_explain(title: str, task: str, actions: list[str], best_metric: str, business_value: str) -> str:
    scope = task or title
    if best_metric:
        return f"我主要负责{scope}，这项工作的直接价值是{business_value}，目前能确认的结果是{best_metric}。"
    if actions:
        return f"我主要负责{scope}，具体包括{actions[0]}，这项工作的价值主要在于{business_value}。"
    return f"我主要负责{scope}，这项工作的价值主要在于{business_value}。"


def build_task_and_actions(title: str, excerpts: list[str], metrics: list[str]) -> tuple[str, list[str], str]:
    lines: list[str] = []
    for excerpt in excerpts:
        for line in split_summary_block(excerpt, title=title):
            if line not in lines:
                lines.append(line)

    if not lines:
        fallback = title or "待补任务描述"
        return fallback, [fallback], metrics[0] if metrics else fallback

    task = choose_scope_line(title, lines)
    actions = choose_action_lines(lines, task, metrics, limit=3)
    if not actions:
        actions = [task]
    outcome = metrics[0] if metrics else (actions[-1] if actions else task)
    return task, actions[:4], outcome


def choose_cluster_key(tags: list[str], fallback: str) -> str:
    for tag in tags:
        lowered = tag.lower()
        if 2 <= len(lowered) <= 18 and lowered not in {"project", "summary", "business", "docs", "repo", "code", "intern", "internship"}:
            return lowered
    cleaned = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", fallback.lower()).strip("-")
    return cleaned or "general"


def suspicious_sentences(text: str, markers: set[str], limit: int = 4) -> list[str]:
    hits: list[str] = []
    for sentence in sentence_candidates(text):
        if any(marker in sentence for marker in markers):
            hits.append(sentence[:180])
    return hits[:limit]


def detect_ai_style_flags(text: str) -> tuple[list[str], list[str]]:
    flags: list[str] = []
    evidence: list[str] = []
    heading_hits = [marker for marker in AI_SUMMARY_MARKERS if marker in text]
    sentence_hits = suspicious_sentences(text, AI_SUMMARY_MARKERS)
    if len(heading_hits) >= 3 or len(sentence_hits) >= 2:
        flags.append("AI总结味较重，需人工核对")
        evidence.extend(sentence_hits[:3] or heading_hits[:3])
    return flags, evidence


def detect_overclaim_flags(text: str) -> tuple[list[str], list[str]]:
    evidence = suspicious_sentences(text, OVERCLAIM_MARKERS)
    return (["存在可能夸大表述，需确认边界"], evidence[:3]) if evidence else ([], [])


def is_low_value_workload_text(text: str) -> bool:
    clean = " ".join(str(text).split())
    generic_workload_re = re.compile(
        r"(?i)(?:\bread\b|\bscan\b|\bprocess\b|\breview\b|[\u8bfb\u626b\u63cf\u5904\u7406\u68b3\u7406]{1,3}).{0,12}\d+\s*(?:[\u4e2a\u4efd\u6761]|\bfiles?\b|\brepos?\b|\u6587\u4ef6|\u4ed3\u5e93)"
    )
    value_signal_re = re.compile(
        r"(?i)(?:\u51cf\u5c11|\u964d\u4f4e|\u63d0\u5347|\u4f18\u5316|\u8282\u7701|\u907f\u514d|f1|recall|precision|accuracy|latency|throughput|\d+(?:\.\d+)?%)"
    )
    return bool(generic_workload_re.search(clean)) and not bool(value_signal_re.search(clean))


def filter_meaningful_metrics(metrics: list[str]) -> list[str]:
    kept: list[str] = []
    for metric in metrics:
        clean = metric.strip()
        if not clean:
            continue
        if is_low_value_workload_text(clean):
            continue
        if clean not in kept:
            kept.append(clean)
    return kept[:6]


def extract_metrics(text: str) -> list[str]:
    metrics: list[str] = []
    for label, pattern in METRIC_PATTERNS:
        for match in pattern.finditer(text):
            value = match.group(1).strip()
            if label in {"F1", "Recall", "Precision"} and not value.lower().startswith(label.lower()):
                value = f"{label} {value}"
            metrics.append(value)
    if not metrics:
        metrics.extend(match.group(0).strip() for match in GENERIC_METRIC_RE.finditer(text))
    return filter_meaningful_metrics(list(dict.fromkeys(metrics)))


def detect_business_context(text: str) -> str:
    primary = []
    secondary = []
    for sentence in sentence_candidates(text):
        if any(keyword in sentence for keyword in ("业务背景", "项目背景", "应用场景", "项目场景")):
            primary.append(sentence)
        elif any(keyword in sentence for keyword in ("人工标注", "成本", "自动化", "流程", "数据", "任务")):
            secondary.append(sentence)
    hits = primary[:1] + secondary[:1]
    joined = "；".join(hits)
    return joined[:120].rstrip("；，。")




def is_generic_work_heading(text: str) -> bool:
    normalized = normalize_title(text)
    if not normalized:
        return False
    work_headings = (
        "\u6838\u5fc3\u804c\u8d23",
        "\u6838\u5fc3\u65b9\u6848",
        "\u4e3b\u8981\u5de5\u4f5c",
        "\u5173\u952e\u5de5\u4f5c",
        "\u6838\u5fc3\u5de5\u4f5c",
        "\u5de5\u4f5c\u5185\u5bb9",
        "\u9879\u76ee\u5185\u5bb9",
        "\u9879\u76ee\u7ecf\u5386",
        "\u9879\u76ee\u7ecf\u9a8c",
    )
    return any(normalized == heading or normalized.startswith(heading) for heading in work_headings)


def is_business_context_heading(text: str) -> bool:
    normalized = normalize_title(text)
    if not normalized:
        return False
    business_headings = (
        "\u4e00\u53e5\u8bdd\u5b9a\u4f4d",
        "\u4e1a\u52a1\u80cc\u666f",
        "\u5b9e\u4e60\u80cc\u666f",
        "\u6838\u5fc3\u95ee\u9898",
        "\u9879\u76ee\u80cc\u666f",
        "\u9879\u76ee\u76ee\u6807",
    )
    return any(normalized == heading or normalized.startswith(heading) for heading in business_headings)


def split_project_summary(text: str, title: str) -> list[dict[str, Any]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    project_heading_re = re.compile(r"^(?:\u9879\u76ee|\u4e13\u9898|\u65b9\u5411)\s*[\u4e00-\u9fa5\d]+\s*[:：]?\s*(.+)$")
    business_context_lines: list[str] = []

    project_blocks: list[dict[str, Any]] = []
    current_project_title = ""
    current_project_lines: list[str] = []
    for stripped in lines:
        heading_match = HEADING_RE.match(stripped)
        heading_text = heading_match.group(1).strip() if heading_match else stripped
        project_match = project_heading_re.match(heading_text)
        if project_match:
            if current_project_title and current_project_lines:
                project_blocks.append({"heading": current_project_title, "text": "\n".join(current_project_lines)})
            current_project_title = project_match.group(1).strip() or heading_text
            current_project_lines = []
            continue
        if current_project_title:
            current_project_lines.append(stripped)
        else:
            business_context_lines.append(stripped)
    if current_project_title and current_project_lines:
        project_blocks.append({"heading": current_project_title, "text": "\n".join(current_project_lines)})
    if project_blocks:
        business_context = "\n".join(line for line in business_context_lines if clean_summary_line(line, title=title))
        return [
            {
                "title": infer_title_from_block(block["text"], block["heading"]),
                "text": block["text"],
                "business_context": business_context,
            }
            for block in project_blocks
        ]

    sections: list[dict[str, Any]] = []
    current_section_title = ""
    current_section_lines: list[str] = []
    mode = "context"

    def flush_section() -> None:
        nonlocal current_section_title, current_section_lines
        if not current_section_lines:
            current_section_title = ""
            return
        block_text = "\n".join(current_section_lines).strip()
        section_title = infer_title_from_block(block_text, current_section_title or title) or normalize_title(title) or "section"
        sections.append(
            {
                "title": section_title,
                "text": block_text,
                "business_context": "\n".join(business_context_lines),
            }
        )
        current_section_title = ""
        current_section_lines = []

    for stripped in lines:
        heading_match = HEADING_RE.match(stripped)
        heading_text = heading_match.group(1).strip() if heading_match else stripped
        normalized_heading = normalize_title(heading_text)

        if is_business_context_heading(normalized_heading):
            if current_section_lines:
                flush_section()
            mode = "context"
            continue
        if is_generic_work_heading(normalized_heading):
            if current_section_lines:
                flush_section()
            mode = "work"
            current_section_title = ""
            continue

        numbered_match = SECTION_ITEM_RE.match(stripped)
        if numbered_match:
            if current_section_lines:
                flush_section()
            mode = "work"
            current_section_title = normalize_title(numbered_match.group(2).strip())
            current_section_lines = []
            continue

        if mode == "context":
            business_context_lines.append(stripped)
            continue

        if mode == "work":
            if not current_section_title:
                current_section_title = normalize_title(title)
            current_section_lines.append(stripped)

    if current_section_lines:
        flush_section()

    if sections:
        return sections

    fallback_lines = [line for line in lines if clean_summary_line(line, title=title)]
    business_context = "\n".join(business_context_lines)
    return [
        {
            "title": infer_title_from_block(line, title) or (title or f"section-{index}"),
            "text": line,
            "business_context": business_context,
        }
        for index, line in enumerate(fallback_lines, start=1)
    ]


def normalize_title(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    raw = re.sub(r"^#+\s*", "", raw)
    raw = re.sub(r"^(?:\u9879\u76ee|\u4e13\u9898|\u65b9\u5411)\s*[\u4e00-\u9fa5\d]+\s*[:：]?\s*", "", raw)
    raw = re.sub(r"^\d+[\.\u3001]\s*", "", raw)
    raw = re.sub(r"[（(][^）)]*[）)]", "", raw)
    raw = " ".join(raw.replace("\n", " ").split()).strip(" -:：")
    raw = TITLE_VERB_PREFIX_RE.sub("", raw).strip(" -:：")
    return raw[:24] or "\u6838\u5fc3\u6210\u679c"


def compress_title_candidate(text: str) -> str:
    raw = normalize_title(text)
    if not raw:
        return ""
    clause = next((part.strip() for part in TITLE_SPLIT_RE.split(raw) if part.strip()), raw)
    clause = TITLE_VERB_PREFIX_RE.sub("", clause).strip(" -:：")
    clause = re.sub(r"^(?:用于|面向|针对)", "", clause).strip(" -:：")
    if len(clause) > 24:
        clause = clause[:24].rstrip(" -:：")
    if len(clause) < 4:
        return ""
    return clause


def title_from_text_intent(text: str) -> tuple[str, int]:
    text = str(text or "")
    candidates = [compress_title_candidate(line) for line in split_summary_block(text)]
    candidates.extend(compress_title_candidate(sentence) for sentence in sentence_candidates(text))
    candidates = [candidate for candidate in candidates if candidate]
    for candidate in candidates:
        if is_generic_work_heading(candidate) or is_business_context_heading(candidate):
            continue
        score = 1
        if re.search(r"[A-Za-z]{2,}|[\u4e00-\u9fff]{4,}", candidate):
            score += 1
        if any(token in text for token in ("设计", "搭建", "构建", "实现", "优化", "归因", "过滤", "评估", "服务", "Prompt")):
            score += 1
        if extract_metrics(text) or VALUE_SIGNAL_RE.search(text):
            score += 1
        return candidate, score
    return "", 0


def is_informative_heading(text: str) -> bool:
    clean = normalize_title(text)
    if not clean:
        return False
    if is_generic_work_heading(clean) or is_business_context_heading(clean):
        return False
    return len(clean) >= 4


def infer_title_from_block(block: str, fallback: str) -> str:
    normalized_fallback = normalize_title(fallback)
    fallback_lower = normalized_fallback.lower()
    looks_like_source_label = any(token in fallback_lower for token in ("summary", "overview", "weekly", "business", "notes"))
    if is_informative_heading(fallback) and not looks_like_source_label:
        return normalized_fallback
    first_line = next((clean_summary_line(line, title=normalized_fallback) for line in block.splitlines() if clean_summary_line(line, title=normalized_fallback)), "")
    if first_line:
        compressed = compress_title_candidate(first_line)
        if compressed and not is_generic_work_heading(compressed) and not is_business_context_heading(compressed):
            return compressed
    inferred_title, score = title_from_text_intent(f"{fallback}\n{block}")
    if score >= 2:
        return inferred_title
    return normalized_fallback






def derive_gaps(metrics: list[str], business_context: str, source_types: list[str], evidence_count: int) -> list[str]:
    gaps = []
    if not metrics:
        gaps.append("缺少量化指标")
    if not business_context:
        gaps.append("缺少业务背景说明")
    if "code_repo" not in source_types:
        gaps.append("缺少代码侧证据")
    if evidence_count < 2:
        gaps.append("证据数量偏少")
    return gaps


def derive_risk_flags(item: dict[str, Any]) -> list[str]:
    risk_flags = []
    if not item.get("metrics"):
        risk_flags.append("待补量化")
    if "code_repo" not in item.get("source_types", []):
        risk_flags.append("缺少代码证据")
    if item.get("source_types") == ["project_summary"]:
        risk_flags.append("仅基于自述材料")
    if not item.get("business_context"):
        risk_flags.append("业务背景待补")
    return list(dict.fromkeys(risk_flags))


def derive_user_check_fields(item: dict[str, Any]) -> tuple[list[str], list[str]]:
    flags = list(dict.fromkeys(item.get("user_check_flags", [])))
    evidence = list(dict.fromkeys(item.get("user_check_evidence", [])))
    candidate_texts = [
        item.get("task", ""),
        item.get("outcome", ""),
        *item.get("actions", []),
        *item.get("metrics", []),
        *[str(entry.get("excerpt_summary") or "") for entry in item.get("evidence", [])],
    ]
    weak_claims: list[str] = []
    for text in candidate_texts:
        if not text:
            continue
        for sentence in sentence_candidates(str(text)) or [str(text)]:
            if is_low_value_workload_text(sentence):
                weak_claims.append(sentence)
    if weak_claims:
        flags.append("文件处理量不等于成果价值，需补充业务结果或工程收益")
        evidence.extend(weak_claims[:2])
    return (list(dict.fromkeys(flags))[:6], list(dict.fromkeys(evidence))[:6])


def derive_readiness_reason(metrics: list[str], source_types: list[str], business_context: str) -> str:
    reasons = []
    if metrics:
        reasons.append("有量化结果")
    if len(source_types) >= 2:
        reasons.append("多源证据已汇合")
    if business_context:
        reasons.append("可以解释业务价值")
    return "；".join(reasons) or "当前更适合先补信息再写简历"


def achievement_tokens(item: dict[str, Any]) -> set[str]:
    text = " ".join(
        [
            item.get("title", ""),
            item.get("background", ""),
            item.get("task", ""),
            item.get("outcome", ""),
            " ".join(item.get("actions", [])),
        ]
    )
    return set(extract_terms(text, top_k=40))


def merge_two_achievements(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    source_types = sorted(set(left["source_types"]) | set(right["source_types"]))
    metrics = list(dict.fromkeys([*left.get("metrics", []), *right.get("metrics", [])]))[:6]
    evidence = [*left.get("evidence", []), *right.get("evidence", [])]
    actions = list(dict.fromkeys([*left.get("actions", []), *right.get("actions", [])]))[:6]
    business_context = left.get("business_context") or right.get("business_context", "")
    merged = {
        **left,
        "title": left.get("title"),
        "background": business_context or left.get("background") or right.get("background"),
        "task": left.get("task") or right.get("task"),
        "actions": actions,
        "tech_stack": list(dict.fromkeys([*left.get("tech_stack", []), *right.get("tech_stack", [])]))[:6],
        "business_context": business_context,
        "collaboration": list(dict.fromkeys([*left.get("collaboration", []), *right.get("collaboration", [])]))[:6],
        "outcome": left.get("outcome") if left.get("metrics") else right.get("outcome", left.get("outcome")),
        "metrics": metrics,
        "evidence": evidence[:8],
        "confidence": round((float(left.get("confidence", 0.0)) + float(right.get("confidence", 0.0))) / 2.0, 3),
        "resume_ready": bool(metrics),
        "source_types": source_types,
        "matched_keywords": list(dict.fromkeys([*left.get("matched_keywords", []), *right.get("matched_keywords", [])]))[:8],
        "user_check_flags": [*left.get("user_check_flags", []), *right.get("user_check_flags", [])],
        "user_check_evidence": [*left.get("user_check_evidence", []), *right.get("user_check_evidence", [])],
    }
    merged["gaps"] = derive_gaps(metrics, business_context, source_types, len(evidence))
    merged["risk_flags"] = derive_risk_flags(merged)
    merged["user_check_flags"], merged["user_check_evidence"] = derive_user_check_fields(merged)
    merged["readiness_reason"] = derive_readiness_reason(metrics, source_types, business_context)
    return merged


def should_merge_titles(left: str, right: str) -> bool:
    if left == right:
        return True
    return False


def merge_similar_achievements(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    used: set[int] = set()
    for index, item in enumerate(items):
        if index in used:
            continue
        current = item
        current_tokens = achievement_tokens(current)
        for other_index in range(index + 1, len(items)):
            if other_index in used:
                continue
            other = items[other_index]
            overlap = current_tokens & achievement_tokens(other)
            should_merge_cross_source = len(overlap) >= 2 and (
                ("business_docs" in current["source_types"] and "project_summary" in other["source_types"])
                or ("project_summary" in current["source_types"] and "business_docs" in other["source_types"])
            )
            if should_merge_titles(current["title"], other["title"]) or should_merge_cross_source:
                current = merge_two_achievements(current, other)
                current_tokens = achievement_tokens(current)
                used.add(other_index)
        merged.append(current)
    return merged


def analyze_code_repo(bundle: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    repo = Path(bundle["path_or_text"]).resolve()
    if not repo.exists() or not repo.is_dir():
        raise FileNotFoundError(f"code_repo path does not exist or is not a directory: {repo}")
    files = collect_repo_files(repo)
    language_counts = Counter(LANGUAGE_SUFFIXES.get(path.suffix.lower(), "Other") for path in files)
    dependency_files = [
        path.as_posix()
        for path in files
        if path.name.lower() in {"requirements.txt", "pyproject.toml", "package.json", "docker-compose.yml"}
    ]
    tags = extract_terms(" ".join(path.as_posix() for path in files), top_k=20)
    evidence: list[dict[str, Any]] = []
    for rel in files[:120]:
        evidence.append(
            {
                "source_type": "code_repo",
                "source_ref": rel.as_posix(),
                "excerpt_summary": f"浠ｇ爜璺緞绾跨储: {rel.as_posix()}",
                "tags": extract_terms(rel.as_posix(), top_k=6),
                "confidence": 0.65,
                "cluster_key": bundle["title"],
                "metrics": [],
            }
        )
    summary = {
        "type": "code_repo",
        "title": bundle["title"],
        "path": str(repo),
        "language_counts": language_counts.most_common(),
        "dependency_files": dependency_files,
        "top_tags": tags,
    }
    return summary, evidence


def structured_extract_to_evidence(
    extracted_items: list[dict[str, Any]],
    bundle: dict[str, Any],
    source_ref: str,
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for item in extracted_items:
        title = normalize_title(str(item.get("title") or bundle["title"]))
        actions = normalize_list(item.get("actions"))
        task = str(item.get("task") or title).strip()
        outcome = str(item.get("outcome") or "").strip()
        metrics = normalize_list(item.get("metrics"))
        excerpt_parts = [task, *actions[:3], outcome]
        excerpt = " ".join(part for part in excerpt_parts if part).strip()
        if not excerpt:
            excerpt = title
        item_metrics = metrics or extract_metrics(excerpt)
        evidence.append(
            {
                "source_type": bundle["source_type"],
                "source_ref": source_ref,
                "excerpt_summary": excerpt[:260],
                "tags": extract_terms(" ".join([title, task, outcome, *actions]), top_k=12),
                "confidence": float(item.get("confidence") or 0.92),
                "cluster_key": title,
                "metrics": item_metrics,
                "seed_title": title,
                "business_context": str(item.get("business_context") or "").strip(),
                "user_check_flags": normalize_list(item.get("user_check_flags")),
                "user_check_evidence": normalize_list(item.get("evidence")),
                "task_hint": task,
                "actions_hint": actions,
                "outcome_hint": outcome,
                "business_value_hint": str(item.get("business_value") or "").strip(),
                "resume_ready_hint": bool(item.get("keep_for_resume", True)),
                "project_title": str(item.get("project_title") or "").strip(),
                "extraction_backend": "structured_model",
            }
        )
    return evidence


def analyze_textual_bundle(
    bundle: dict[str, Any],
    prefer_context_only_business_docs: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any] | None]:
    raw = bundle["path_or_text"]
    path = Path(raw)
    documents = load_documents([raw]) if path.exists() else [{"path": raw, "title": bundle["title"], "text": raw}]
    joined = "\n".join(doc["text"] for doc in documents)
    global_anchor = choose_cluster_key(extract_terms(joined, top_k=20), bundle["title"])
    knowledge = None
    if bundle["source_type"] == "business_docs":
        knowledge = build_knowledge_base(documents, mode=bundle.get("knowledge_mode"))
    structured_items = load_structured_extract(bundle)
    if structured_items:
        evidence: list[dict[str, Any]] = []
        for doc in documents:
            evidence.extend(structured_extract_to_evidence(structured_items, bundle, doc["title"]))
        summary = {
            "type": bundle["source_type"],
            "title": bundle["title"],
            "documents": [doc["title"] for doc in documents],
            "top_terms": extract_terms(joined, top_k=14),
            "metric_hits": extract_metrics(joined),
            "extraction_backend": "structured_model",
        }
        return summary, evidence, knowledge

    if prefer_context_only_business_docs and bundle["source_type"] == "business_docs":
        summary = {
            "type": bundle["source_type"],
            "title": bundle["title"],
            "documents": [doc["title"] for doc in documents],
            "top_terms": extract_terms(joined, top_k=14),
            "metric_hits": extract_metrics(joined),
            "extraction_backend": "knowledge_only",
        }
        return summary, [], knowledge

    evidence: list[dict[str, Any]] = []
    for doc in documents:
        text = doc["text"]
        if bundle["source_type"] == "project_summary":
            business_context = detect_business_context(text)
            ai_flags, ai_evidence = detect_ai_style_flags(text)
            overclaim_flags, overclaim_evidence = detect_overclaim_flags(text)
            user_check_flags = [*ai_flags, *overclaim_flags]
            user_check_evidence = [*ai_evidence, *overclaim_evidence]
            sections = split_project_summary(text, bundle["title"])
            for section in sections:
                section_check_flags = list(user_check_flags)
                section_check_evidence = list(user_check_evidence)
                weak_sentences = [sentence for sentence in sentence_candidates(section["text"]) if is_low_value_workload_text(sentence)]
                if weak_sentences:
                    section_check_flags.append("文件处理量不等于成果价值，需补充业务结果或工程收益")
                    section_check_evidence.extend(weak_sentences[:2])
                evidence.append(
                    {
                        "source_type": bundle["source_type"],
                        "source_ref": doc["title"],
                        "excerpt_summary": section["text"][:260],
                        "tags": extract_terms(section["text"], top_k=12),
                        "confidence": 0.82,
                        "cluster_key": section["title"],
                        "metrics": extract_metrics(section["text"]),
                        "seed_title": section["title"],
                        "business_context": detect_business_context(section.get("business_context", "") or business_context),
                        "user_check_flags": section_check_flags,
                        "user_check_evidence": section_check_evidence,
                    }
                )
            if not sections:
                for sentence in sentence_candidates(text)[:20]:
                    evidence.append(
                        {
                            "source_type": bundle["source_type"],
                            "source_ref": doc["title"],
                            "excerpt_summary": sentence[:180],
                            "tags": extract_terms(sentence, top_k=8),
                            "confidence": 0.8,
                            "cluster_key": global_anchor,
                            "metrics": extract_metrics(sentence),
                            "seed_title": normalize_title(bundle["title"]),
                            "business_context": business_context,
                            "user_check_flags": user_check_flags,
                            "user_check_evidence": user_check_evidence,
                        }
                    )
        else:
            for sentence in sentence_candidates(text)[:20]:
                inferred_title = infer_title_from_block(sentence, bundle["title"])
                _, score = title_from_text_intent(sentence)
                if inferred_title == normalize_title(bundle["title"]) and score == 0:
                    inferred_title = choose_cluster_key(extract_terms(sentence, top_k=8), bundle["title"])
                if inferred_title == normalize_title(bundle["title"]) and score == 0:
                    continue
                evidence.append(
                    {
                        "source_type": bundle["source_type"],
                        "source_ref": doc["title"],
                        "excerpt_summary": sentence[:180],
                        "tags": extract_terms(sentence, top_k=8),
                        "confidence": 0.75 if bundle["source_type"] == "business_docs" else 0.8,
                        "cluster_key": inferred_title,
                        "metrics": extract_metrics(sentence),
                        "seed_title": inferred_title,
                    }
                )

    summary = {
        "type": bundle["source_type"],
        "title": bundle["title"],
        "documents": [doc["title"] for doc in documents],
        "top_terms": extract_terms(joined, top_k=14),
        "metric_hits": extract_metrics(joined),
        "extraction_backend": "rules",
    }
    return summary, evidence, knowledge


def merge_achievements(evidence_items: list[dict[str, Any]], knowledge_entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in evidence_items:
        grouped[item["cluster_key"]].append(item)

    achievements: list[dict[str, Any]] = []
    for cluster_key, items in grouped.items():
        source_types = sorted({item["source_type"] for item in items})
        tag_counts = Counter(tag for item in items for tag in item["tags"])
        top_tags = [tag for tag, _ in tag_counts.most_common(8)]
        excerpts = [item["excerpt_summary"] for item in items[:6]]
        metrics = list(dict.fromkeys(metric for item in items for metric in item.get("metrics", [])))[:6]
        knowledge_hits = []
        for entry in knowledge_entries:
            knowledge_hits.extend(query_knowledge(entry, " ".join(top_tags[:4]) or cluster_key, top_k=1))
        textual_business_context = next((item.get("business_context", "") for item in items if item.get("business_context")), "")
        knowledge_context = knowledge_hits[0]["text"][:200] if knowledge_hits else ""
        extraction_backends = sorted({str(item.get("extraction_backend") or "rules") for item in items})
        if "structured_model" in extraction_backends and textual_business_context:
            business_context = textual_business_context
        else:
            business_context = knowledge_context or textual_business_context
        background = business_context or (excerpts[0] if excerpts else "")
        hinted_task = next((str(item.get("task_hint") or "").strip() for item in items if str(item.get("task_hint") or "").strip()), "")
        hinted_actions = list(
            dict.fromkeys(
                action.strip()
                for item in items
                for action in normalize_list(item.get("actions_hint"))
                if action.strip()
            )
        )[:4]
        hinted_outcome = next((str(item.get("outcome_hint") or "").strip() for item in items if str(item.get("outcome_hint") or "").strip()), "")
        task, actions, outcome = build_task_and_actions(normalize_title(str(items[0].get("seed_title") or cluster_key)), excerpts, metrics)
        if hinted_task:
            task = hinted_task
        if hinted_actions:
            actions = hinted_actions
        if hinted_outcome:
            outcome = hinted_outcome
        normalized_title = normalize_title(str(items[0].get("seed_title") or cluster_key))
        best_metric = best_metric_from_texts(metrics, excerpts)
        business_value_hint = next(
            (str(item.get("business_value_hint") or "").strip() for item in items if str(item.get("business_value_hint") or "").strip()),
            "",
        )
        business_value = business_value_hint or choose_business_value(normalized_title, actions, business_context)
        achievement = {
            "title": normalized_title,
            "background": background,
            "task": task,
            "actions": actions,
            "tech_stack": [tag for tag in top_tags if re.search(r"[a-zA-Z]", tag)][:6],
            "business_context": business_context,
            "collaboration": [item["source_ref"] for item in items[:4]],
            "outcome": outcome or next((excerpt for excerpt in excerpts if extract_metrics(excerpt)), excerpts[-1] if excerpts else ""),
            "metrics": metrics,
            "evidence": [
                {
                    "source_type": item["source_type"],
                    "source_ref": item["source_ref"],
                    "excerpt_summary": item["excerpt_summary"],
                    "confidence": item["confidence"],
                }
                for item in items[:8]
            ],
            "confidence": round(sum(item["confidence"] for item in items) / len(items), 3),
            "resume_ready": any(item.get("resume_ready_hint") for item in items) or bool(metrics),
            "source_types": source_types,
            "matched_keywords": top_tags,
            "user_check_flags": list(dict.fromkeys(flag for item in items for flag in item.get("user_check_flags", []))),
            "user_check_evidence": list(dict.fromkeys(flag for item in items for flag in item.get("user_check_evidence", []))),
            "one_line_scope": task,
            "core_actions": actions[:3],
            "core_result": outcome,
            "best_metric": best_metric,
            "business_value": business_value,
            "extraction_backends": extraction_backends,
            "interview_explain": build_interview_safe_explain(normalized_title, task, actions, best_metric, business_value),
            "resume_safe_bullet_seed": build_resume_seed(normalized_title, task, actions, outcome),
        }
        achievement["gaps"] = derive_gaps(metrics, business_context, source_types, len(items))
        achievement["risk_flags"] = derive_risk_flags(achievement)
        achievement["user_check_flags"], achievement["user_check_evidence"] = derive_user_check_fields(achievement)
        achievement["readiness_reason"] = derive_readiness_reason(metrics, source_types, business_context)
        achievements.append(achievement)
    achievements = merge_similar_achievements(achievements)
    achievements.sort(key=lambda item: (not item["resume_ready"], len(item["risk_flags"]), -len(item["evidence"]), item["title"]))
    return achievements


def rewrite_business_context(audit: dict[str, Any]) -> str:
    contexts = [item.get("business_context", "").strip() for item in audit.get("achievements", []) if item.get("business_context", "").strip()]
    unique_contexts = list(dict.fromkeys(contexts))
    if not unique_contexts:
        return "# 业务背景改写\n\n暂无足够业务背景信息，建议补充业务目标、数据流转方式、上下游角色和人工流程痛点。\n"
    primary = unique_contexts[0]
    secondary = unique_contexts[1] if len(unique_contexts) > 1 else ""
    parts = [
        "# 业务背景改写",
        "",
        "## 可直接复用版本",
        "",
        "- 该项目面向 Agent 评估或业务执行场景，核心目标通常是降低人工审核与标注成本，并让关键判断与失败归因更自动化、更稳定。",
        "- 从工作流角度看，这类系统通常处在轨迹采集、任务评估、失败 case 归因、数据回流和策略迭代之间。",
        f"- 当前材料里的原始业务线索：{primary}",
    ]
    if secondary:
        parts.append(f"- 补充业务线索：{secondary}")
    parts.extend(
        [
            "",
            "## 面试讲述建议",
            "",
            "- 对外讲述时，优先强调真实业务痛点、人工成本压力，以及你负责的那段 workflow 或自动化链路。",
            "- 如果项目仍在迭代，可以先说明你负责的链路范围、当前做到哪里，以及哪些结果还在持续验证。",
        ]
    )
    return "\n".join(parts) + "\n"


def audit_sources(sources: list[dict[str, Any]], name: str | None = None) -> dict[str, Any]:
    validated = validate_sources(sources)
    source_summaries: list[dict[str, Any]] = []
    evidence_items: list[dict[str, Any]] = []
    knowledge_entries: list[dict[str, Any]] = []
    has_structured_source = any(load_structured_extract(bundle) for bundle in validated)
    for bundle in validated:
        if bundle["source_type"] == "code_repo":
            summary, evidence = analyze_code_repo(bundle)
            source_summaries.append(summary)
            evidence_items.extend(evidence)
        else:
            summary, evidence, knowledge = analyze_textual_bundle(
                bundle,
                prefer_context_only_business_docs=has_structured_source,
            )
            source_summaries.append(summary)
            evidence_items.extend(evidence)
            if knowledge:
                knowledge_entries.append(knowledge)

    achievements = merge_achievements(evidence_items, knowledge_entries)
    missing = []
    if not any(item["metrics"] for item in achievements):
        missing.append("缺少量化指标")
    if not any(item["business_context"] for item in achievements):
        missing.append("缺少清晰业务背景")
    if not any("code_repo" in item["source_types"] for item in achievements):
        missing.append("缺少代码侧证据")

    return {
        "name": name or "internship-achievement-audit",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_count": len(validated),
        "sources": source_summaries,
        "achievements": achievements,
        "knowledge_modes": [entry["mode"] for entry in knowledge_entries],
        "extraction_modes": sorted({str(source.get("extraction_backend") or "rules") for source in source_summaries}),
        "missing_information": missing,
    }


def summarize_action(text: str) -> str:
    for sentence in sentence_candidates(text):
        lowered = sentence.lower()
        if any(keyword in lowered for keyword in ("负责", "实现", "搭建", "优化", "设计", "构建", "support", "build", "improve", "design")):
            return sentence[:140]
    return text.strip().replace("\n", " ")[:140]


def render_markdown(audit: dict[str, Any]) -> str:
    achievement_rows = []
    for item in audit["achievements"][:10]:
        achievement_rows.append(
            [
                item["title"],
                ", ".join(item["source_types"]),
                "是" if item["resume_ready"] else "否",
                ", ".join(item["metrics"][:3]) or "待补量化",
                ", ".join(item["matched_keywords"][:5]),
                "; ".join([*item["risk_flags"], *item.get("user_check_flags", [])]) or "低",
            ]
        )

    parts = [
        f"# {audit['name']} 成果审计报告",
        "",
        f"- generated_at: `{audit['generated_at']}`",
        f"- source_count: {audit['source_count']}",
        f"- knowledge_modes: {', '.join(audit['knowledge_modes']) or 'none'}",
        f"- extraction_modes: {', '.join(audit.get('extraction_modes', [])) or 'rules'}",
        "",
        "## 成果概览",
        "",
        markdown_table(["Title", "Sources", "Resume Ready", "Metrics", "Keywords", "Risks"], achievement_rows),
        "",
        "## 缺失信息",
        "",
        "\n".join(f"- {item}" for item in audit["missing_information"]) or "- 暂无",
        "",
        "## 主要来源",
    ]
    for source in audit["sources"]:
        source_bits = [source["type"], source["title"]]
        if source["type"] == "code_repo":
            source_bits.append(", ".join(f"{lang}:{count}" for lang, count in source["language_counts"][:4]))
        else:
            source_bits.append(", ".join(source.get("top_terms", [])[:8]))
            source_bits.append(source.get("extraction_backend", "rules"))
        parts.append(f"- {' | '.join(bit for bit in source_bits if bit)}")

    parts.extend(["", "## 代表性成果"])
    for item in audit["achievements"][:5]:
        parts.extend(
            [
                "",
                f"### {item['title']}",
                f"- background: {item['background']}",
                f"- action: {summarize_action(' '.join(item['actions']))}",
                f"- outcome: {item['outcome'] or '待补结果'}",
                f"- readiness_reason: {item.get('readiness_reason', '待确认')}",
                f"- gaps: {', '.join(item.get('gaps', [])) or '暂无'}",
                f"- user_check: {'; '.join(item.get('user_check_flags', [])) or '无'}",
                f"- evidence: {', '.join(e['source_ref'] for e in item['evidence'][:4])}",
            ]
        )
    return "\n".join(parts)


def render_html(audit: dict[str, Any], markdown: str) -> str:
    del markdown
    achievement_cards = []
    for item in audit["achievements"][:8]:
        evidence = "".join(
            f"<li><code>{html.escape(e['source_ref'])}</code> {html.escape(e['excerpt_summary'])}</li>"
            for e in item["evidence"][:4]
        )
        achievement_cards.append(
            f"""
            <section class=\"card\">
              <h3>{html.escape(item['title'])}</h3>
              <p><strong>背景:</strong> {html.escape(item['background'])}</p>
              <p><strong>结果:</strong> {html.escape(item['outcome'] or '待补结果')}</p>
              <p><strong>指标:</strong> {html.escape(', '.join(item['metrics']) or '待补量化')}</p>
              <p><strong>为何可写:</strong> {html.escape(item.get('readiness_reason', '待确认'))}</p>
              <p><strong>缺口:</strong> {html.escape('；'.join(item.get('gaps', [])) or '暂无')}</p>
              <ul>{evidence}</ul>
            </section>
            """
        )
    source_items = "".join(
        f"<li><strong>{html.escape(source['title'])}</strong> <span>{html.escape(source['type'])}</span></li>"
        for source in audit["sources"]
    )
    missing = "".join(f"<li>{html.escape(item)}</li>" for item in audit["missing_information"]) or "<li>暂无</li>"
    return f"""<!doctype html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>{html.escape(audit['name'])} 成果审计报告</title>
  <style>
    body {{ font-family: 'Segoe UI', sans-serif; margin: 0; background: #f3f5f7; color: #14202b; }}
    main {{ max-width: 1080px; margin: 0 auto; padding: 28px 18px 48px; }}
    .hero, .panel, .card {{ background: #fff; border: 1px solid #d9e0e8; border-radius: 10px; padding: 18px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }}
    .hero {{ margin-bottom: 18px; }}
    h1, h2, h3 {{ margin-top: 0; }}
    code {{ background: #eef2f6; padding: 1px 4px; border-radius: 4px; }}
  </style>
</head>
<body>
  <main>
    <section class=\"hero\">
      <p>多源实习材料成果审计</p>
      <h1>{html.escape(audit['name'])}</h1>
      <p>sources={audit['source_count']} | knowledge_modes={html.escape(', '.join(audit['knowledge_modes']) or 'none')}</p>
    </section>
    <section class=\"panel\">
      <h2>缺失信息</h2>
      <ul>{missing}</ul>
      <h2>主要来源</h2>
      <ul>{source_items}</ul>
    </section>
    <section class=\"grid\">
      {''.join(achievement_cards)}
    </section>
  </main>
</body>
</html>"""
def write_audit_outputs(audit: dict[str, Any], out_dir: str | Path) -> dict[str, str]:
    out = ensure_dir(out_dir)
    markdown = render_markdown(audit)
    html_doc = render_html(audit, markdown)
    business_context_rewrite = rewrite_business_context(audit)
    return {
        "achievement_audit_json": str(write_json(out / "achievement_audit.json", audit)),
        "overview_md": str(write_text(out / "overview.md", markdown)),
        "overview_html": str(write_text(out / "overview.html", html_doc)),
        "business_context_rewrite_md": str(write_text(out / "business_context_rewrite.md", business_context_rewrite)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit multi-source internship materials into resume-ready achievements.")
    parser.add_argument("--sources", required=True, help="Path to source bundle JSON.")
    parser.add_argument("--out", required=True, help="Output directory.")
    parser.add_argument("--name", default=None, help="Display name for the audit report.")
    args = parser.parse_args(argv)

    payload = load_json(args.sources)
    sources = parse_sources(payload)
    audit = audit_sources(sources, name=args.name)
    paths = write_audit_outputs(audit, args.out)
    for label, path in paths.items():
        print(f"{label}: {path}")
    return 0


__all__ = [
    "audit_sources",
    "build_source_bundle",
    "parse_sources",
    "rewrite_business_context",
    "render_markdown",
    "validate_sources",
    "write_audit_outputs",
]


if __name__ == "__main__":
    raise SystemExit(main())
