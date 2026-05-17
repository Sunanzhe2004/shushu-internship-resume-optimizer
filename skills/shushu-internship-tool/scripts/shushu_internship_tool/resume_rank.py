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
CLAUSE_SPLIT_RE = re.compile(r"[，,；;。.!？?\n]")


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
    return clean[:max_len].rstrip("，,；;。.!？? ")


def compress_phrase(text: str, max_len: int) -> str:
    clean = " ".join(str(text).split())
    if len(clean) <= max_len:
        return clean
    clauses = [part.strip(" -") for part in CLAUSE_SPLIT_RE.split(clean) if part.strip(" -")]
    for clause in clauses:
        if len(clause) <= max_len:
            return clause
    return clip_text(clean, max_len)


def clean_action(action: str, title: str) -> str:
    value = " ".join(str(action).replace("\n", " ").split()).strip(" -")
    if title and title in value:
        value = value.replace(title, "", 1).strip("：:，, ")
    return value or title


def best_metric(metrics: list[str]) -> str:
    if not metrics:
        return ""
    priority = ["F1", "Recall", "Precision", "减少", "缩短"]
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


def build_bullet(item: dict[str, Any], target_role: str, jd_text: str, variant: int = 0) -> str:
    del jd_text
    benchmark = get_style_benchmark(target_role or item.get("target_role", ""))
    title = item.get("title", "项目")
    actions = normalize_list(item.get("actions"))
    action = clean_action(actions[0] if actions else item.get("task", "推进关键模块"), title)
    business = compress_phrase(item.get("business_context") or item.get("background") or title, 34)
    tech_stack = "/".join(normalize_list(item.get("tech_stack"))[:3]) or "Python/工程化工具链"
    metric = best_metric(normalize_list(item.get("metrics")))
    short_action = compress_phrase(action, 28)
    short_tech = compress_phrase(tech_stack, 20)
    lead = choose_lead_verb(item, variant=variant)

    if benchmark["track"] == "ai":
        if variant == 0:
            if metric:
                return f"{lead}{title}，围绕{business}改进{short_action}，结果达到{metric}"
            return f"{lead}{title}，围绕{business}改进{short_action}"
        if metric:
            return f"在{business}场景中{lead}{title}，结合{short_tech}完善{compress_phrase(action, 26)}，核心结果为{metric}"
        return f"在{business}场景中{lead}{title}，结合{short_tech}完善{compress_phrase(action, 26)}"

    if variant == 0:
        if metric:
            return f"{lead}{title}，基于{compress_phrase(tech_stack, 18)}推进{short_action}，结果达到{metric}"
        return f"{lead}{title}，基于{compress_phrase(tech_stack, 18)}推进{short_action}"
    if metric:
        return f"围绕{business}落地{title}，通过{compress_phrase(action, 26)}支撑{metric}"
    return f"围绕{business}落地{title}，通过{compress_phrase(action, 26)}支撑业务需求"


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
        steps.append("补充业务背景，说明这套评估或自动打标流程处在数据闭环的哪个环节、上游下游分别是谁")
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
    return sorted(scored, key=lambda item: (-item["score"], len(item["risk_notes"]), item["title"]))


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

    top = ranked[:4]
    primary = top[0]
    role_label = target_role or primary.get("target_role") or "AI / Agent 相关岗位"
    context = compress_phrase(primary.get("business_context") or primary.get("background") or primary.get("title", ""), 90)
    bullets = [item["resume_bullets"][0] for item in top if item.get("resume_bullets")]
    style_issues = detect_generated_style_issues(bullets)

    parts = [
        "# 简历项目精简版",
        "",
        "## 项目定位",
        "",
        f"- 面向 `{role_label}` 的简历版项目描述，建议从长版项目总结中提炼后再写入正式简历。",
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
