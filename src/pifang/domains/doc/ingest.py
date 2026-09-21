"""PDF ingest orchestration."""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from pifang.domains.doc.engines import _rewrite_image_refs, default_engine, get_engine
from pifang.domains.doc.types import IngestBatchResult, IngestResult
from pifang.errors import PifangError, ValidationError


def _sanitize_stem(stem: str) -> str:
    """Normalize PDF stem for output paths (engines may rewrite whitespace to `_`)."""
    return re.sub(r"\s+", "_", stem)


def _collect_pdfs(path: Path, recursive: bool) -> list[Path]:
    if path.is_file():
        if path.suffix.lower() != ".pdf":
            raise ValidationError(f"Not a PDF: {path}", "NOT_PDF")
        return [path]
    if not path.is_dir():
        raise ValidationError(f"Path not found: {path}", "PATH_NOT_FOUND")
    globber = path.rglob("*.pdf") if recursive else path.glob("*.pdf")
    files = sorted(globber)
    if not files:
        raise ValidationError("No PDF files found", "NO_PDFS")
    return files


def ingest_one(
    pdf_path: Path,
    output_dir: Path,
    *,
    engine_name: str | None = None,
    dry_run: bool = False,
    write_engine_json: bool = True,
) -> IngestResult:
    started = time.perf_counter()
    engine = get_engine(engine_name) if engine_name else default_engine()
    stem = _sanitize_stem(pdf_path.stem)
    output_dir.mkdir(parents=True, exist_ok=True)

    if dry_run:
        elapsed = int((time.perf_counter() - started) * 1000)
        return IngestResult(
            ok=True,
            input_path=pdf_path,
            markdown_path=output_dir / f"{stem}.md",
            images_dir=output_dir / f"{stem}_images",
            json_path=None,
            engine=engine.name,
            duration_ms=elapsed,
        )

    try:
        md_path, images_dir, json_path, image_count = engine.ingest(
            pdf_path,
            output_dir,
            stem,
            write_json=write_engine_json,
        )
        if images_dir:
            _rewrite_image_refs(md_path, images_dir, stem)
        elapsed = int((time.perf_counter() - started) * 1000)
        return IngestResult(
            ok=True,
            input_path=pdf_path,
            markdown_path=md_path,
            images_dir=images_dir,
            json_path=json_path,
            engine=engine.name,
            duration_ms=elapsed,
            image_count=image_count,
        )
    except PifangError:
        raise
    except Exception as exc:
        elapsed = int((time.perf_counter() - started) * 1000)
        return IngestResult(
            ok=False,
            input_path=pdf_path,
            markdown_path=None,
            images_dir=None,
            json_path=None,
            engine=engine.name,
            duration_ms=elapsed,
            error=str(exc),
        )


def _load_manifest_entries(manifest_path: Path) -> tuple[dict[str, dict], list[str]]:
    """Load prior ingest.jsonl keyed by resolved input path.

    Corrupt lines are skipped with a warning (stderr + returned list) that
    includes the 1-based line number.
    """
    entries: dict[str, dict] = {}
    warnings: list[str] = []
    if not manifest_path.is_file():
        return entries, warnings
    for lineno, raw in enumerate(manifest_path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            msg = (
                f"Skipping corrupt JSONL line {lineno} in {manifest_path.name}: "
                f"{exc.msg} (col {exc.colno})"
            )
            warnings.append(msg)
            print(msg, file=sys.stderr)
            continue
        key = row.get("input")
        if isinstance(key, str) and key:
            entries[key] = row
    return entries, warnings


def _write_manifest(manifest_path: Path, entries: dict[str, dict]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as fh:
        for key in sorted(entries):
            fh.write(json.dumps(entries[key], sort_keys=True) + "\n")


def ingest_batch(
    path: Path,
    output_dir: Path,
    *,
    engine_name: str | None = None,
    recursive: bool = False,
    manifest_path: Path | None = None,
    dry_run: bool = False,
    write_manifest: bool = True,
    write_engine_json: bool = True,
    command: str = "doc.ingest",
) -> IngestBatchResult:
    started = time.perf_counter()
    pdfs = _collect_pdfs(path, recursive)
    results = [
        ingest_one(
            p,
            output_dir,
            engine_name=engine_name,
            dry_run=dry_run,
            write_engine_json=write_engine_json,
        )
        for p in pdfs
    ]

    written_manifest: Path | None = None
    warnings: list[str] = []
    if write_manifest:
        if manifest_path is None:
            manifest_path = output_dir / "ingest.jsonl"
        if not dry_run:
            merged, warnings = _load_manifest_entries(manifest_path)
            for r in results:
                row = r.to_dict()
                merged[row["input"]] = row
            _write_manifest(manifest_path, merged)
            written_manifest = manifest_path

    elapsed = int((time.perf_counter() - started) * 1000)
    return IngestBatchResult(
        ok=all(r.ok for r in results),
        command=command,
        output_dir=output_dir,
        results=results,
        manifest_path=written_manifest,
        duration_ms=elapsed,
        warnings=warnings,
    )


def convert_batch(
    path: Path,
    output_dir: Path,
    *,
    engine_name: str | None = None,
    recursive: bool = False,
    dry_run: bool = False,
) -> IngestBatchResult:
    """PDF → markdown + images only (no ingest.jsonl, no engine JSON sidecar)."""
    return ingest_batch(
        path,
        output_dir,
        engine_name=engine_name,
        recursive=recursive,
        dry_run=dry_run,
        write_manifest=False,
        write_engine_json=False,
        command="doc.convert",
    )
