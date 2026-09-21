"""Folder batch processing."""

from __future__ import annotations

import fnmatch
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from pifang.core.manifest import ManifestEntry, ManifestWriter
from pifang.core.pipe import run_image_pipe
from pifang.core.recipe import get_recipe, run_recipe
from pifang.core.result import OpResult
from pifang.core.video_pipe import run_video_pipe
from pifang.domains.image import ops
from pifang.domains.video import ops as video_ops
from pifang.errors import ValidationError

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".tif"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".mpeg", ".mpg"}


@dataclass
class BatchSpec:
    domain: str
    command: str
    paths: list[Path]
    output_dir: Path
    glob_pattern: str = "*"
    recursive: bool = False
    jobs: int = 1
    manifest_path: Path | None = None
    continue_on_error: bool = False
    force: bool = False
    dry_run: bool = False
    params: dict = field(default_factory=dict)


@dataclass
class BatchResult:
    total: int
    succeeded: int
    failed: int
    skipped: int
    not_attempted: int
    results: list[OpResult]
    manifest_path: Path | None
    first_error_code: str | None = None
    first_error_message: str | None = None


def _collect_files(paths: list[Path], glob_pattern: str, recursive: bool, exts: set[str]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_file():
            if fnmatch.fnmatch(path.name, glob_pattern):
                files.append(path)
            continue
        if not path.is_dir():
            raise ValidationError(f"Path not found: {path}", "PATH_NOT_FOUND")
        iterator = path.rglob("*") if recursive else path.glob("*")
        for item in iterator:
            if item.is_file() and item.suffix.lower() in exts and fnmatch.fnmatch(item.name, glob_pattern):
                files.append(item)
    return sorted(set(files))


def _output_for(input_file: Path, input_root: Path, output_dir: Path, suffix: str) -> Path:
    if input_root.is_file():
        return output_dir / f"{input_file.stem}{suffix}"
    rel = input_file.relative_to(input_root)
    return output_dir / rel.parent / f"{rel.stem}{suffix}"


def _run_image_item(spec: BatchSpec, input_file: Path, input_root: Path) -> OpResult:
    fmt = spec.params.get("format", "webp")
    suffix = f".{fmt.lstrip('.')}"
    out = _output_for(input_file, input_root, spec.output_dir, suffix)
    cmd = spec.command

    if cmd == "convert":
        return ops.convert(
            input_file,
            out,
            format=fmt,
            quality=int(spec.params.get("quality", 85)),
            force=spec.force,
            dry_run=spec.dry_run,
        )
    if cmd.startswith("pipe:"):
        return run_image_pipe(cmd.removeprefix("pipe:"), input_file, out, force=spec.force, dry_run=spec.dry_run)
    try:
        get_recipe(cmd)
        return run_recipe(cmd, input_file, out, spec.params, force=spec.force, dry_run=spec.dry_run)
    except ValidationError:
        pass
    raise ValidationError(f"Unsupported batch command: {spec.command}", "UNSUPPORTED_BATCH_COMMAND")


def _run_video_item(spec: BatchSpec, input_file: Path, input_root: Path) -> OpResult:
    fmt = spec.params.get("format", "mp4")
    suffix = f".{fmt.lstrip('.')}"
    out = _output_for(input_file, input_root, spec.output_dir, suffix)
    cmd = spec.command

    if cmd == "transcode":
        return video_ops.transcode(
            input_file,
            out,
            format=fmt,
            crf=int(spec.params.get("crf", 23)),
            force=spec.force,
            dry_run=spec.dry_run,
        )
    if cmd.startswith("pipe:"):
        return run_video_pipe(cmd.removeprefix("pipe:"), input_file, out, force=spec.force, dry_run=spec.dry_run)
    try:
        get_recipe(cmd)
        return run_recipe(cmd, input_file, out, spec.params, force=spec.force, dry_run=spec.dry_run)
    except ValidationError:
        pass
    raise ValidationError(f"Unsupported batch command: {spec.command}", "UNSUPPORTED_BATCH_COMMAND")


def batch_run(spec: BatchSpec) -> BatchResult:
    if spec.domain not in ("image", "video"):
        raise ValidationError(f"Batch domain not supported: {spec.domain}")

    input_root = spec.paths[0] if len(spec.paths) == 1 else spec.paths[0].parent
    if spec.paths[0].is_dir():
        input_root = spec.paths[0]

    exts = IMAGE_EXTS if spec.domain == "image" else VIDEO_EXTS
    files = _collect_files(spec.paths, spec.glob_pattern, spec.recursive, exts)
    if not files:
        raise ValidationError("No matching files found", "NO_FILES")

    spec.output_dir.mkdir(parents=True, exist_ok=True)
    writer = ManifestWriter(spec.manifest_path)
    results: list[OpResult] = []

    def work(f: Path) -> OpResult:
        try:
            if spec.domain == "video":
                return _run_video_item(spec, f, input_root)
            return _run_image_item(spec, f, input_root)
        except Exception as exc:  # noqa: BLE001 — batch captures per-file failures
            from pifang.errors import PifangError, ProcessingError

            err = exc if isinstance(exc, PifangError) else ProcessingError(str(exc))
            return OpResult(
                ok=False,
                command=f"batch.{spec.domain}.{spec.command}",
                input_path=f,
                output_path=None,
                duration_ms=0,
                error=err,
            )

    if spec.jobs <= 1:
        for f in files:
            result = work(f)
            # Ensure command is domain-labeled
            if result.command and not result.command.startswith(f"batch.{spec.domain}."):
                result.command = f"batch.{spec.domain}.{spec.command}"
            results.append(result)
            writer.append(
                ManifestEntry(
                    input=str(f.resolve()),
                    output=str(result.output_path.resolve()) if result.output_path else None,
                    command=result.command,
                    ok=result.ok,
                    duration_ms=result.duration_ms,
                    error=result.error.to_dict() if result.error else None,
                )
            )
            if not result.ok and not spec.continue_on_error:
                break
    else:
        with ThreadPoolExecutor(max_workers=spec.jobs) as pool:
            futures = {pool.submit(work, f): f for f in files}
            for fut in as_completed(futures):
                result = fut.result()
                if result.command and not result.command.startswith(f"batch.{spec.domain}."):
                    result.command = f"batch.{spec.domain}.{spec.command}"
                results.append(result)
                writer.append(
                    ManifestEntry(
                        input=str(result.input_path.resolve()),
                        output=str(result.output_path.resolve()) if result.output_path else None,
                        command=result.command,
                        ok=result.ok,
                        duration_ms=result.duration_ms,
                        error=result.error.to_dict() if result.error else None,
                    )
                )

    succeeded = sum(1 for r in results if r.ok and not r.skipped)
    skipped = sum(1 for r in results if r.skipped)
    failed = sum(1 for r in results if not r.ok)
    not_attempted = max(0, len(files) - len(results))

    first_error_code = None
    first_error_message = None
    for r in results:
        if not r.ok and r.error:
            first_error_code = r.error.error_code
            first_error_message = r.error.message
            break

    return BatchResult(
        total=len(files),
        succeeded=succeeded,
        failed=failed,
        skipped=skipped,
        not_attempted=not_attempted,
        results=results,
        manifest_path=spec.manifest_path,
        first_error_code=first_error_code,
        first_error_message=first_error_message,
    )
