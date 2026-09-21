"""Stdout/stderr formatting for CLI."""

from __future__ import annotations

import json
import sys
from typing import Any

import yaml


def emit_json(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, sort_keys=True, ensure_ascii=False) + "\n")


def emit_text(message: str) -> None:
    sys.stdout.write(message + "\n")


def emit_error_text(message: str) -> None:
    sys.stderr.write(message + "\n")


def format_text(payload: dict[str, Any]) -> str:
    """Render a result payload as plain text: status line, then the remaining fields as YAML."""
    body = {k: v for k, v in payload.items() if k not in ("ok", "command")}
    lines = []
    if "command" in payload or payload.get("ok") is False:
        status = "OK" if payload.get("ok", True) else "FAILED"
        lines.append(f"{status} {payload.get('command', '')}".rstrip())
    if body:
        lines.append(yaml.safe_dump(body, sort_keys=False, default_flow_style=False, allow_unicode=True).rstrip())
    return "\n".join(lines)


def emit_progress(message: str, verbose: bool) -> None:
    if verbose:
        sys.stderr.write(message + "\n")
