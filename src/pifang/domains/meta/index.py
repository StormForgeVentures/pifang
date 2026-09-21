"""Ingest folder indexing and manifest validation."""

from __future__ import annotations

import json
from pathlib import Path

from pifang.errors import ValidationError


def build_index(root: Path, output: Path | None = None) -> dict:
    if not root.is_dir():
        raise ValidationError(f"Not a directory: {root}", "NOT_A_DIRECTORY")

    entries: list[dict] = []
    for md in sorted(root.rglob("*.md")):
        if md.name.endswith("-chunks.jsonl") or md.name == "manifest.json":
            continue
        stem = md.stem
        images_dir = md.parent / f"{stem}_images"
        entry = {
            "markdown": str(md.resolve()),
            "stem": stem,
            "images_dir": str(images_dir.resolve()) if images_dir.is_dir() else None,
            "image_count": len(list(images_dir.glob("*"))) if images_dir.is_dir() else 0,
            "json": str(j) if (j := md.with_suffix(".json")).exists() else None,
        }
        entries.append(entry)

    out = output or root / "index.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for e in entries:
            fh.write(json.dumps(e, sort_keys=True) + "\n")

    return {"root": str(root.resolve()), "count": len(entries), "index": str(out.resolve()), "entries": entries}


def validate_ingest_manifest(manifest_path: Path, root: Path | None = None) -> dict:
    if not manifest_path.exists():
        raise ValidationError(f"Manifest not found: {manifest_path}", "MANIFEST_NOT_FOUND")

    missing: list[dict] = []
    ok_count = 0
    total = 0
    for line_no, line in enumerate(manifest_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        total += 1
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValidationError(
                f"Invalid JSON on line {line_no} of {manifest_path}: {exc.msg}",
                "INVALID_MANIFEST_LINE",
                {"hint": f"Fix or remove line {line_no} in the manifest JSONL"},
            ) from exc
        if not isinstance(row, dict):
            raise ValidationError(
                f"Manifest line {line_no} must be a JSON object",
                "INVALID_MANIFEST_LINE",
                {"hint": f"Fix line {line_no} in the manifest JSONL"},
            )
        md = row.get("markdown")
        if md and not Path(md).exists():
            missing.append({"field": "markdown", "path": md, "input": row.get("input")})
            continue
        images = row.get("images_dir")
        if images and not Path(images).exists():
            missing.append({"field": "images_dir", "path": images, "input": row.get("input")})
            continue
        ok_count += 1

    if root:
        listed: set[str] = set()
        for line_no, line in enumerate(manifest_path.read_text().splitlines(), start=1):
            if not line.strip():
                continue
            try:
                listed.add(json.loads(line).get("markdown") or "")
            except json.JSONDecodeError as exc:
                raise ValidationError(
                    f"Invalid JSON on line {line_no} of {manifest_path}: {exc.msg}",
                    "INVALID_MANIFEST_LINE",
                    {"hint": f"Fix or remove line {line_no} in the manifest JSONL"},
                ) from exc
        for md in root.rglob("*.md"):
            if md.name in ("manifest.json",):
                continue
            rel = str(md.resolve())
            if rel not in listed:
                missing.append({"field": "unlisted_markdown", "path": rel})

    return {
        "manifest": str(manifest_path.resolve()),
        "total": total,
        "ok": ok_count,
        "missing": missing,
        "valid": len(missing) == 0,
    }
