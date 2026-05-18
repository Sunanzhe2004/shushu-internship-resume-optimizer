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
CLAUSE_SPLIT_RE = re.compile(r"[，。！？；\n]")
SENTENCE_SPLIT_RE = re.compile(r"[。！？；\n]")
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


def tokenize(text: str) -> set[str]:
    tokens: set[str] = set()
    for raw in TOKEN_RE.findall(text):
        token = raw.lower()
        tokens.add(token)
        if re.fullmatch(r"[\u4e00-\u9fff]{3,}", raw):
            for index in range(len(raw) - 1):
                tokens.add(raw[index : index + 2])
    return tokens


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


def clean_action(action: str, title: str) -> str:
    value = sanitize_text(action)
    if is_noise_line(value):
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
            if not cleaned:
                continue
            if cleaned not in fragments:
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
    candidates = re.findall(r"(F1[^，。；\n]*|Recall[^，。；\n]*|Precision[^，。；\n]*|[^，。；\n]*(?:一致率|准确率|召回率|误判率|无效 LLM 调用|%|30s)[^，。；\n]*)", joined, flags=re.I)
    cleaned = [sanitize_text(candidate) for candidate in candidates if sanitize_text(candidate)]
    return cleaned[0] if cleaned else ""


def title_track(item: dict[str, Any]) -> str:
    title = item.get("title", "")
    if "自动评估任务完成情况优化" in title:
        return "eval"
    if "错误标签自动化判别" in title or "错误标签自动化归因" in title:
        return "label"
    if "异步评估服务工程化" in title:
        return "service"
    return "general"


def track_rank(item: dict[str, Any]) -> int:
    order = {
        "eval": 0,
        "label": 1,
        "service": 2,
        "general": 3,
    }
    return order.get(title_track(item), 9)


def concise_metric(metric: str) -> str:
    clean = sanitize_text(metric)
    if not clean:
        return ""
    if "通过 Compass API 查询 `result_code`" in clean or "匹配已知错误码" in clean:
        return "可前置识别并拦截结果码异常样本"
    if "后续可以直接接入 eval 分析链路" in clean:
        return "已形成可接入后续分析链路的归因框架"
    if "asyncio.Semaphore" in clean:
        return "补齐并发控制与异步服务运行能力"
    clean = clean.replace("当前结果为", "").replace("结果达到", "").strip("，。； ")
    if len(clean) > 34:
        clean = compress_phrase(clean, 34)
    return clean


def build_track_bullet(item: dict[str, Any], variant: int = 0) -> str:
    track = title_track(item)
    metric = concise_metric(extract_metric_summary(item))

    if track == "eval":
        if variant == 0:
            base = (
                "围绕 GUI Agent 轨迹自动评估，设计 P-E-R 无效数据过滤与判定链路，"
                "通过前置规则拦截文件缺失、结果码异常等问题，减少无效样本对任务完成判断的干扰"
            )
        else:
            base = (
                "优化手机 GUI Agent 任务完成情况自动评估流程，"
                "将无效数据前置过滤、LLM 判定与后置校验拆成分层链路，提升评估稳定性"
            )
        return base + (f"，已验证 {metric}" if metric else "")

    if track == "label":
        if variant == 0:
            base = (
                "搭建失败 case 一级、二级标签归因 workflow，"
                "将任务失败原因结构化，便于后续接入 eval 分析链路并定位高频问题"
            )
        else:
            base = (
                "推进失败样本自动化归因方案设计，"
                "沉淀一级、二级标签体系，为后续策略迭代和问题分析提供统一入口"
            )
        return base + (f"，当前阶段 {metric}" if metric else "")

    if track == "service":
        if variant == 0:
            base = (
                "将 AutoEval 工具链服务化，基于 FastAPI + asyncio 搭建异步评估服务，"
                "支持 HTTP 提交、文件监听触发和任务持久化，提升采集端与评估端解耦能力"
            )
        else:
            base = (
                "完成自动评估 workflow 的服务化落地，"
                "补充并发控制、任务恢复与文件防抖机制，支撑跨机器协作运行"
            )
        return base + (f"，其中 {metric}" if metric else "")

    return ""


def build_bullet(item: dict[str, Any], target_role: str, jd_text: str, variant: int = 0) -> str:
    del jd_text
    track_bullet = build_track_bullet(item, variant=variant)
    if track_bullet:
        return track_bullet

    benchmark = get_style_benchmark(target_role or item.get("target_role", ""))
    title = item.get("title", "项目")
    action = choose_focus_fragment(item)
    business = choose_business_context(item)
    tech_stack = "/".join(normalize_list(item.get("tech_stack"))[:3]) or "Python/工程工具链"
    metric = extract_metric_summary(item)
    business_value = compress_phrase(sanitize_text(item.get("business_value", "")), 26)
    short_tech = compress_phrase(tech_stack, 20)
    lead = choose_lead_verb(item, variant=variant)

    if benchmark["track"] == "ai":
        if variant == 0:
            if "异步评估服务" in title:
                return f"基于 FastAPI + asyncio 搭建异步评估服务，支撑采集端与评估端解耦" + (f"，并通过 {metric} 验证阶段性效果" if metric else "")
            if "自动评估任务完成情况优化" in title:
                return f"设计 P-E-R 三阶段无效数据检测与评估链路，降低无效数据对任务完成判断的干扰" + (f"，当前结果为 {metric}" if metric else "")
            if "错误标签自动化判别" in title:
                return f"设计失败 case 的一级、二级标签归因 workflow，支撑高频问题定位与后续策略迭代" + (f"，阶段性结果为 {metric}" if metric else "")
            base = f"{lead}{title}，负责{action}"
            if business_value and business_value != action:
                base += f"，支撑{business_value}"
            return base + (f"，结果达到{metric}" if metric else "")
        return f"在{business}场景中{lead}{title}，结合{short_tech}完成{action}" + (f"，核心结果为{metric}" if metric else "")

    if variant == 0:
        base = f"{lead}{title}，基于{compress_phrase(tech_stack, 18)}推进{action}"
        if business_value and business_value != action:
            base += f"，支撑{business_value}"
        return base + (f"，结果达到{metric}" if metric else "")
    return f"围绕{business}落地{title}，通过{action}支撑业务需求" + (f"，并取得{metric}" if metric else "")


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
    jd_tokens = tokenize(jd_text)
    item_tokens = tokenize(
        " ".join(
            [
                item.get("title", ""),
                item.get("background", ""),
                item.get("task", ""),
                item.get("outcome", ""),
                item.get("business_context", ""),
                " ".join(normalize_list(item.get("tech_stack"))),
                " ".join(normalize_list(item.get("matched_keywords"))),
            ]
        )
    )
    matches = sorted(jd_tokens & item_tokens)
    keyword_points = min(36, len(matches) * 4)
    evidence_points = min(20, len(item.get("evidence", [])) * 3)
    metric_points = 16 if item.get("metrics") else 4
    readiness_points = 12 if item.get("resume_ready") else 2
    business_points = 10 if item.get("business_context") else 2

    primary_bullet = build_bullet(item, target_role, jd_text, variant=0)
    backup_bullet = build_bullet(item, target_role, jd_text, variant=1)
    benchmark = get_style_benchmark(target_role or jd_text)
    phrasing_risks = evaluate_risk_phrases(primary_bullet, benchmark)
    risk_notes = list(dict.fromkeys([*normalize_list(item.get("risk_flags")), *phrasing_risks]))
    if item.get("user_check_flags"):
        risk_notes.extend(flag for flag in item["user_check_flags"] if flag not in risk_notes)
    risk_notes = list(dict.fromkeys(risk_notes))
    risk_penalty = min(24, len(risk_notes) * 4)
    score = max(
        0,
        min(
            100,
            int(
                math.ceil(
                    keyword_points + evidence_points + metric_points + readiness_points + business_points - risk_penalty
                )
            ),
        ),
    )
    return {
        **item,
        "target_role": target_role,
        "score": score,
        "keywords_hit": matches[:10],
        "strength": "strong" if score >= 75 else "medium" if score >= 55 else "weak",
        "risk_notes": risk_notes,
        "resume_bullets": [primary_bullet, backup_bullet],
        "followup_questions": [
            "这个成果的业务目标是什么？",
            "你具体做了哪一部分，如何验证效果？",
            "如果没有完整指标，你会怎么证明这件事有价值？",
        ],
        "recommendation_reason": derive_recommendation_reason({**item, "keywords_hit": matches}),
        "next_steps": derive_next_steps(item),
        "score_breakdown": {
            "jd_match": keyword_points,
            "evidence_strength": evidence_points,
            "metrics": metric_points,
            "resume_readiness": readiness_points,
            "business_context": business_points,
            "risk_penalty": -risk_penalty,
        },
    }


def rank_achievements(jd_text: str, achievements: list[dict[str, Any]], target_role: str = "") -> list[dict[str, Any]]:
    scored = [score_achievement(item, jd_text, target_role=target_role) for item in achievements]
    return sorted(
        scored,
        key=lambda item: (track_rank(item), -item["score"], len(item["risk_notes"]), item["title"]),
    )


def render_markdown(ranked: list[dict[str, Any]], jd_path: str | None = None, target_role: str = "") -> str:
    rows = []
    for index, item in enumerate(ranked, start=1):
        rows.append(
            [
                index,
                item["title"],
                item["score"],
                item["strength"],
                ", ".join(item["keywords_hit"][:5]) or "待补充",
                ", ".join(item.get("metrics", [])[:3]) or "待补量化",
                "; ".join(item["risk_notes"]) or "低",
            ]
        )

    top = ranked[0] if ranked else None
    style_issues = detect_generated_style_issues([top["resume_bullets"][0], top["resume_bullets"][1]]) if top else []
    parts = [
        "# 简历成果排序",
        "",
        f"- JD source: `{jd_path}`" if jd_path else "- JD source: inline",
        f"- target_role: `{target_role or 'auto'}`",
        f"- primary recommendation: `{top['title']}` score={top['score']}" if top else "- primary recommendation: none",
        "",
        markdown_table(["Rank", "Achievement", "Score", "Strength", "Keywords", "Metrics", "Risks"], rows),
    ]
    if top:
        parts.extend(
            [
                "",
                "## 推荐写法",
                "",
                f"- {top['resume_bullets'][0]}",
                f"- {top['resume_bullets'][1]}",
                "",
                "## 为什么排前",
                "",
                f"- {top['recommendation_reason']}",
            ]
        )
        if style_issues:
            parts.extend(
                [
                    "",
                    "## 生成表述提醒",
                    "",
                    "\n".join(f"- {issue}" for issue in style_issues),
                ]
            )
        parts.extend(
            [
                "",
                "## 下一步补强",
                "",
                "\n".join(f"- {step}" for step in top["next_steps"]),
            ]
        )
    return "\n".join(parts)


def render_resume_project_summary(ranked: list[dict[str, Any]], target_role: str = "") -> str:
    if not ranked:
        return "# 简历项目精简版\n\n暂无可用项目内容。\n"

    top = sorted(ranked[:4], key=track_rank)
    primary = top[0]
    role_label = target_role or primary.get("target_role") or "AI / Agent 相关岗位"
    context = choose_business_context(primary)
    bullets = [item["resume_bullets"][0] for item in top if item.get("resume_bullets")]
    style_issues = detect_generated_style_issues(bullets)

    parts = [
        "# 简历项目精简版",
        "",
        "## 项目定位",
        "",
        f"- 面向 `{role_label}` 的简历版项目描述，建议保留 1 句项目定位 + 2 到 4 条结果导向 bullet。",
        f"- 项目背景可压缩为：{context}",
        "",
        "## 可直接写进简历",
        "",
        "\n".join(f"- {bullet}" for bullet in bullets[:4]),
    ]
    if style_issues:
        parts.extend(
            [
                "",
                "## 生成表述提醒",
                "",
                "\n".join(f"- {issue}" for issue in style_issues),
            ]
        )
    parts.extend(
        [
            "",
            "## 使用建议",
            "",
            "- 长版 `.md` 更适合自己复盘、面试准备和补证据；简历里建议只保留 1 句项目定位 + 2 到 4 条结果导向 bullet。",
            "- 如果某条里出现 AI 总结味重、边界不清或数字未确认，先和本人经历核对，再决定是否写入正式简历。",
        ]
    )
    return "\n".join(parts) + "\n"


def write_ranking_outputs(
    ranked: list[dict[str, Any]],
    out_dir: str | Path,
    jd_path: str | None = None,
    target_role: str = "",
) -> dict[str, str]:
    out = ensure_dir(out_dir)
    return {
        "resume_rank_json": str(write_json(out / "resume_rank.json", {"achievements": ranked, "target_role": target_role})),
        "resume_rank_md": str(write_text(out / "resume_rank.md", render_markdown(ranked, jd_path=jd_path, target_role=target_role))),
        "resume_project_summary_md": str(
            write_text(out / "resume_project_summary.md", render_resume_project_summary(ranked, target_role=target_role))
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rank internship achievements for resume writing against a target JD.")
    parser.add_argument("--jd", required=True, help="Path to a text file containing the target job description.")
    parser.add_argument("--achievements", required=True, help="Path to achievement JSON or achievement audit JSON.")
    parser.add_argument("--target-role", default="", help="Target role or lane, used for style calibration.")
    parser.add_argument("--out", required=True, help="Output directory.")
    args = parser.parse_args(argv)

    jd_path = Path(args.jd)
    jd_text = jd_path.read_text(encoding="utf-8", errors="replace")
    achievements = parse_achievements(load_json(args.achievements))
    ranked = rank_achievements(jd_text, achievements, target_role=args.target_role)
    paths = write_ranking_outputs(ranked, args.out, jd_path=str(jd_path), target_role=args.target_role)
    for label, path in paths.items():
        print(f"{label}: {path}")
    return 0


__all__ = [
    "build_bullet",
    "parse_achievements",
    "rank_achievements",
    "render_resume_project_summary",
    "score_achievement",
    "write_ranking_outputs",
]


if __name__ == "__main__":
    raise SystemExit(main())
