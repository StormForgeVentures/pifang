"""Recolor foreground pixels while preserving transparency."""

from __future__ import annotations

import time
from pathlib import Path

from PIL import Image

from pifang.core.result import OpResult
from pifang.domains.image.bg import parse_color
from pifang.domains.image.ops import _load, _result, _save, _should_skip
from pifang.errors import ValidationError


def recolor_foreground(
    input_path: Path,
    output_path: Path,
    *,
    color: str = "white",
    alpha_threshold: int = 1,
    force: bool = False,
    dry_run: bool = False,
) -> OpResult:
    """
    Replace every non-transparent pixel's RGB with one color; alpha channel unchanged.

    Use for logos (e.g. purple/green → all white or black) on a transparent canvas.
    """
    command = "image.recolor"
    started = time.perf_counter()
    target = parse_color(color)

    if alpha_threshold < 0 or alpha_threshold > 255:
        raise ValidationError("alpha-threshold must be 0–255", "INVALID_THRESHOLD")

    out = output_path
    if out.suffix.lower() in (".jpg", ".jpeg"):
        out = out.with_suffix(".png")
    elif not out.suffix:
        out = out.with_suffix(".png")
    out.parent.mkdir(parents=True, exist_ok=True)

    if _should_skip(input_path, out, force):
        img = _load(input_path)
        return _result(command, input_path, out, started, img.convert("RGBA"), out.suffix.lstrip("."), out.stat().st_size, skipped=True)

    img = _load(input_path).convert("RGBA")
    tr, tg, tb = target
    # Pillow C-level composite: replace RGB where alpha >= threshold, keep alpha.
    r_ch, g_ch, b_ch, a_ch = img.split()
    mask = a_ch.point(lambda v, t=alpha_threshold: 255 if v >= t else 0)
    solid_r = Image.new("L", img.size, tr)
    solid_g = Image.new("L", img.size, tg)
    solid_b = Image.new("L", img.size, tb)
    img = Image.merge(
        "RGBA",
        (
            Image.composite(solid_r, r_ch, mask),
            Image.composite(solid_g, g_ch, mask),
            Image.composite(solid_b, b_ch, mask),
            a_ch,
        ),
    )

    fmt = out.suffix.lstrip(".").lower() or "png"
    if fmt in ("jpg", "jpeg"):
        fmt = "png"
        out = out.with_suffix(".png")

    if dry_run:
        return _result(command, input_path, out, started, img, fmt, None, dry_run=True)

    size_bytes = _save(img, out, fmt)
    return _result(command, input_path, out, started, img, fmt, size_bytes)
