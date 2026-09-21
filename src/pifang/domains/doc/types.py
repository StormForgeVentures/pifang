"""Document ingestion types."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class IngestResult:
    ok: bool
    input_path: Path
    markdown_path: Path | None
    images_dir: Path | None
    json_path: Path | None
    engine: str
    duration_ms: int
    image_count: int = 0
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "input": str(self.input_path.resolve()),
            "markdown": str(self.markdown_path.resolve()) if self.markdown_path else None,
            "images_dir": str(self.images_dir.resolve()) if self.images_dir else None,
            "json": str(self.json_path.resolve()) if self.json_path else None,
            "engine": self.engine,
            "duration_ms": self.duration_ms,
            "image_count": self.image_count,
            "error": self.error,
        }


@dataclass
class IngestBatchResult:
    ok: bool
    command: str
    output_dir: Path
    results: list[IngestResult] = field(default_factory=list)
    manifest_path: Path | None = None
    duration_ms: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        succeeded = sum(1 for r in self.results if r.ok)
        failed = len(self.results) - succeeded
        payload = {
            "ok": failed == 0,
            "command": self.command,
            "output_dir": str(self.output_dir.resolve()),
            "total": len(self.results),
            "succeeded": succeeded,
            "failed": failed,
            "duration_ms": self.duration_ms,
            "manifest": str(self.manifest_path) if self.manifest_path else None,
            "results": [r.to_dict() for r in self.results],
        }
        if self.warnings:
            payload["warnings"] = list(self.warnings)
        return payload
