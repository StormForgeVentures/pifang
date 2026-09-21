"""Multi-platform export packs."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from pifang.domains.image import ops
from pifang.domains.image.analyze import ImageAnalysis, anchor_for_target, analyze_path, fit_quality
from pifang.domains.image.platforms import PlatformTarget, targets_for_pack
from pifang.errors import ValidationError


@dataclass
class ExportItem:
    target_id: str
    platform: str
    label: str
    width: int
    height: int
    output: str
    fit_quality: str
    anchor: str
    bytes: int | None
    skipped: bool = False
    dry_run: bool = False


@dataclass
class PackResult:
    ok: bool
    command: str
    pack: str
    input_path: Path
    output_dir: Path
    analysis: ImageAnalysis
    exports: list[ExportItem] = field(default_factory=list)
    duration_ms: int = 0
    manifest_path: Path | None = None
    dry_run: bool = False

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "command": self.command,
            "pack": self.pack,
            "input": str(self.input_path.resolve()),
            "output_dir": str(self.output_dir.resolve()),
            "duration_ms": self.duration_ms,
            "dry_run": self.dry_run,
            "analysis": self.analysis.to_dict(),
            "exports": [
                {
                    "id": e.target_id,
                    "platform": e.platform,
                    "label": e.label,
                    "width": e.width,
                    "height": e.height,
                    "output": e.output,
                    "fit_quality": e.fit_quality,
                    "anchor": e.anchor,
                    "bytes": e.bytes,
                    "skipped": e.skipped,
                    "dry_run": e.dry_run,
                }
                for e in self.exports
            ],
            "manifest": str(self.manifest_path) if self.manifest_path else None,
        }


def _export_target(
    input_path: Path,
    output_path: Path,
    target: PlatformTarget,
    analysis: ImageAnalysis,
    *,
    format: str,
    quality: int,
    force: bool,
    dry_run: bool,
) -> ExportItem:
    anchor = anchor_for_target(analysis, target)
    quality_label = fit_quality(analysis, target)

    if dry_run:
        return ExportItem(
            target_id=target.id,
            platform=target.platform,
            label=target.label,
            width=target.width,
            height=target.height,
            output=str(output_path.resolve()),
            fit_quality=quality_label,
            anchor=anchor,
            bytes=None,
            dry_run=True,
        )

    tmp = output_path.with_suffix(".tmp.png")
    if target.width == target.height:
        ops.crop_square(input_path, tmp, anchor=anchor, size=target.width, force=force)
    else:
        ops.cover_resize(input_path, tmp, width=target.width, height=target.height, anchor=anchor, force=force)

    if format == "png" and output_path.suffix.lstrip(".") == "png":
        tmp.replace(output_path)
        size_bytes = output_path.stat().st_size
    else:
        ops.convert(tmp, output_path, format=format, quality=quality, force=True)
        tmp.unlink(missing_ok=True)
        size_bytes = output_path.stat().st_size

    return ExportItem(
        target_id=target.id,
        platform=target.platform,
        label=target.label,
        width=target.width,
        height=target.height,
        output=str(output_path.resolve()),
        fit_quality=quality_label,
        anchor=anchor,
        bytes=size_bytes,
    )


def run_pack(
    pack: str,
    input_path: Path,
    output_dir: Path,
    *,
    only: set[str] | None = None,
    custom_specs: list[str] | None = None,
    skip_heavy: bool = False,
    format: str = "webp",
    quality: int = 85,
    force: bool = False,
    dry_run: bool = False,
) -> PackResult:
    from pifang.domains.image.platforms import PACKS, parse_custom_targets

    if pack not in PACKS:
        raise ValidationError(f"Unknown pack: {pack}", "UNKNOWN_PACK")

    custom_targets = parse_custom_targets(custom_specs)
    started = time.perf_counter()
    analysis = analyze_path(input_path)
    targets = targets_for_pack(pack, only, custom_targets)
    if not targets:
        raise ValidationError(
            "No export targets (check --only filter or add --custom WxH:slug)",
            "NO_TARGETS",
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    exports: list[ExportItem] = []
    ext = format.lstrip(".")

    for target in targets:
        fq = fit_quality(analysis, target)
        if skip_heavy and fq == "heavy_crop":
            continue
        out_path = output_dir / f"{target.id}.{ext}"
        exports.append(
            _export_target(
                input_path,
                out_path,
                target,
                analysis,
                format=ext,
                quality=quality,
                force=force,
                dry_run=dry_run,
            )
        )

    manifest_path = output_dir / "manifest.json"
    if not dry_run:
        manifest_path.write_text(
            json.dumps(
                {
                    "pack": pack,
                    "input": str(input_path.resolve()),
                    "analysis": analysis.to_dict(),
                    "exports": [
                        {
                            "id": e.target_id,
                            "output": e.output,
                            "fit_quality": e.fit_quality,
                            "width": e.width,
                            "height": e.height,
                        }
                        for e in exports
                    ],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    elapsed = int((time.perf_counter() - started) * 1000)
    command = f"image.{pack.replace('_', '-')}-pack"
    return PackResult(
        ok=True,
        command=command,
        pack=pack,
        input_path=input_path,
        output_dir=output_dir,
        analysis=analysis,
        exports=exports,
        duration_ms=elapsed,
        manifest_path=manifest_path if not dry_run else None,
        dry_run=dry_run,
    )
