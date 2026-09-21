"""Markdown chunking for RAG."""

from __future__ import annotations

import json
import re
from pathlib import Path

from pifang.errors import ValidationError


def chunk_markdown_file(
    path: Path,
    output_dir: Path,
    *,
    mode: str = "heading",
    max_chars: int = 4000,
) -> dict:
    if not path.exists():
        raise ValidationError(f"File not found: {path}", "FILE_NOT_FOUND")
    text = path.read_text(encoding="utf-8")
    chunks = chunk_markdown(text, mode=mode, max_chars=max_chars)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = path.stem
    outputs: list[str] = []
    manifest_lines: list[str] = []
    for i, chunk in enumerate(chunks):
        out = output_dir / f"{stem}-chunk-{i + 1:03d}.md"
        out.write_text(chunk["text"], encoding="utf-8")
        outputs.append(str(out.resolve()))
        manifest_lines.append(json.dumps({"index": i + 1, "path": str(out), "title": chunk.get("title"), "chars": len(chunk["text"])}, sort_keys=True))

    manifest = output_dir / f"{stem}-chunks.jsonl"
    manifest.write_text("\n".join(manifest_lines) + ("\n" if manifest_lines else ""), encoding="utf-8")
    return {
        "input": str(path.resolve()),
        "output_dir": str(output_dir.resolve()),
        "chunk_count": len(chunks),
        "manifest": str(manifest.resolve()),
        "outputs": outputs,
    }


def chunk_markdown(text: str, *, mode: str = "heading", max_chars: int = 4000) -> list[dict]:
    if mode == "heading":
        return _chunk_by_heading(text)
    if mode == "size":
        return _chunk_by_size(text, max_chars)
    raise ValidationError(f"Unknown chunk mode: {mode}", "UNKNOWN_CHUNK_MODE", {"hint": "heading or size"})


def _chunk_by_heading(text: str) -> list[dict]:
    pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
    matches = list(pattern.finditer(text))
    if not matches:
        return [{"title": None, "text": text.strip()}] if text.strip() else []

    chunks: list[dict] = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end].strip()
        title = match.group(2).strip()
        if block:
            chunks.append({"title": title, "text": block})
    return chunks


def _chunk_by_size(text: str, max_chars: int) -> list[dict]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[dict] = []
    current: list[str] = []
    size = 0
    for para in paragraphs:
        if size + len(para) + 2 > max_chars and current:
            chunks.append({"title": None, "text": "\n\n".join(current)})
            current = []
            size = 0
        current.append(para)
        size += len(para) + 2
    if current:
        chunks.append({"title": None, "text": "\n\n".join(current)})
    return chunks
