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


def load_project_payload(path: str | Path) -> dict[str, Any]:
    payload = load_json(path)
    if isinstance(payload, dict):
        return payload
    raise ValueError("project payload must be a JSON object")


def select_achievements(payload: dict[str, Any]) -> list[dict[str, Any]]:
    achievements = payload.get("achievements", [])
    order = {
        "自动评估任务完成情况优化": 0,
        "错误标签自动化判别": 1,
        "错误标签自动化归因": 1,
        "异步评估服务工程化": 2,
    }
    return sorted(
        (dict(item) for item in achievements),
        key=lambda item: (
            order.get(item.get("title", ""), 9),
            -int(item.get("score", 0)),
            len(item.get("risk_notes", item.get("risk_flags", []))),
            item.get("title", ""),
        ),
    )[:5]


def compress_sentence(text: str, fallback: str) -> str:
    clean = " ".join(str(text).split()).strip()
    return clean or fallback


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
    return any(value.startswith(prefix) for prefix in NOISE_PREFIXES)


def first_metric(item: dict[str, Any]) -> str:
    metrics = normalize_list(item.get("metrics"))
    return metrics[0] if metrics else "阶段性工程结果"


def summarize_actions(item: dict[str, Any], limit: int = 2) -> str:
    seeded = [sanitize_text(line) for line in normalize_list(item.get("core_actions")) if sanitize_text(line)]
    if seeded:
        return "；".join(seeded[:limit])
    cleaned: list[str] = []
    title = item.get("title", "")
    for raw in normalize_list(item.get("actions")):
        value = sanitize_text(raw)
        if not value or is_noise_line(value):
            continue
        if title and title in value:
            value = value.replace(title, "", 1).strip("，。！？； ")
        if value not in cleaned:
            cleaned.append(value)
        if len(cleaned) >= limit:
            break
    if not cleaned and item.get("task"):
        fallback = sanitize_text(item["task"])
        if fallback and not is_noise_line(fallback):
            cleaned.append(fallback)
    if not cleaned:
        return "推进关键模块落地"
    return "；".join(cleaned[:limit])


def intro_opening(index: int) -> str:
    options = [
        "第一块是",
        "第二块是",
        "另外一块是",
    ]
    return options[min(index, len(options) - 1)]


def short_context(item: dict[str, Any]) -> str:
    text = item.get("business_context") or item.get("background") or "待补业务背景"
    clean = sanitize_text(text)
    return clean[:80].rstrip("，。！？； ") if len(clean) > 80 else clean


def short_scope(item: dict[str, Any]) -> str:
    text = item.get("one_line_scope") or item.get("task") or item.get("title") or "待补职责"
    clean = sanitize_text(text)
    return clean[:48].rstrip("，。！？； ") if len(clean) > 48 else clean


def short_result(item: dict[str, Any]) -> str:
    if item.get("best_metric"):
        text = item["best_metric"]
    else:
        text = item.get("core_result") or first_metric(item)
    clean = sanitize_text(text)
    if "通过 Compass API 查询 `result_code`" in clean:
        return "通过结果码前置拦截无效样本"
    if "asyncio.Semaphore" in clean:
        return "补齐并发控制与服务化运行能力"
    if "接入 eval 分析链路" in clean:
        return "已形成可接入后续分析链路的归因框架"
    return clean[:48].rstrip("，。！？； ") if len(clean) > 48 else clean


def short_business_value(item: dict[str, Any]) -> str:
    text = item.get("business_value") or short_context(item)
    clean = sanitize_text(text)
    return clean[:60].rstrip("，。！？； ") if len(clean) > 60 else clean


def title_track(item: dict[str, Any]) -> str:
    title = item.get("title", "")
    if "异步评估服务" in title:
        return "service"
    if "自动评估任务完成情况优化" in title:
        return "eval"
    if "错误标签自动化判别" in title:
        return "label"
    return "general"


def intro_line_for_item(item: dict[str, Any], index: int) -> str:
    track = title_track(item)
    metric = short_result(item)
    if track == "service":
        return "第三块是把评估流程服务化，我主要做了 FastAPI + asyncio 的异步评估服务，把采集端和评估端拆开，并补了并发控制、任务恢复和文件监听触发。"
    if track == "eval":
        return f"第一块是自动评估任务完成情况优化，我主要在做任务是否完成的自动判定，核心是把无效数据过滤、LLM 评估和后置校验拆开做，先尽量把环境异常和真实失败区分开。现在比较能落地地讲的是 {metric}。"
    if track == "label":
        return "第二块是失败 case 的错误标签自动化归因，我在搭一级、二级标签体系和归因 workflow，目标是把失败原因结构化，方便后面做分析和策略迭代。"
    return f"{intro_opening(index)}{item['title']}，我主要负责其中几块，这一块主要在做 {short_scope(item)}。"


def qa_answer_for_scope(item: dict[str, Any]) -> str:
    track = title_track(item)
    metric = short_result(item)
    if track == "service":
        return "我主要负责把评估 workflow 做成异步服务，包括 HTTP 提交、文件监听触发、并发控制和任务持久化，目标是让采集端和评估端可以解耦运行，而不是靠人工串流程。"
    if track == "eval":
        return f"我主要负责任务完成情况自动评估这条线，重点是优化判定逻辑本身，并把无效数据先筛出去，避免它干扰任务成功率判断。当前比较能确认的结果可以先讲 {metric}。"
    if track == "label":
        return "我主要在推进失败 case 的一级、二级标签归因 workflow，这部分现在还在迭代，当前更偏流程和标签框架搭建。"
    return sanitize_text(item.get("interview_explain", "")) or ("这一块我主要在做 " + short_scope(item) + "。")


def qa_answer_for_flow(item: dict[str, Any]) -> str:
    track = title_track(item)
    if track == "service":
        return "可以先讲采集端生成轨迹数据，评估服务异步消费并输出结果，再补充任务恢复、文件监听和跨机器协作方式。"
    if track == "eval":
        return "可以先讲 Agent 轨迹进来之后，先做前置规则拦截，再做 LLM 核心评估，最后补规则和视觉兜底，目标是把任务失败和环境异常区分开。"
    if track == "label":
        return "可以先讲任务失败 case 先进入评估链路，再进入一级、二级标签归因流程，最后把标签结果回流给后续分析和策略迭代。"
    return f"可以先从 {short_context(item)} 切入，再补充这项工作的业务价值主要在于 {short_business_value(item)}。"


def render_resume_star(achievements: list[dict[str, Any]], target_role: str) -> str:
    benchmark = get_style_benchmark(target_role or "backend")
    parts = [f"# STAR 简历草稿（{benchmark['track']}）", ""]
    for item in achievements[:4]:
        track = title_track(item)
        if track == "eval":
            task = "负责任务完成情况自动评估优化，并减少无效数据对判定结果的干扰"
            action = "设计 P-E-R 分层链路，把前置规则拦截、LLM 判定和后置规则 / 视觉兜底拆开实现"
            result = short_result(item)
        elif track == "label":
            task = "负责失败 case 的自动化归因方案搭建"
            action = "设计一级、二级标签体系与归因 workflow，给后续分析链路沉淀结构化标签"
            result = short_result(item)
        elif track == "service":
            task = "负责评估流程服务化，支撑采集与评估解耦"
            action = "基于 FastAPI + asyncio 搭建异步评估服务，并补充并发控制、任务恢复和文件监听触发"
            result = short_result(item)
        else:
            task = item.get("task") or "负责关键模块推进"
            action = summarize_actions(item)
            result = item.get("outcome") or first_metric(item)
        parts.extend(
            [
                f"## {item['title']}",
                f"- Situation: {item.get('business_context') or item.get('background') or item.get('task', '待补背景')}",
                f"- Task: {task}",
                f"- Action: {action}",
                f"- Result: {result}",
                f"- Resume bullet: {(item.get('resume_bullets') or [item.get('resume_bullet', '')])[0]}",
                "",
            ]
        )
    return "\n".join(parts)


def render_project_intro(achievements: list[dict[str, Any]]) -> str:
    parts = ["# 1分钟项目介绍", ""]
    if not achievements:
        return "\n".join(parts + ["- 暂无可用项目内容。"])

    parts.append("- 这个项目整体是在做手机 GUI Agent 的自动评估，用自动化方式替代人工逐条标注，核心是判断任务有没有完成，同时把无效数据过滤出去。")

    spoken_lines: list[str] = []
    for index, item in enumerate(achievements[:3]):
        sentence = intro_line_for_item(item, index)
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
                f"  A: 目前可回溯的证据来自 {evidence_sources or '待补证据'}，核心指标可以先讲 {short_result(item)}。",
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
                f"- 稳妥说法: 这部分我目前能确认的是 {item.get('outcome') or item.get('task') or first_metric(item)}，可回溯证据包括 {', '.join(e['source_ref'] for e in item.get('evidence', [])[:3]) or '待补'}。",
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


if __name__ == "__main__":
    raise SystemExit(main())
