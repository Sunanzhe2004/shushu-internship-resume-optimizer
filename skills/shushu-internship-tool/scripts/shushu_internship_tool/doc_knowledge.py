from __future__ import annotations

import argparse
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .common import ensure_dir, normalize_list, read_text_sample, write_json, write_text


TOKEN_RE = re.compile(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9_+#.-]{1,}")


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for raw in TOKEN_RE.findall(text):
        token = raw.lower()
        tokens.append(token)
        if re.fullmatch(r"[\u4e00-\u9fff]{3,}", raw):
            tokens.extend(raw[index : index + 2] for index in range(len(raw) - 1))
    return tokens


def chunk_text(text: str, chunk_size: int = 420, overlap: int = 80) -> list[str]:
    if len(text) <= chunk_size:
        return [text.strip()] if text.strip() else []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        chunk = text[start : start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        if start + chunk_size >= len(text):
            break
        start += max(1, chunk_size - overlap)
    return chunks


def infer_mode(documents: list[dict[str, Any]], requested_mode: str | None = None) -> str:
    if requested_mode:
        return requested_mode
    total_chars = sum(len(item.get("text", "")) for item in documents)
    if total_chars < 1200 and len(documents) <= 2:
        return "direct"
    return "basic_rag"


def extract_terms(text: str, top_k: int = 12) -> list[str]:
    counts = Counter(tokenize(text))
    stop = {"the", "and", "for", "with", "todo", "this", "that", "from", "into", "项目", "业务", "功能"}
    terms = [token for token, _ in counts.most_common() if token not in stop]
    return terms[:top_k]


def load_documents(paths: list[str]) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            for file in sorted(path.rglob("*")):
                if file.is_file():
                    text = read_text_sample(file, max_chars=40000)
                    if text.strip():
                        documents.append({"path": str(file), "title": file.name, "text": text})
        elif path.exists():
            text = read_text_sample(path, max_chars=40000)
            if text.strip():
                documents.append({"path": str(path), "title": path.name, "text": text})
    return documents


def build_knowledge_base(documents: list[dict[str, Any]], mode: str | None = None) -> dict[str, Any]:
    resolved_mode = infer_mode(documents, requested_mode=mode)
    chunks: list[dict[str, Any]] = []
    for doc in documents:
        for index, chunk in enumerate(chunk_text(doc["text"])):
            token_counts = Counter(tokenize(chunk))
            norm = math.sqrt(sum(value * value for value in token_counts.values())) or 1.0
            chunks.append(
                {
                    "chunk_id": f"{Path(doc['title']).stem}-{index}",
                    "source": doc["title"],
                    "source_path": doc["path"],
                    "text": chunk,
                    "terms": extract_terms(chunk),
                    "token_counts": dict(token_counts),
                    "norm": norm,
                }
            )
    return {
        "mode": resolved_mode,
        "documents": [{"title": doc["title"], "path": doc["path"], "terms": extract_terms(doc["text"])} for doc in documents],
        "chunks": chunks,
    }


def query_knowledge(base: dict[str, Any], question: str, top_k: int = 3) -> list[dict[str, Any]]:
    q_counts = Counter(tokenize(question))
    if not q_counts:
        return []
    q_norm = math.sqrt(sum(value * value for value in q_counts.values())) or 1.0
    ranked: list[dict[str, Any]] = []
    for chunk in base.get("chunks", []):
        overlap = sum(q_counts[token] * chunk["token_counts"].get(token, 0) for token in q_counts)
        if overlap <= 0:
            continue
        score = overlap / (q_norm * float(chunk["norm"]))
        ranked.append(
            {
                "chunk_id": chunk["chunk_id"],
                "source": chunk["source"],
                "score": round(score, 4),
                "text": chunk["text"],
                "terms": chunk["terms"],
            }
        )
    ranked.sort(key=lambda item: (-item["score"], item["source"], item["chunk_id"]))
    return ranked[:top_k]


def render_markdown(base: dict[str, Any], queries: list[str], query_results: dict[str, list[dict[str, Any]]]) -> str:
    parts = [
        "# 文档知识层概览",
        "",
        f"- mode: `{base['mode']}`",
        f"- documents: {len(base.get('documents', []))}",
        f"- chunks: {len(base.get('chunks', []))}",
        "",
        "## 文档摘要",
    ]
    for doc in base.get("documents", []):
        parts.append(f"- `{doc['title']}`: {', '.join(doc['terms'][:8])}")
    if queries:
        parts.extend(["", "## 检索结果"])
        for query in queries:
            parts.append("")
            parts.append(f"### {query}")
            hits = query_results.get(query, [])
            if not hits:
                parts.append("- no hits")
                continue
            for hit in hits:
                parts.append(f"- `{hit['source']}` score={hit['score']}: {hit['text'][:180]}")
    return "\n".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or query a lightweight business document knowledge layer.")
    parser.add_argument("--docs", nargs="+", required=True, help="One or more business document files or directories.")
    parser.add_argument("--mode", choices=["direct", "basic_rag", "knowledge_base"], default=None)
    parser.add_argument("--query", action="append", default=[], help="Question to query against the knowledge layer.")
    parser.add_argument("--out", required=True, help="Output directory.")
    args = parser.parse_args(argv)

    documents = load_documents(normalize_list(args.docs))
    base = build_knowledge_base(documents, mode=args.mode)
    query_results = {query: query_knowledge(base, query) for query in args.query}
    out = ensure_dir(args.out)
    write_json(out / "doc_knowledge.json", {"knowledge": base, "queries": query_results})
    write_text(out / "doc_knowledge.md", render_markdown(base, args.query, query_results))
    return 0


__all__ = [
    "build_knowledge_base",
    "chunk_text",
    "extract_terms",
    "infer_mode",
    "load_documents",
    "query_knowledge",
]
