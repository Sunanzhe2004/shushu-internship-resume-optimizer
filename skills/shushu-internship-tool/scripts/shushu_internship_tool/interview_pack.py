from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from .common import ensure_dir, load_json, markdown_table, normalize_list, write_json, write_text
from .resume_style_bench import detect_generated_style_issues, get_style_benchmark


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
)
SENTENCE_SPLIT_RE = re.compile(r"[。！？；;\n]")


def load_project_payload(path: str | Path) -> dict[str, Any]:
    payload = load_json(path)
    if isinstance(payload, dict):
        return payload
    raise ValueError("project payload must be a JSON object")


def sanitize_text(text: str) -> str:
    value = " ".join(str(text).replace("\n", " ").split()).strip(" -:：")
    value = re.sub(r"^#+\s*", "", value)
    value = re.sub(r"^\d+[.)、]\s*", "", value)
    return value.strip(" -:：")


def is_noise_line(text: str) -> bool:
    value = sanitize_text(text)
    if not value:
        return True
    return any(value.startswith(prefix) for prefix in NOISE_PREFIXES)


def extract_sentences(text: str) -> list[str]:
    clean = sanitize_text(text)
    if not clean:
        return []
    return [part.strip() for part in SENTENCE_SPLIT_RE.split(clean) if part.strip()]


def compress_sentence(text: str, fallback: str) -> str:
    clean = sanitize_text(text)
    return clean or fallback


def choose_metric(item: dict[str, Any]) -> str:
    if item.get("best_metric"):
        return sanitize_text(item["best_metric"])
    metrics = normalize_list(item.get("metrics"))
    return sanitize_text(metrics[0]) if metrics else "阶段性工程结果待补充"


def summarize_actions(item: dict[str, Any], limit: int = 2) -> str:
    candidates = [sanitize_text(line) for line in normalize_list(item.get("core_actions")) if sanitize_text(line)]
    title = sanitize_text(item.get("title", ""))
    for raw in normalize_list(item.get("actions")):
        for sentence in extract_sentences(raw):
            value = sanitize_text(sentence)
            if not value or is_noise_line(value):
                continue
            if title and title in value:
                value = value.replace(title, "", 1).strip("，。！？； ")
            if value not in candidates:
                candidates.append(value)
            if len(candidates) >= limit:
                return "；".join(candidates[:limit])
    if not candidates and item.get("task"):
        fallback = sanitize_text(item["task"])
        if fallback and not is_noise_line(fallback):
            candidates.append(fallback)
    return "；".join(candidates[:limit]) if candidates else "推进关键模块落地"


def short_context(item: dict[str, Any]) -> str:
    text = item.get("business_context") or item.get("background") or "待补业务背景"
    clean = sanitize_text(text)
    return clean[:80].rstrip("，。！？； ") if len(clean) > 80 else clean


def short_scope(item: dict[str, Any]) -> str:
    text = item.get("one_line_scope") or item.get("task") or item.get("title") or "待补职责"
    clean = sanitize_text(text)
    return clean[:48].rstrip("，。！？； ") if len(clean) > 48 else clean


def short_business_value(item: dict[str, Any]) -> str:
    text = item.get("business_value") or short_context(item)
    clean = sanitize_text(text)
    return clean[:60].rstrip("，。！？； ") if len(clean) > 60 else clean


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


def select_achievements(payload: dict[str, Any]) -> list[dict[str, Any]]:
    achievements = payload.get("achievements")
    if not isinstance(achievements, list):
        achievements = payload.get("ranked_achievements", [])
    return sorted(
        (dict(item) for item in achievements),
        key=lambda item: (
            {"evaluation": 0, "analysis": 1, "service": 2, "general": 3}.get(infer_semantic_track(item), 9),
            -int(item.get("score", 0)),
            len(item.get("risk_notes", item.get("risk_flags", []))),
            item.get("title", ""),
        ),
    )[:5]


def project_opening_line(achievements: list[dict[str, Any]]) -> str:
    primary = achievements[0]
    context = compress_sentence(
        primary.get("business_context") or primary.get("background"),
        "这个项目整体是在做一套自动化评估 workflow，目标是减少人工逐条核对成本",
    )
    return f"这个项目整体是在做{context}。"


def intro_line_for_item(item: dict[str, Any]) -> str:
    scope = short_scope(item)
    action = summarize_actions(item, limit=1)
    result = choose_metric(item)
    value = short_business_value(item)
    if action and action != scope and result and result not in {scope, action}:
        return f"我主要负责{scope}，具体做的是{action}，目前比较能落地讲的结果是{result}。"
    if action and action != scope:
        return f"我主要负责{scope}，具体做的是{action}，主要价值是{value}。"
    if result and result != scope:
        return f"我主要负责{scope}，目前比较能落地讲的结果是{result}。"
    return f"我主要负责{scope}，主要价值是{value}。"


def qa_answer_for_scope(item: dict[str, Any]) -> str:
    scope = short_scope(item)
    action = summarize_actions(item, limit=2)
    value = short_business_value(item)
    metric = choose_metric(item)
    return f"我主要负责{scope}，核心动作是{action}，这项工作的价值主要在于{value}，当前能确认的结果可以先讲{metric}。"


def qa_answer_for_flow(item: dict[str, Any]) -> str:
    track = infer_semantic_track(item)
    action = summarize_actions(item, limit=2)
    context = short_context(item)
    if track == "service":
        return f"可以先从{context}切入，再讲我是怎么把这套流程服务化的，重点包括{action}。"
    if track == "analysis":
        return f"可以先讲失败 case 怎么进入分析链路，再讲我怎么做结构化标签归因，重点包括{action}。"
    if track == "evaluation":
        return f"可以先讲任务轨迹进入评估链路后，前置过滤、核心判定和结果兜底是怎么串起来的，重点包括{action}。"
    return f"可以先从{context}切入，再补充这项工作的业务价值主要在于{short_business_value(item)}。"


def render_resume_star(achievements: list[dict[str, Any]], target_role: str) -> str:
    benchmark = get_style_benchmark(target_role or "backend")
    parts = [f"# STAR 简历草稿（{benchmark['track']}）", ""]
    for item in achievements[:4]:
        parts.extend(
            [
                f"## {item['title']}",
                f"- Situation: {item.get('business_context') or item.get('background') or item.get('task', '待补背景')}",
                f"- Task: {short_scope(item)}",
                f"- Action: {summarize_actions(item)}",
                f"- Result: {choose_metric(item)}",
                f"- Resume bullet: {(item.get('resume_bullets') or [item.get('resume_bullet', '')])[0]}",
                "",
            ]
        )
    return "\n".join(parts)


def render_project_intro(achievements: list[dict[str, Any]]) -> str:
    parts = ["# 1分钟项目介绍", ""]
    if not achievements:
        return "\n".join(parts + ["- 暂无可用项目内容。"])
    parts.append(f"- {project_opening_line(achievements)}")
    spoken_lines: list[str] = []
    for item in achievements[:3]:
        sentence = intro_line_for_item(item)
        parts.append(f"- {sentence}")
        spoken_lines.append(sentence)
    style_issues = detect_generated_style_issues(spoken_lines)
    if style_issues:
        parts.extend(["", "## 表述提醒", "", "\n".join(f"- {issue}" for issue in style_issues)])
    return "\n".join(parts)


def render_interview_qa(achievements: list[dict[str, Any]]) -> str:
    parts = ["# 面试追问 Q&A", ""]
    for item in achievements[:3]:
        evidence_sources = ", ".join(e["source_ref"] for e in item.get("evidence", [])[:3])
        risky = "；".join(item.get("user_check_flags", [])) or "暂无特别风险提示"
        risky_examples = "；".join(item.get("user_check_evidence", [])[:2])
        parts.extend(
            [
                f"## {item['title']}",
                "- Q: 这个项目解决什么业务问题？",
                f"  A: {short_context(item)}",
                "- Q: 你具体负责了哪部分？",
                f"  A: {qa_answer_for_scope(item)}",
                "- Q: 结果怎么证明？",
                f"  A: 目前可回溯的证据来自 {evidence_sources or '待补证据'}，核心指标可以先讲 {choose_metric(item)}。",
                "- Q: 如果被问上下游流程？",
                f"  A: {qa_answer_for_flow(item)}",
                "- Q: 哪些表述需要你自己再确认一遍？",
                f"  A: 需要优先核对 {risky}。" + (f" 可疑表述示例：{risky_examples}" if risky_examples else ""),
                "",
            ]
        )
    return "\n".join(parts)


def render_risk_answers(achievements: list[dict[str, Any]]) -> str:
    parts = ["# 风险问法与稳妥回答", ""]
    for item in achievements[:3]:
        risk_notes = item.get("risk_notes", item.get("risk_flags", []))
        parts.extend(
            [
                f"## {item['title']}",
                f"- 高风险点: {'；'.join(risk_notes) or '低'}",
                f"- 稳妥说法: 这部分我目前能确认的是 {item.get('outcome') or item.get('task') or choose_metric(item)}，可回溯证据包括 {', '.join(e['source_ref'] for e in item.get('evidence', [])[:3]) or '待补'}。",
                f"- 需要复核: {'；'.join(item.get('user_check_flags', [])) or '暂无'}",
                f"- 下一步: {'；'.join(item.get('next_steps', ['补充证据']))}",
                "",
            ]
        )
    return "\n".join(parts)


def render_checklist(achievements: list[dict[str, Any]]) -> str:
    rows = []
    for item in achievements[:5]:
        rows.append(
            [
                item["title"],
                "ready" if item.get("resume_ready") else "needs-work",
                ", ".join(item.get("metrics", [])[:2]) or "待补量化",
                ", ".join(item.get("risk_notes", item.get("risk_flags", []))) or "低",
            ]
        )
    return "\n".join(["# 投递检查表", "", markdown_table(["Achievement", "Status", "Metrics", "Risks"], rows)])


def write_interview_pack(payload: dict[str, Any], out_dir: str | Path, target_role: str = "") -> dict[str, str]:
    out = ensure_dir(out_dir)
    achievements = select_achievements(payload)
    for item in achievements:
        if "resume_bullet" not in item and item.get("resume_bullets"):
            item["resume_bullet"] = item["resume_bullets"][0]
    pack = {"target_role": target_role, "achievements": achievements}
    return {
        "interview_pack_json": str(write_json(out / "interview_pack.json", pack)),
        "resume_star": str(write_text(out / "resume_star.md", render_resume_star(achievements, target_role))),
        "project_intro": str(write_text(out / "project_intro.md", render_project_intro(achievements))),
        "interview_qa": str(write_text(out / "interview_qa.md", render_interview_qa(achievements))),
        "risk_answers": str(write_text(out / "risk_answers.md", render_risk_answers(achievements))),
        "application_checklist": str(write_text(out / "application_checklist.md", render_checklist(achievements))),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create an interview pack from achievement audit or resume rank output.")
    parser.add_argument("--project-notes", required=True, help="Path to achievement audit JSON or resume rank JSON.")
    parser.add_argument("--target-role", default="", help="Target role or lane, used for style calibration.")
    parser.add_argument("--out", required=True, help="Output directory.")
    args = parser.parse_args(argv)
    payload = load_project_payload(args.project_notes)
    paths = write_interview_pack(payload, args.out, target_role=args.target_role)
    for label, path in paths.items():
        print(f"{label}: {path}")
    return 0


__all__ = ["select_achievements", "write_interview_pack"]


if __name__ == "__main__":
    raise SystemExit(main())
