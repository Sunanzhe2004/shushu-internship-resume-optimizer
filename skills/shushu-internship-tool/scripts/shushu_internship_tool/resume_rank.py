from __future__ import annotations

import argparse
import math
import re
from pathlib import Path
from typing import Any

from .common import ensure_dir, load_json, markdown_table, normalize_list, write_json, write_text
from .resume_style_bench import (
    detect_generated_style_issues,
    evaluate_risk_phrases,
    get_style_benchmark,
)


TOKEN_RE = re.compile(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9_+#.-]{1,}")
CLAUSE_SPLIT_RE = re.compile(r"[，。！？；;\n]")
SENTENCE_SPLIT_RE = re.compile(r"[。！？；;\n]")
NOISE_PREFIXES = (
    "核心职责",
    "技术栈",
    "项目描述",
    "一句话定位",
    "业务背景",
    "核心问题",
    "项目目标",
    "当前工作主要聚焦",
    "我的工作定位",
    "关键迭代过程",
    "当前阶段结果",
)
NOISE_EXACT = {
    "异步评估服务工程化",
    "自动评估任务完成情况优化",
    "错误标签自动化判别",
    "错误标签自动化归因",
    "无效数据检测体系设计（P-E-R 流水线）",
    "LLM-as-Judge 评估 Prompt 工程",
}
LOW_VALUE_WORKLOAD_RE = re.compile(
    r"(?i)(?:读取|扫描|遍历|处理|分析|review|read|scan|process).{0,12}\d+\s*(?:个|份|条|文件|file|files|仓库|repo|repos)"
)
VALUE_SIGNAL_RE = re.compile(
    r"(?i)(?:减少|降低|提升|优化|节省|支持|避免|拦截|过滤|定位|归因|解释|恢复|稳定|吞吐|准确率|召回率|一致率|F1|Recall|Precision|成本|效率|误判|耗时|延迟|成功率)"
)


def tokenize(text: str) -> set[str]:
    tokens: set[str] = set()
    for raw in TOKEN_RE.findall(text):
        token = raw.lower()
        tokens.add(token)
        if re.fullmatch(r"[\u4e00-\u9fff]{3,}", raw):
            for index in range(len(raw) - 1):
                tokens.add(raw[index : index + 2])
    return tokens


def extract_jd_keywords(jd_text: str) -> list[str]:
    tokens = list(dict.fromkeys(TOKEN_RE.findall(jd_text)))
    preferred = ["fastapi", "asyncio", "python", "后端", "backend", "llm", "prompt", "评估", "归因", "自动化"]
    ordered: list[str] = []
    lowered = jd_text.lower()
    for keyword in preferred:
        if keyword.lower() in lowered:
            ordered.append(keyword)
    for token in tokens:
        if token not in ordered:
            ordered.append(token)
    return ordered


def parse_achievements(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [dict(item) for item in payload]
    if isinstance(payload, dict) and isinstance(payload.get("achievements"), list):
        return [dict(item) for item in payload["achievements"]]
    raise ValueError("achievement JSON must be a list or an object with an 'achievements' list")


def clip_text(text: str, max_len: int) -> str:
    clean = " ".join(str(text).split())
    if len(clean) <= max_len:
        return clean
    return clean[:max_len].rstrip("，。！？；,.!? ")


def compress_phrase(text: str, max_len: int) -> str:
    clean = " ".join(str(text).split())
    if len(clean) <= max_len:
        return clean
    clauses = [part.strip(" -") for part in CLAUSE_SPLIT_RE.split(clean) if part.strip(" -")]
    for clause in clauses:
        if 6 <= len(clause) <= max_len:
            return clause
    return clip_text(clean, max_len)


def sanitize_text(text: str) -> str:
    value = " ".join(str(text).replace("\n", " ").split()).strip(" -:：")
    value = re.sub(r"^#+\s*", "", value)
    value = re.sub(r"^\d+[.)、]\s*", "", value)
    value = value.strip(" -:：")
    return value


def is_noise_line(text: str) -> bool:
    value = sanitize_text(text)
    if not value:
        return True
    if value in NOISE_EXACT:
        return True
    return any(value.startswith(prefix) for prefix in NOISE_PREFIXES)


def is_low_value_workload_text(text: str) -> bool:
    clean = sanitize_text(text)
    return bool(LOW_VALUE_WORKLOAD_RE.search(clean)) and not VALUE_SIGNAL_RE.search(clean)


def clean_action(action: str, title: str) -> str:
    value = sanitize_text(action)
    if is_noise_line(value) or is_low_value_workload_text(value):
        return ""
    if title and title in value:
        value = value.replace(title, "", 1).strip("，。！？； ")
    value = re.sub(r"^(通过|基于|围绕|针对)\s*", "", value)
    return value


def best_metric(metrics: list[str]) -> str:
    if not metrics:
        return ""
    priority = ["F1", "Recall", "Precision", "一致率", "准确率", "召回率", "减少", "降低", "提升", "30s", "%"]
    for keyword in priority:
        for metric in metrics:
            if keyword.lower() in metric.lower():
                return metric
    return metrics[0]


def choose_lead_verb(item: dict[str, Any], variant: int = 0) -> str:
    text = " ".join(
        [
            item.get("title", ""),
            item.get("task", ""),
            " ".join(normalize_list(item.get("actions"))),
        ]
    ).lower()
    if any(keyword in text for keyword in ("评估", "eval", "judge")):
        return "优化" if variant == 0 else "搭建"
    if any(keyword in text for keyword in ("标签", "归因", "分类")):
        return "推进" if variant == 0 else "完善"
    if any(keyword in text for keyword in ("服务", "fastapi", "asyncio", "workflow", "pipeline")):
        return "搭建" if variant == 0 else "落地"
    if any(keyword in text for keyword in ("prompt", "llm", "vlm", "规则")):
        return "迭代" if variant == 0 else "优化"
    return "负责" if variant == 0 else "推进"


def extract_sentences(text: str) -> list[str]:
    clean = sanitize_text(text)
    if not clean:
        return []
    return [part.strip() for part in SENTENCE_SPLIT_RE.split(clean) if part.strip()]


def extract_action_fragments(item: dict[str, Any], limit: int = 3) -> list[str]:
    fragments: list[str] = []
    title = item.get("title", "")
    task = clean_action(item.get("task", ""), title)
    if task:
        fragments.append(task)
    for raw in normalize_list(item.get("actions")):
        for sentence in extract_sentences(raw):
            cleaned = clean_action(sentence, title)
            if cleaned and cleaned not in fragments:
                fragments.append(cleaned)
            if len(fragments) >= limit:
                return fragments
    return fragments[:limit]


def choose_focus_fragment(item: dict[str, Any]) -> str:
    seeded = sanitize_text(item.get("one_line_scope", ""))
    if seeded:
        return compress_phrase(seeded, 28)
    fragments = extract_action_fragments(item, limit=4)
    if not fragments:
        return "推进评估链路优化"
    preferred = ("设计", "搭建", "优化", "迭代", "实现", "构建", "接入", "过滤", "识别", "归因", "支持")
    for keyword in preferred:
        for fragment in fragments:
            if keyword in fragment:
                return compress_phrase(fragment, 28)
    return compress_phrase(fragments[0], 28)


def choose_business_context(item: dict[str, Any]) -> str:
    context = item.get("business_context") or item.get("background") or item.get("title", "")
    return compress_phrase(sanitize_text(context), 24)


def extract_metric_summary(item: dict[str, Any]) -> str:
    if item.get("best_metric"):
        return sanitize_text(item["best_metric"])
    if item.get("core_result"):
        result = sanitize_text(item["core_result"])
        if result and result != sanitize_text(item.get("one_line_scope", "")):
            return result
    metrics = normalize_list(item.get("metrics"))
    if metrics:
        return best_metric(metrics)
    joined = " ".join(normalize_list(item.get("actions")))
    candidates = re.findall(
        r"(F1[^，。；\n]*|Recall[^，。；\n]*|Precision[^，。；\n]*|[^，。；\n]*(?:一致率|准确率|召回率|误判率|无效 LLM 调用|%|30s)[^，。；\n]*)",
        joined,
        flags=re.I,
    )
    cleaned = [sanitize_text(candidate) for candidate in candidates if sanitize_text(candidate)]
    return cleaned[0] if cleaned else ""


def infer_semantic_track(item: dict[str, Any]) -> str:
    text = " ".join(
        [
            sanitize_text(item.get("title", "")),
            sanitize_text(item.get("task", "")),
            sanitize_text(item.get("outcome", "")),
            sanitize_text(item.get("business_context", "")),
            " ".join(normalize_list(item.get("actions"))),
            " ".join(normalize_list(item.get("tech_stack"))),
        ]
    ).lower()
    if any(keyword in text for keyword in ("service", "fastapi", "asyncio", "http", "queue", "workflow", "pipeline", "服务")):
        return "service"
    if any(keyword in text for keyword in ("label", "归因", "标签", "错误", "失败", "case")):
        return "analysis"
    if any(keyword in text for keyword in ("prompt", "llm", "vlm", "judge", "评估", "eval", "判定", "规则")):
        return "evaluation"
    return "general"


def title_track(item: dict[str, Any]) -> str:
    return infer_semantic_track(item)


def track_rank(item: dict[str, Any]) -> int:
    order = {"evaluation": 0, "analysis": 1, "service": 2, "general": 3}
    return order.get(title_track(item), 9)


def related_item_tokens(item: dict[str, Any]) -> set[str]:
    return tokenize(
        " ".join(
            [
                item.get("title", ""),
                item.get("one_line_scope", ""),
                item.get("task", ""),
                item.get("business_context", ""),
                item.get("background", ""),
                " ".join(normalize_list(item.get("tech_stack"))),
                " ".join(normalize_list(item.get("matched_keywords"))),
                " ".join(entry.get("source_ref", "") for entry in item.get("evidence", [])),
            ]
        )
    )


def merge_reason_summary(left: dict[str, Any], right: dict[str, Any], overlap: set[str]) -> list[str]:
    reasons: list[str] = []
    if title_track(left) == title_track(right):
        reasons.append("同一能力主线")
    shared_tech = list(dict.fromkeys(set(normalize_list(left.get("tech_stack"))) & set(normalize_list(right.get("tech_stack")))))
    if shared_tech:
        reasons.append(f"共享技术栈：{', '.join(shared_tech[:3])}")
    left_context = choose_business_context(left)
    right_context = choose_business_context(right)
    if left_context and right_context and (left_context in right_context or right_context in left_context):
        reasons.append("业务上下文高度重合")
    shared_sources = list(
        dict.fromkeys(
            {
                entry.get("source_ref", "")
                for entry in left.get("evidence", [])
                if entry.get("source_ref")
            }
            & {
                entry.get("source_ref", "")
                for entry in right.get("evidence", [])
                if entry.get("source_ref")
            }
        )
    )
    if shared_sources:
        reasons.append(f"证据来源重合：{', '.join(shared_sources[:2])}")
    if overlap:
        reasons.append(f"关键词重合：{', '.join(sorted(overlap)[:5])}")
    return reasons[:4]


def relation_score(left: dict[str, Any], right: dict[str, Any]) -> tuple[int, list[str]]:
    overlap = related_item_tokens(left) & related_item_tokens(right)
    score = len(overlap)
    if title_track(left) == title_track(right):
        score += 3
    if set(normalize_list(left.get("tech_stack"))) & set(normalize_list(right.get("tech_stack"))):
        score += 2
    left_context = choose_business_context(left)
    right_context = choose_business_context(right)
    if left_context and right_context and (left_context in right_context or right_context in left_context):
        score += 2
    left_sources = {entry.get("source_ref", "") for entry in left.get("evidence", []) if entry.get("source_ref")}
    right_sources = {entry.get("source_ref", "") for entry in right.get("evidence", []) if entry.get("source_ref")}
    if left_sources & right_sources:
        score += 2
    return score, merge_reason_summary(left, right, overlap)


def concise_metric(metric: str) -> str:
    clean = sanitize_text(metric)
    if not clean:
        return ""
    if len(clean) > 34:
        clean = compress_phrase(clean, 34)
    return clean


def build_merged_bullet(left: dict[str, Any], right: dict[str, Any], variant: int = 0) -> str:
    context = choose_business_context(left)
    other_context = choose_business_context(right)
    if other_context and len(other_context) > len(context):
        context = other_context
    action_a = choose_focus_fragment(left)
    action_b = choose_focus_fragment(right)
    metric_a = concise_metric(extract_metric_summary(left))
    metric_b = concise_metric(extract_metric_summary(right))
    metrics = [metric for metric in [metric_a, metric_b] if metric]
    metric_text = "；".join(list(dict.fromkeys(metrics))[:2])
    shared_tech = "/".join(
        list(dict.fromkeys([*normalize_list(left.get("tech_stack")), *normalize_list(right.get("tech_stack"))]))[:3]
    )
    if variant == 0:
        sentence = f"围绕{context}，串联{action_a}与{action_b}"
        if shared_tech:
            sentence += f"，覆盖{shared_tech}等关键实现"
    else:
        sentence = f"将两块强关联工作合并整理：一方面{action_a}，另一方面{action_b}"
        if context:
            sentence += f"，共同服务于{context}"
    if metric_text:
        sentence += f"，结果可结合{metric_text}一起表达"
    return sentence


def build_related_merge_candidates(ranked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for index, left in enumerate(ranked):
        for other_index in range(index + 1, len(ranked)):
            right = ranked[other_index]
            score, reasons = relation_score(left, right)
            if score < 8:
                continue
            candidates.append(
                {
                    "achievement_titles": [left.get("title", ""), right.get("title", "")],
                    "merge_strength": score,
                    "merge_reasons": reasons,
                    "merged_resume_bullets": [
                        build_merged_bullet(left, right, variant=0),
                        build_merged_bullet(left, right, variant=1),
                    ],
                }
            )
    return sorted(candidates, key=lambda item: (-item["merge_strength"], item["achievement_titles"]))


def causal_stage(bullet: str) -> int:
    text = sanitize_text(bullet)
    lowered = text.lower()
    if any(keyword in text for keyword in ("结果为", "核心结果", "最终", "从而", "因此", "进而")):
        return 2
    if any(keyword in text for keyword in ("减少", "降低", "提升", "节省", "支撑", "避免", "稳定", "提效", "优化效果")):
        return 2
    if any(keyword in lowered for keyword in ("f1", "recall", "precision")) or "%" in text:
        return 2
    if any(keyword in text for keyword in ("优化", "迭代", "完善", "补充", "改进", "归因")):
        return 1
    if any(keyword in text for keyword in ("搭建", "设计", "构建", "实现", "梳理", "沉淀", "接入", "过滤", "识别", "服务化")):
        return 0
    return 1


def reorder_bullets_by_causality(bullets: list[str]) -> list[str]:
    decorated = [(index, bullet, causal_stage(bullet)) for index, bullet in enumerate(bullets) if str(bullet).strip()]
    if len(decorated) < 2:
        return [bullet for _, bullet, _ in decorated]
    if len({stage for _, _, stage in decorated}) == 1:
        return [bullet for _, bullet, _ in decorated]
    ordered = sorted(decorated, key=lambda item: (item[2], item[0]))
    return [bullet for _, bullet, _ in ordered]


def build_track_bullet(item: dict[str, Any], variant: int = 0) -> str:
    track = title_track(item)
    title = sanitize_text(item.get("title", "项目"))
    action = choose_focus_fragment(item)
    metric = concise_metric(extract_metric_summary(item))
    business = choose_business_context(item)
    value = compress_phrase(sanitize_text(item.get("business_value", "")), 24)
    tech = "/".join(normalize_list(item.get("tech_stack"))[:3]) or "Python"

    if track == "service":
        base = (
            f"围绕{business or title}搭建服务化能力，基于{tech}完成{action}"
            if variant == 0
            else f"将{title}落到可复用服务形态，围绕{action}补齐工程化运行能力"
        )
    elif track == "analysis":
        base = (
            f"围绕{business or title}推进{title}，通过{action}支撑失败样本归因与问题定位"
            if variant == 0
            else f"围绕{title}完善结构化分析链路，重点完成{action}"
        )
    elif track == "evaluation":
        base = (
            f"围绕{business or title}优化{title}，重点推进{action}"
            if variant == 0
            else f"面向{business or title}搭建评估与判定能力，围绕{action}持续迭代"
        )
    else:
        return ""

    if value and value not in base and value != action:
        base += f"，支撑{value}"
    if metric:
        base += f"，结果为{metric}"
    return base


def build_bullet(item: dict[str, Any], target_role: str, jd_text: str, variant: int = 0) -> str:
    del jd_text
    track_bullet = build_track_bullet(item, variant=variant)
    if track_bullet:
        return track_bullet

    benchmark = get_style_benchmark(target_role or item.get("target_role", ""))
    title = sanitize_text(item.get("title", "项目")) or "项目"
    action = choose_focus_fragment(item)
    business = choose_business_context(item)
    tech_stack = "/".join(normalize_list(item.get("tech_stack"))[:3]) or "Python/工程工具链"
    metric = concise_metric(extract_metric_summary(item))
    business_value = compress_phrase(sanitize_text(item.get("business_value", "")), 26)
    short_tech = compress_phrase(tech_stack, 20)
    lead = choose_lead_verb(item, variant=variant)

    if benchmark["track"] == "ai":
        if variant == 0:
            base = f"{lead}{title}，重点完成{action}"
            if business_value and business_value != action:
                base += f"，支撑{business_value}"
            return base + (f"，结果为{metric}" if metric else "")
        return f"在{business or title}场景中{lead}{title}，结合{short_tech}推进{action}" + (f"，核心结果为{metric}" if metric else "")

    if variant == 0:
        base = f"{lead}{title}，基于{compress_phrase(tech_stack, 18)}推进{action}"
        if business_value and business_value != action:
            base += f"，支撑{business_value}"
        return base + (f"，结果为{metric}" if metric else "")
    return f"围绕{business or title}落地{title}，通过{action}支撑业务需求" + (f"，并取得{metric}" if metric else "")


def derive_recommendation_reason(item: dict[str, Any]) -> str:
    reasons = []
    if item.get("keywords_hit"):
        reasons.append(f"命中 {len(item['keywords_hit'])} 个 JD 关键词")
    if item.get("metrics"):
        reasons.append("有可引用指标")
    if item.get("business_context"):
        reasons.append("有业务背景可解释")
    if "code_repo" in item.get("source_types", []):
        reasons.append("有代码侧证据")
    if item.get("user_check_flags"):
        reasons.append("部分表述建议和本人经历再核对")
    return "；".join(reasons) or "信息较少，建议先补充材料再写入正式简历"


def derive_next_steps(item: dict[str, Any]) -> list[str]:
    steps: list[str] = []
    text = " ".join(
        [
            item.get("title", ""),
            item.get("background", ""),
            item.get("task", ""),
            item.get("outcome", ""),
            item.get("business_context", ""),
            " ".join(normalize_list(item.get("actions"))),
            " ".join(normalize_list(item.get("matched_keywords"))),
        ]
    ).lower()
    metrics_text = " ".join(normalize_list(item.get("metrics"))).lower()

    if any(keyword in text for keyword in ("评估", "eval", "judge", "f1", "recall", "precision")) and not any(
        marker in metrics_text for marker in ("f1", "recall", "precision")
    ):
        steps.append("补充任务完成判断的核心评估指标，例如 F1、Recall、Precision，以及对应样本量和评测口径")
    if any(keyword in text for keyword in ("标签", "归因", "失败", "error", "case")):
        steps.append("补充一级/二级错误标签归因的准确率、覆盖率，或人工抽检一致性结果")
    if any(keyword in text for keyword in ("workflow", "服务", "fastapi", "asyncio", "批量", "pipeline")):
        steps.append("补充 workflow 或服务化落地证据，例如接口形态、并发规模、任务恢复机制或批处理吞吐表现")
    if any(keyword in text for keyword in ("prompt", "llm", "vlm", "规则")) and not item.get("metrics"):
        steps.append("补充 prompt 优化或规则改造前后的效果对比，例如误判下降、无效调用减少或审核成本节省")
    if not item.get("business_context"):
        steps.append("补充业务背景，说明这套评估或自动打标流程处在数据闭环的哪个环节")
    if "code_repo" not in item.get("source_types", []):
        steps.append("补充代码、PR 或服务实现证据，最好能对应到具体模块、脚本、接口或评测任务")
    if item.get("user_check_flags"):
        steps.append("逐条确认 AI 总结味重或可能夸大的表述是否准确，尤其是“独立负责”“显著提升”“闭环”等说法")
    if not item.get("resume_ready"):
        steps.append("先补齐关键信息，再压缩成 2 到 4 条简历 bullet，避免长段项目总结直接上简历")

    deduped = list(dict.fromkeys(steps))
    return deduped or ["已经具备简历改写基础，下一步可以直接压缩成正式投递版项目描述"]


def score_achievement(item: dict[str, Any], jd_text: str, target_role: str) -> dict[str, Any]:
    jd_tokens = set(extract_jd_keywords(jd_text))
    text = " ".join(
        [
            item.get("title", ""),
            item.get("task", ""),
            item.get("outcome", ""),
            item.get("business_context", ""),
            " ".join(normalize_list(item.get("actions"))),
            " ".join(normalize_list(item.get("matched_keywords"))),
        ]
    )
    item_tokens = tokenize(text)
    matches = [token for token in extract_jd_keywords(jd_text) if token.lower() in item_tokens]

    keyword_points = min(36, len(matches) * 4)
    evidence_points = min(20, len(item.get("evidence", [])) * 4)
    metric_points = 16 if normalize_list(item.get("metrics")) else 0
    readiness_points = 12 if item.get("resume_ready") else 4
    business_points = 8 if item.get("business_context") else 0

    primary_bullet = build_bullet(item, target_role, jd_text, variant=0)
    backup_bullet = build_bullet(item, target_role, jd_text, variant=1)
    benchmark = get_style_benchmark(target_role or item.get("target_role", ""))
    phrasing_risks = evaluate_risk_phrases(primary_bullet, benchmark)
    risk_notes = list(dict.fromkeys([*normalize_list(item.get("risk_flags")), *normalize_list(item.get("user_check_flags")), *phrasing_risks]))
    risk_penalty = min(20, len(risk_notes) * 3)

    score = max(
        0,
        keyword_points + evidence_points + metric_points + readiness_points + business_points - risk_penalty,
    )

    ranked = dict(item)
    ranked.update(
        {
            "target_role": target_role,
            "score": score,
            "keywords_hit": matches[:10],
            "risk_notes": risk_notes,
            "resume_bullets": [primary_bullet, backup_bullet],
            "best_metric": extract_metric_summary(item),
            "recommendation_reason": derive_recommendation_reason({**item, "keywords_hit": matches}),
            "next_steps": derive_next_steps({**item, "matched_keywords": matches}),
            "score_breakdown": {
                "jd_match": keyword_points,
                "evidence": evidence_points,
                "metric": metric_points,
                "readiness": readiness_points,
                "business": business_points,
                "risk_penalty": risk_penalty,
            },
        }
    )
    return ranked


def rank_achievements(jd_text: str, achievements: list[dict[str, Any]], target_role: str) -> list[dict[str, Any]]:
    ranked = [score_achievement(item, jd_text, target_role) for item in achievements]
    return sorted(
        ranked,
        key=lambda item: (-item["score"], track_rank(item), len(item["risk_notes"]), item["title"]),
    )


def render_markdown(ranked: list[dict[str, Any]], target_role: str) -> str:
    top = ranked[0] if ranked else None
    style_issues = detect_generated_style_issues([top["resume_bullets"][0], top["resume_bullets"][1]]) if top else []
    lines = [
        "# 简历排序报告",
        "",
        f"- target role: `{target_role or '未指定'}`",
        f"- achievement count: `{len(ranked)}`",
        f"- primary recommendation: `{top['title']}` score={top['score']}" if top else "- primary recommendation: none",
        "",
    ]
    if top:
        lines.extend(
            [
                "## 推荐写法",
                "",
                f"- {top['resume_bullets'][0]}",
                f"- {top['resume_bullets'][1]}",
                "",
            ]
        )
    if style_issues:
        lines.extend(["## 生成表述提醒", "", *[f"- {issue}" for issue in style_issues], ""])
    if ranked:
        rows = [
            [item["title"], item["score"], ", ".join(item["keywords_hit"][:5]) or "待补充", "；".join(item["risk_notes"][:3]) or "低"]
            for item in ranked[:8]
        ]
        lines.extend(["## 排序概览", "", markdown_table(["title", "score", "keywords", "risk"], rows), ""])
    return "\n".join(lines).strip() + "\n"


def render_resume_project_summary(
    ranked: list[dict[str, Any]],
    target_role: str,
    use_merged_bullet: bool = False,
) -> str:
    merge_candidates = build_related_merge_candidates(ranked)
    role_label = target_role or (ranked[0].get("target_role", "") if ranked else "未指定")
    top = ranked[:4]
    bullets = [item["resume_bullets"][0] for item in top if item.get("resume_bullets")]
    if use_merged_bullet and merge_candidates:
        bullets = [merge_candidates[0]["merged_resume_bullets"][1], *bullets]
    bullets = reorder_bullets_by_causality(bullets)
    style_issues = detect_generated_style_issues(bullets)

    lines = [
        "# 简历项目精简版",
        "",
        f"- 面向 `{role_label}` 的简历版项目描述，建议保留 1 句项目定位 + 2 到 4 条结果导向 bullet。",
        "- 可直接写进简历，也可以作为后续 refine 的输入底稿。",
        "",
        "## 建议写法",
        "",
        "\n".join(f"- {bullet}" for bullet in bullets[:4]),
        "",
    ]
    if merge_candidates:
        top_merge = merge_candidates[0]
        lines.extend(
            [
                "## 强关联项目合并建议",
                "",
                f"- 推荐组合：{' + '.join(top_merge['achievement_titles'])}",
                f"- 原因：{'；'.join(top_merge['merge_reasons'])}",
                f"- 合并版 bullet：{top_merge['merged_resume_bullets'][0]}",
                "- 默认仍保留拆开写；如果你更想突出一条完整主线，可以改用这条合并版 bullet。",
                "",
            ]
        )
    if style_issues:
        lines.extend(["## 生成表述提醒", "", *[f"- {issue}" for issue in style_issues], ""])
    lines.extend(
        [
            "## 使用提醒",
            "",
            "- 长版 `.md` 更适合自己复盘、面试准备和补证据；简历里建议只保留 1 句项目定位 + 2 到 4 条结果导向 bullet。",
            "",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def write_ranking_outputs(
    ranked: list[dict[str, Any]],
    out_dir: str | Path,
    target_role: str,
    use_merged_bullet: bool = False,
) -> dict[str, str]:
    out = ensure_dir(out_dir)
    merge_candidates = build_related_merge_candidates(ranked)
    payload = {
        "target_role": target_role,
        "achievement_count": len(ranked),
        "merge_related_bullets_enabled": use_merged_bullet,
        "related_merge_candidates": merge_candidates,
        "ranked_achievements": ranked,
    }
    paths = {
        "resume_rank_json": str(write_json(out / "resume_rank.json", payload)),
        "resume_rank_md": str(write_text(out / "resume_rank.md", render_markdown(ranked, target_role))),
        "resume_project_summary_md": str(
            write_text(
                out / "resume_project_summary.md",
                render_resume_project_summary(ranked, target_role, use_merged_bullet=use_merged_bullet),
            )
        ),
    }
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Rank audited achievements for resume writing.")
    parser.add_argument("--jd", required=True, help="Path to target JD text file.")
    parser.add_argument("--achievements", required=True, help="Path to achievement_audit json.")
    parser.add_argument("--target-role", default="", help="Target role label used for style selection.")
    parser.add_argument("--out", required=True, help="Output directory.")
    parser.add_argument(
        "--merge-related-bullets",
        action="store_true",
        help="When strong-related project bullets are detected, include the merged version directly in the resume project summary.",
    )
    args = parser.parse_args()

    jd_text = Path(args.jd).read_text(encoding="utf-8")
    payload = load_json(args.achievements)
    achievements = parse_achievements(payload)
    ranked = rank_achievements(jd_text, achievements, target_role=args.target_role)
    paths = write_ranking_outputs(
        ranked,
        args.out,
        target_role=args.target_role,
        use_merged_bullet=args.merge_related_bullets,
    )
    for key, value in paths.items():
        print(f"{key}: {value}")


__all__ = [
    "build_bullet",
    "build_related_merge_candidates",
    "parse_achievements",
    "rank_achievements",
    "render_markdown",
    "render_resume_project_summary",
    "write_ranking_outputs",
]


if __name__ == "__main__":
    main()
