"""YAML frontmatter for markdown files."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from pifang.errors import ValidationError


def add_frontmatter(path: Path, fields: dict, *, in_place: bool = True, output: Path | None = None) -> dict:
    if not path.exists():
        raise ValidationError(f"File not found: {path}", "FILE_NOT_FOUND")
    body = path.read_text(encoding="utf-8")
    if body.startswith("---"):
        raise ValidationError("File already has frontmatter", "FRONTMATTER_EXISTS")

    fm = yaml.safe_dump(fields, sort_keys=True, allow_unicode=True).strip()
    new_text = f"---\n{fm}\n---\n\n{body}"
    target = path if in_place else (output or path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(new_text, encoding="utf-8")
    return {"path": str(target.resolve()), "fields": fields}


def frontmatter_from_json(path: Path, json_fields: str) -> dict:
    fields = json.loads(json_fields)
    if not isinstance(fields, dict):
        raise ValidationError("JSON fields must be an object", "INVALID_FIELDS")
    return add_frontmatter(path, fields)
