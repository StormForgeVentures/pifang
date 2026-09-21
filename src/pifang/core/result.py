"""Operation result types."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pifang.errors import PifangError


@dataclass
class OpResult:
    ok: bool
    command: str
    input_path: Path
    output_path: Path | None
    duration_ms: int
    width: int | None = None
    height: int | None = None
    format: str | None = None
    bytes: int | None = None
    dry_run: bool = False
    skipped: bool = False
    error: PifangError | None = None

    def to_dict(self) -> dict:
        payload: dict = {
            "ok": self.ok,
            "command": self.command,
            "input": str(self.input_path.resolve()),
            "duration_ms": self.duration_ms,
        }
        if self.output_path:
            payload["output"] = str(self.output_path.resolve())
        if self.dry_run:
            payload["dry_run"] = True
        if self.skipped:
            payload["skipped"] = True
        if self.ok and not self.dry_run:
            payload["result"] = {
                k: v
                for k, v in {
                    "width": self.width,
                    "height": self.height,
                    "format": self.format,
                    "bytes": self.bytes,
                }.items()
                if v is not None
            }
        if self.error:
            payload.update(self.error.to_dict())
            payload["ok"] = False
        return payload
