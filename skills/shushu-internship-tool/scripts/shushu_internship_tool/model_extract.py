from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .common import load_json, normalize_list


def _normalize_confidence(value: Any, default: float = 0.92) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, score))


def _normalize_highlight(raw: Any, project: dict[str, Any], index: int) -> dict[str, Any]:
    item = raw if isinstance(raw, dict) else {"summary": str(raw)}
    title = str(item.get("title") or item.get("module") or project.get("title") or f"highlight-{index}").strip()
    task = str(item.get("task") or item.get("summary") or item.get("scope") or title).strip()
    outcome = str(item.get("outcome") or item.get("result") or item.get("impact") or "").strip()
    business_context = str(
        item.get("business_context") or project.get("business_context") or project.get("background") or project.get("project_background") or ""
    ).strip()
    business_value = str(item.get("business_value") or item.get("value") or "").strip()
    actions = normalize_list(item.get("actions") or item.get("action"))
    metrics = normalize_list(item.get("metrics"))
    evidence = normalize_list(item.get("evidence") or item.get("evidence_refs"))
    user_check_flags = normalize_list(item.get("user_check_flags") or item.get("risk_flags"))
    return {
        "title": title,
        "project_title": str(project.get("title") or "").strip(),
        "task": task,
        "actions": actions,
        "outcome": outcome,
        "metrics": metrics,
        "business_context": business_context,
        "business_value": business_value,
        "keep_for_resume": bool(item.get("keep_for_resume", True)),
        "user_check_flags": user_check_flags,
        "evidence": evidence,
        "confidence": _normalize_confidence(item.get("confidence")),
    }


def normalize_structured_extract(payload: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if not isinstance(payload, dict):
        return normalized

    projects = payload.get("projects")
    if isinstance(projects, list):
        for project_index, project_raw in enumerate(projects, start=1):
            project = project_raw if isinstance(project_raw, dict) else {"title": f"project-{project_index}"}
            highlights = (
                project.get("highlights")
                or project.get("contributions")
                or project.get("achievements")
                or project.get("bullets")
                or []
            )
            if isinstance(highlights, list) and highlights:
                for item_index, item in enumerate(highlights, start=1):
                    normalized.append(_normalize_highlight(item, project, item_index))
            elif project.get("title"):
                normalized.append(_normalize_highlight(project, project, 1))

    achievements = payload.get("achievements")
    if isinstance(achievements, list):
        project = {
            "title": str(payload.get("project_title") or payload.get("title") or "").strip(),
            "business_context": str(payload.get("business_context") or payload.get("background") or "").strip(),
        }
        for item_index, item in enumerate(achievements, start=1):
            normalized.append(_normalize_highlight(item, project, item_index))

    return [item for item in normalized if item["title"]]


def load_structured_extract(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    path = str(bundle.get("structured_extract_path") or "").strip()
    inline = bundle.get("structured_extract")
    if path:
        payload = load_json(Path(path))
    elif inline is not None:
        payload = inline if isinstance(inline, dict) else json.loads(str(inline))
    else:
        return []
    return normalize_structured_extract(payload)


__all__ = ["load_structured_extract", "normalize_structured_extract"]
