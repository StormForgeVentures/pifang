"""JSONL manifest writer."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ManifestEntry:
    input: str
    output: str | None
    command: str
    ok: bool
    duration_ms: int
    error: dict[str, Any] | None = None

    def to_line(self) -> str:
        return json.dumps(
            {
                "input": self.input,
                "output": self.output,
                "command": self.command,
                "ok": self.ok,
                "duration_ms": self.duration_ms,
                "error": self.error,
            },
            sort_keys=True,
        )


class ManifestWriter:
    def __init__(self, path: Path | None) -> None:
        self.path = path
        self.entries: list[ManifestEntry] = []
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")

    def append(self, entry: ManifestEntry) -> None:
        self.entries.append(entry)
        if self.path:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(entry.to_line() + "\n")
