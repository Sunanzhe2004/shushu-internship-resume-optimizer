from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .common import ensure_dir, load_json, markdown_table, normalize_list, write_json, write_text
from .resume_style_bench import detect_generated_style_issues, get_style_benchmark


def load_project_payload(path: str | Path) -> dict[str, Any]:
    payload = load_json(path)
    if isinstance(payload, dict):
        return payload
    raise ValueError("project payload must be a JSON object")


def select_achievements(payload: dict[str, Any]) -> list[dict[str, Any]]:
    achievements = payload.get("achievements", [])
    return sorted(
        (dict(item) for item in achievements),
        key=lambda item: (-int(item.get("score", 0)), len(item.get("risk_notes", item.get("risk_flags", []))), item.get("title", "")),
    )[:5]


def compress_sentence(text: str, fallback: str) -> str:
    clean = " ".join(str(text).split()).strip()
    return clean or fallback


def first_metric(item: dict[str, Any]) -> str:
    metrics = normalize_list(item.get("metrics"))
    return metrics[0] if metrics else "阶段性工程结果"


def summarize_actions(item: dict[str, Any], limit: int = 2) -> str:
    actions = [compress_sentence(action, "") for action in normalize_list(item.get("actions"))[:limit]]
    actions = [action for action in actions if action]
    if not actions:
        return "推进关键模块落地"
    return "；".join(actions)


def intro_opening(index: int) -> str:
    options = [
        "我负责的第一块是",
        "第二块更偏",
        "另外一块是",
    ]
    return options[min(index, len(options) - 1)]


def render_resume_star(achievements: list[dict[str, Any]], target_role: str) -> str:
    benchmark = get_style_benchmark(target_role or "backend")
    parts = [f"# STAR 简历草稿（{benchmark['track']}）", ""]
    for item in achievements[:4]:
        parts.extend(
            [
                f"## {item['title']}",
                f"- Situation: {item.get('business_context') or item.get('background') or item.get('task', '待补背景')}",
                f"- Task: {item.get('task') or '负责关键模块推进'}",
                f"- Action: {'；'.join(item.get('actions', [])[:2]) or '待补具体动作'}",
                f"- Result: {item.get('outcome') or '待补结果'}",
                f"- Resume bullet: {item.get('resume_bullet') or item.get('resume_bullets', [''])[0]}",
                "",
            ]
        )
    return "\n".join(parts)


def render_project_intro(achievements: list[dict[str, Any]]) -> str:
    parts = ["# 1分钟项目介绍", ""]
    if not achievements:
        return "\n".join(parts + ["- 暂无可用项目内容。"])

    shared_background = compress_sentence(
        achievements[0].get("business_context") or achievements[0].get("background"),
        "待补业务背景",
    )
    parts.append(f"- 这个项目整体是在做：{shared_background}。我主要负责其中几块和 eval / 自动化打标相关的工作。")

    spoken_lines: list[str] = []
    for index, item in enumerate(achievements[:3]):
        actions = summarize_actions(item)
        result = first_metric(item)
        sentence = f"{intro_opening(index)}{item['title']}，我这边主要做的是{actions}。"
        if item.get("metrics"):
            sentence += f" 当前能确认的结果可以先用{result}来说明。"
        else:
            sentence += " 这部分还在迭代，我会优先补充更稳定的评估指标或阶段性结果。"
        parts.append(f"- {sentence}")
        spoken_lines.append(sentence)

    style_issues = detect_generated_style_issues(spoken_lines)
    if style_issues:
        parts.extend(
            [
                "",
                "## 表述提醒",
                "",
                "\n".join(f"- {issue}" for issue in style_issues),
            ]
        )
    return "\n".join(parts)


def render_interview_qa(achievements: list[dict[str, Any]]) -> str:
    parts = ["# 面试追问 Q&A", ""]
    for item in achievements[:3]:
        evidence_sources = ", ".join(e["source_ref"] for e in item.get("evidence", [])[:3])
        parts.extend(
            [
                f"## {item['title']}",
                "- Q: 这个项目解决什么业务问题？",
                f"  A: {item.get('business_context') or item.get('background') or '待补业务背景'}",
                "- Q: 你具体负责了哪部分？",
                f"  A: {'；'.join(item.get('actions', [])[:2]) or item.get('task', '待补职责范围')}",
                "- Q: 结果怎么证明？",
                f"  A: 目前可回溯的证据来自 {evidence_sources or '待补证据'}，核心指标是 {first_metric(item)}。",
                "- Q: 如果被问上下游流程？",
                f"  A: 可以从 {item.get('business_context') or '业务文档知识层'} 切入，说明目标、流程和协作对象。",
                "- Q: 哪些表述需要你自己再确认一遍？",
                f"  A: 需要优先核对 {'；'.join(item.get('user_check_flags', [])) or '暂无特别风险提示'}。"
                + (
                    f" 可疑表述示例：{'；'.join(item.get('user_check_evidence', [])[:2])}"
                    if item.get("user_check_evidence")
                    else ""
                ),
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
                f"- 稳妥说法: 这部分我目前能确认的是 {item.get('outcome') or item.get('task', '阶段性工作结果')}，可回溯证据包括 {', '.join(e['source_ref'] for e in item.get('evidence', [])[:3]) or '待补'}。",
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
    pack = {
        "target_role": target_role,
        "achievements": achievements,
    }
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
