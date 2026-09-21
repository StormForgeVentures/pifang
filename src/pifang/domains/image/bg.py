"""Background removal and flat fill for logos / product shots."""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Literal

from PIL import Image

from pifang.core.result import OpResult
from pifang.domains.image.ops import _load, _resolve_output, _result, _save, _should_skip
from pifang.errors import ValidationError

BgRemoveMode = Literal["white", "black", "auto", "color", "checker"]

_NAMED_COLORS = {
    "white": (255, 255, 255),
    "black": (0, 0, 0),
}

# Common baked-in transparency checker colors (Photoshop, Figma exports, etc.)
_CHECKER_DEFAULTS: tuple[tuple[int, int, int], ...] = (
    (255, 255, 255),
    (204, 204, 204),
    (192, 192, 192),
    (230, 230, 230),
    (128, 128, 128),
)


def parse_color(value: str) -> tuple[int, int, int]:
    """Parse white, black, #rgb, #rrggbb, or rrggbb."""
    v = value.strip().lower()
    if v in _NAMED_COLORS:
        return _NAMED_COLORS[v]
    if v.startswith("#"):
        v = v[1:]
    if re.fullmatch(r"[0-9a-f]{3}", v):
        return tuple(int(c * 2, 16) for c in v)  # type: ignore[return-value]
    if re.fullmatch(r"[0-9a-f]{6}", v):
        return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)
    raise ValidationError(
        f"Invalid color: {value!r}",
        "INVALID_COLOR",
        {"hint": "Use white, black, or #rrggbb"},
    )


def _pixel_rgb(pixel: tuple) -> tuple[int, int, int]:
    if len(pixel) >= 3:
        return int(pixel[0]), int(pixel[1]), int(pixel[2])
    g = int(pixel[0])
    return g, g, g


def _color_match(rgb: tuple[int, int, int], target: tuple[int, int, int], tolerance: int) -> bool:
    return all(abs(a - b) <= tolerance for a, b in zip(rgb, target))


def _matches_any(rgb: tuple[int, int, int], targets: list[tuple[int, int, int]], tolerance: int) -> bool:
    return any(_color_match(rgb, t, tolerance) for t in targets)


def _corner_samples(img: Image.Image) -> list[tuple[int, int, int]]:
    w, h = img.size
    rgb = img.convert("RGB")
    points = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1), (w // 2, 0), (0, h // 2)]
    return [_pixel_rgb(rgb.getpixel(p)) for p in points]


def _detect_auto_color(img: Image.Image, tolerance: int) -> tuple[int, int, int]:
    samples = _corner_samples(img)
    base = samples[0]
    if all(_color_match(s, base, tolerance) for s in samples):
        return base
    raise ValidationError(
        "Corners differ — background is not a solid color. Try --mode color or --mode checker.",
        "BG_NOT_UNIFORM",
        {"hint": "Pass --color #rrggbb for the background you want removed"},
    )


def _detect_checker_colors(img: Image.Image, tolerance: int) -> list[tuple[int, int, int]]:
    samples = _corner_samples(img)
    unique: list[tuple[int, int, int]] = []
    for s in samples:
        if not any(_color_match(s, u, tolerance) for u in unique):
            unique.append(s)
    if len(unique) >= 2:
        return unique[:2]
    # Fall back to common checker grays if corners are ambiguous
    return list(_CHECKER_DEFAULTS[:2])


def _remove_colors_to_alpha(img: Image.Image, targets: list[tuple[int, int, int]], tolerance: int) -> Image.Image:
    """Zero alpha for pixels matching any target color within tolerance.

    Pure Pillow C-level ops (``ImageChops`` + ``point``) — no nested Python
    pixel loops. Target ≤ ~2s at 24MP without numpy.
    """
    from PIL import ImageChops

    rgba = img.convert("RGBA")
    r_ch, g_ch, b_ch, a_ch = rgba.split()
    size = rgba.size
    # Accumulator: 255 where pixel matches any target within tolerance
    match = Image.new("L", size, 0)
    tol = max(0, min(255, int(tolerance)))

    for tr, tg, tb in targets:
        # abs(channel - target) via difference against a solid band
        dr = ImageChops.difference(r_ch, Image.new("L", size, tr))
        dg = ImageChops.difference(g_ch, Image.new("L", size, tg))
        db = ImageChops.difference(b_ch, Image.new("L", size, tb))
        # 255 where each channel is within tolerance
        mr = dr.point(lambda v, t=tol: 255 if v <= t else 0)
        mg = dg.point(lambda v, t=tol: 255 if v <= t else 0)
        mb = db.point(lambda v, t=tol: 255 if v <= t else 0)
        # AND across channels, OR into the running match mask
        band = ImageChops.multiply(ImageChops.multiply(mr, mg), mb)
        match = ImageChops.lighter(match, band)

    # new_alpha = 0 where match else keep original (multiply by inverted mask)
    new_a = ImageChops.multiply(a_ch, ImageChops.invert(match))
    return Image.merge("RGBA", (r_ch, g_ch, b_ch, new_a))


def remove_background(
    input_path: Path,
    output_path: Path,
    *,
    mode: BgRemoveMode = "auto",
    color: str | None = None,
    tolerance: int = 32,
    force: bool = False,
    dry_run: bool = False,
) -> OpResult:
    """Remove a solid or checkerboard background; output keeps alpha."""
    command = "image.remove-bg"
    started = time.perf_counter()

    if tolerance < 0 or tolerance > 128:
        raise ValidationError("Tolerance must be 0–128", "INVALID_TOLERANCE")

    out = output_path
    if out.suffix.lower() in (".jpg", ".jpeg"):
        out = out.with_suffix(".png")
    elif not out.suffix:
        out = out.with_suffix(".png")
    out.parent.mkdir(parents=True, exist_ok=True)

    if _should_skip(input_path, out, force):
        img = _load(input_path)
        return _result(command, input_path, out, started, img.convert("RGBA"), "png", out.stat().st_size, skipped=True)

    img = _load(input_path)

    if mode == "white":
        targets = [(255, 255, 255)]
    elif mode == "black":
        targets = [(0, 0, 0)]
    elif mode == "color":
        if not color:
            raise ValidationError("--color required for mode=color", "MISSING_COLOR")
        targets = [parse_color(color)]
    elif mode == "checker":
        targets = _detect_checker_colors(img, tolerance)
        targets = [*targets, *_CHECKER_DEFAULTS]
        # dedupe by similarity
        deduped: list[tuple[int, int, int]] = []
        for t in targets:
            if not any(_color_match(t, d, tolerance) for d in deduped):
                deduped.append(t)
        targets = deduped
    else:  # auto
        targets = [_detect_auto_color(img, tolerance)]

    result_img = _remove_colors_to_alpha(img, targets, tolerance)

    if dry_run:
        return _result(command, input_path, out, started, result_img, "png", None, dry_run=True)

    size_bytes = _save(result_img, out, "png")
    return _result(command, input_path, out, started, result_img, "png", size_bytes)


def flatten_background(
    input_path: Path,
    output_path: Path,
    *,
    color: str = "white",
    format: str | None = None,
    quality: int = 90,
    force: bool = False,
    dry_run: bool = False,
) -> OpResult:
    """Composite a transparent logo/image onto a solid background color."""
    command = "image.flatten-bg"
    started = time.perf_counter()
    fill = parse_color(color)
    out = _resolve_output(input_path, output_path, format)

    if out.suffix.lower() in (".jpg", ".jpeg"):
        fmt = "jpg"
    elif format:
        fmt = format.lstrip(".").lower()
    else:
        fmt = out.suffix.lstrip(".").lower() or "png"

    if fmt in ("jpg", "jpeg") and out.suffix.lower() not in (".jpg", ".jpeg"):
        out = out.with_suffix(".jpg")

    if _should_skip(input_path, out, force):
        img = _load(input_path)
        return _result(command, input_path, out, started, img, fmt, out.stat().st_size, skipped=True)

    img = _load(input_path).convert("RGBA")
    canvas = Image.new("RGBA", img.size, (*fill, 255))
    canvas.paste(img, (0, 0), img)

    if fmt in ("jpg", "jpeg"):
        flat = canvas.convert("RGB")
    else:
        flat = canvas

    if dry_run:
        return _result(command, input_path, out, started, flat, fmt, None, dry_run=True)

    size_bytes = _save(flat, out, fmt, quality)
    return _result(command, input_path, out, started, flat, fmt, size_bytes)
