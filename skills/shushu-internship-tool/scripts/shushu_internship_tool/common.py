from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable


TEXT_SUFFIXES = {
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".cfg",
    ".ini",
    ".log",
    ".csv",
}


def ensure_dir(path: str | Path) -> Path:
    out = Path(path)
    out.mkdir(parents=True, exist_ok=True)
    return out


def write_json(path: str | Path, data: Any) -> Path:
    target = Path(path)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def write_text(path: str | Path, text: str) -> Path:
    target = Path(path)
    target.write_text(text.rstrip() + "\n", encoding="utf-8")
    return target


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple | set):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        if not value.strip():
            return []
        parts = re.split(r"[,;\n]", value)
        return [part.strip() for part in parts if part.strip()]
    return [str(value).strip()]


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def markdown_table(headers: list[str], rows: Iterable[Iterable[Any]]) -> str:
    def cell(value: Any) -> str:
        text = "" if value is None else str(value)
        return text.replace("|", "\\|").replace("\n", "<br>")

    header = "| " + " | ".join(cell(item) for item in headers) + " |"
    divider = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(cell(item) for item in row) + " |" for row in rows]
    return "\n".join([header, divider, *body])


def read_text_sample(path: Path, max_chars: int = 6000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...[truncated]"


def is_probably_text(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES or path.name.lower() in {
        "dockerfile",
        "makefile",
        "license",
        "notice",
    }
