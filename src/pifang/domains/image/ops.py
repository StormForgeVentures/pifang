"""Image processing operations."""

from __future__ import annotations

import io
import time
from pathlib import Path
from typing import Literal

from PIL import Image, ImageColor, ImageOps

from pifang.core.result import OpResult
from pifang.errors import ProcessingError, ValidationError

Anchor = Literal["center", "top", "bottom", "left", "right"]
FitMode = Literal["contain", "cover"]

FORMAT_EXT = {
    "png": "png",
    "jpg": "jpeg",
    "jpeg": "jpeg",
    "webp": "webp",
    "gif": "gif",
    "avif": "avif",
}

SUPPORTED_FORMATS = sorted(set(FORMAT_EXT.keys()) | set(FORMAT_EXT.values()))


def _validate_positive_dim(name: str, value: int | None) -> None:
    if value is not None and value <= 0:
        raise ValidationError(
            f"{name} must be > 0, got {value}",
            "INVALID_DIMENSION",
            {"hint": f"Pass a positive integer for --{name}"},
        )


def _validate_format(fmt: str) -> str:
    normalized = fmt.lower().lstrip(".")
    if normalized not in FORMAT_EXT:
        supported = ", ".join(sorted(FORMAT_EXT.keys()))
        raise ValidationError(
            f"Unknown format: {fmt}. Supported formats: {supported}",
            "UNSUPPORTED_FORMAT",
            {"hint": f"Use one of: {supported}"},
        )
    return normalized


def _validate_quality(quality: int) -> None:
    if not 1 <= quality <= 100:
        raise ValidationError(
            f"quality must be between 1 and 100, got {quality}",
            "INVALID_QUALITY",
            {"hint": "Pass --quality in the range 1–100"},
        )


def _load(path: Path) -> Image.Image:
    if not path.exists():
        raise ValidationError(f"Input file not found: {path}", "FILE_NOT_FOUND", {"hint": "Check input path"})
    try:
        img = Image.open(path)
        img.load()
        return img
    except Image.DecompressionBombError as exc:
        raise ProcessingError(
            f"Image rejected as decompression bomb: {exc}",
            "DECOMPRESSION_BOMB",
            {"hint": "Use a smaller image or raise PIL.Image.MAX_IMAGE_PIXELS deliberately"},
        ) from exc
    except OSError as exc:
        raise ProcessingError(f"Failed to open image: {exc}", "IMAGE_OPEN_FAILED") from exc


def _resolve_output(input_path: Path, output: Path, fmt: str | None = None) -> Path:
    if output.is_dir() or str(output).endswith("/"):
        output.mkdir(parents=True, exist_ok=True)
        ext = FORMAT_EXT.get(fmt or input_path.suffix.lstrip(".").lower(), input_path.suffix.lstrip(".") or "png")
        return output / f"{input_path.stem}.{ext}"
    output.parent.mkdir(parents=True, exist_ok=True)
    return output


def _should_skip(input_path: Path, output_path: Path, force: bool) -> bool:
    if force or not output_path.exists():
        return False
    return output_path.stat().st_mtime >= input_path.stat().st_mtime


def _save(img: Image.Image, output_path: Path, fmt: str, quality: int = 85) -> int:
    save_kwargs: dict = {}
    pil_fmt = FORMAT_EXT.get(fmt, fmt)
    if pil_fmt not in FORMAT_EXT.values() and pil_fmt not in FORMAT_EXT:
        supported = ", ".join(sorted(FORMAT_EXT.keys()))
        raise ValidationError(
            f"Unknown format: {fmt}. Supported formats: {supported}",
            "UNSUPPORTED_FORMAT",
            {"hint": f"Use one of: {supported}"},
        )
    if pil_fmt in ("jpeg", "webp", "avif"):
        save_kwargs["quality"] = quality
    if pil_fmt == "jpeg":
        save_kwargs["optimize"] = True
    try:
        img.save(output_path, format=pil_fmt.upper() if pil_fmt != "jpg" else "JPEG", **save_kwargs)
    except (OSError, KeyError, ValueError) as exc:
        if fmt == "avif":
            raise ProcessingError(
                "AVIF save failed; install pillow-avif-plugin or use webp",
                "AVIF_UNSUPPORTED",
                {"hint": "pip install pillow-avif-plugin"},
            ) from exc
        if isinstance(exc, KeyError):
            supported = ", ".join(sorted(FORMAT_EXT.keys()))
            raise ValidationError(
                f"Unknown format: {fmt}. Supported formats: {supported}",
                "UNSUPPORTED_FORMAT",
                {"hint": f"Use one of: {supported}"},
            ) from exc
        raise ProcessingError(f"Failed to save image: {exc}", "IMAGE_SAVE_FAILED") from exc
    return output_path.stat().st_size


def _result(
    command: str,
    input_path: Path,
    output_path: Path | None,
    started: float,
    img: Image.Image | None,
    fmt: str | None,
    size_bytes: int | None,
    *,
    dry_run: bool = False,
    skipped: bool = False,
) -> OpResult:
    elapsed = int((time.perf_counter() - started) * 1000)
    return OpResult(
        ok=True,
        command=command,
        input_path=input_path,
        output_path=output_path,
        duration_ms=elapsed,
        width=img.size[0] if img else None,
        height=img.size[1] if img else None,
        format=fmt,
        bytes=size_bytes,
        dry_run=dry_run,
        skipped=skipped,
    )


def _skip_result(
    command: str,
    input_path: Path,
    output_path: Path,
    started: float,
    fmt: str | None = None,
) -> OpResult:
    """Skip-if-unchanged: report EXISTING OUTPUT file dimensions/bytes, not the source."""
    out_img = _load(output_path)
    out_fmt = fmt or output_path.suffix.lstrip(".") or None
    return _result(
        command,
        input_path,
        output_path,
        started,
        out_img,
        out_fmt,
        output_path.stat().st_size,
        skipped=True,
    )


def info(input_path: Path) -> dict:
    img = _load(input_path)
    exif = {}
    raw_exif = img.getexif()
    if raw_exif:
        for tag_id, value in raw_exif.items():
            exif[str(tag_id)] = str(value)
    return {
        "path": str(input_path.resolve()),
        "width": img.size[0],
        "height": img.size[1],
        "format": img.format,
        "mode": img.mode,
        "exif_count": len(exif),
        "has_exif": bool(exif),
    }


def resize(
    input_path: Path,
    output_path: Path,
    *,
    width: int | None = None,
    height: int | None = None,
    fit: FitMode = "contain",
    force: bool = False,
    dry_run: bool = False,
) -> OpResult:
    command = "image.resize"
    started = time.perf_counter()
    if not width and not height:
        raise ValidationError("At least one of width or height is required", "MISSING_DIMENSION")
    _validate_positive_dim("width", width)
    _validate_positive_dim("height", height)
    if fit not in ("contain", "cover"):
        raise ValidationError(
            f"fit must be 'contain' or 'cover', got {fit!r}",
            "INVALID_FIT",
            {"hint": "Use --fit contain or --fit cover"},
        )

    out = _resolve_output(input_path, output_path)
    if _should_skip(input_path, out, force):
        return _skip_result(command, input_path, out, started)

    img = _load(input_path)
    orig_w, orig_h = img.size
    target_w = width or orig_w
    target_h = height or orig_h

    if fit == "cover" and width and height:
        img = ImageOps.fit(img, (target_w, target_h), method=Image.Resampling.LANCZOS)
    else:
        img.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)

    if dry_run:
        return _result(command, input_path, out, started, img, out.suffix.lstrip("."), None, dry_run=True)

    size_bytes = _save(img, out, out.suffix.lstrip(".") or "png")
    return _result(command, input_path, out, started, img, out.suffix.lstrip("."), size_bytes)


def crop(
    input_path: Path,
    output_path: Path,
    *,
    width: int,
    height: int,
    x: int | None = None,
    y: int | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> OpResult:
    command = "image.crop"
    started = time.perf_counter()
    _validate_positive_dim("width", width)
    _validate_positive_dim("height", height)
    out = _resolve_output(input_path, output_path)
    if _should_skip(input_path, out, force):
        return _skip_result(command, input_path, out, started)

    img = _load(input_path)
    left = x if x is not None else max(0, (img.width - width) // 2)
    top = y if y is not None else max(0, (img.height - height) // 2)
    box = (left, top, left + width, top + height)
    img = img.crop(box)

    if dry_run:
        return _result(command, input_path, out, started, img, out.suffix.lstrip("."), None, dry_run=True)

    size_bytes = _save(img, out, out.suffix.lstrip(".") or "png")
    return _result(command, input_path, out, started, img, out.suffix.lstrip("."), size_bytes)


def _crop_box_for_cover(img: Image.Image, target_w: int, target_h: int, anchor: Anchor) -> tuple[int, int, int, int]:
    """Crop box matching target aspect ratio before final resize."""
    tgt_ratio = target_w / target_h
    src_w, src_h = img.size
    src_ratio = src_w / src_h

    if src_ratio > tgt_ratio:
        crop_h = src_h
        crop_w = int(src_h * tgt_ratio)
    else:
        crop_w = src_w
        crop_h = int(src_w / tgt_ratio)

    if anchor == "center":
        left = (src_w - crop_w) // 2
        top = (src_h - crop_h) // 2
    elif anchor == "top":
        left = (src_w - crop_w) // 2
        top = 0
    elif anchor == "bottom":
        left = (src_w - crop_w) // 2
        top = src_h - crop_h
    elif anchor == "left":
        left = 0
        top = (src_h - crop_h) // 2
    else:  # right
        left = src_w - crop_w
        top = (src_h - crop_h) // 2

    return left, top, left + crop_w, top + crop_h


def cover_resize(
    input_path: Path,
    output_path: Path,
    *,
    width: int,
    height: int,
    anchor: Anchor = "center",
    force: bool = False,
    dry_run: bool = False,
) -> OpResult:
    """Cover-crop to aspect ratio (with anchor), then resize to exact dimensions."""
    command = "image.cover-resize"
    started = time.perf_counter()
    _validate_positive_dim("width", width)
    _validate_positive_dim("height", height)
    out = _resolve_output(input_path, output_path)
    if _should_skip(input_path, out, force):
        return _skip_result(command, input_path, out, started)

    img = _load(input_path)
    box = _crop_box_for_cover(img, width, height, anchor)
    img = img.crop(box).resize((width, height), Image.Resampling.LANCZOS)

    if dry_run:
        return _result(command, input_path, out, started, img, out.suffix.lstrip("."), None, dry_run=True)

    size_bytes = _save(img, out, out.suffix.lstrip(".") or "png")
    return _result(command, input_path, out, started, img, out.suffix.lstrip("."), size_bytes)


def crop_square(
    input_path: Path,
    output_path: Path,
    *,
    anchor: Anchor = "center",
    size: int | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> OpResult:
    command = "image.crop-square"
    started = time.perf_counter()
    if size is not None:
        _validate_positive_dim("size", size)
    if anchor not in ("center", "top", "bottom", "left", "right"):
        raise ValidationError(
            f"anchor must be one of center, top, bottom, left, right; got {anchor!r}",
            "INVALID_ANCHOR",
            {"hint": "Use --anchor center|top|bottom|left|right"},
        )
    out = _resolve_output(input_path, output_path)
    if _should_skip(input_path, out, force):
        return _skip_result(command, input_path, out, started)

    img = _load(input_path)
    side = min(img.width, img.height)
    if anchor == "center":
        left = (img.width - side) // 2
        top = (img.height - side) // 2
    elif anchor == "top":
        left = (img.width - side) // 2
        top = 0
    elif anchor == "bottom":
        left = (img.width - side) // 2
        top = img.height - side
    elif anchor == "left":
        left = 0
        top = (img.height - side) // 2
    else:  # right
        left = img.width - side
        top = (img.height - side) // 2

    img = img.crop((left, top, left + side, top + side))
    if size:
        img = img.resize((size, size), Image.Resampling.LANCZOS)

    if dry_run:
        return _result(command, input_path, out, started, img, out.suffix.lstrip("."), None, dry_run=True)

    size_bytes = _save(img, out, out.suffix.lstrip(".") or "png")
    return _result(command, input_path, out, started, img, out.suffix.lstrip("."), size_bytes)


def fit(
    input_path: Path,
    output_path: Path,
    *,
    width: int,
    height: int,
    color: str = "#000000",
    force: bool = False,
    dry_run: bool = False,
) -> OpResult:
    command = "image.fit"
    started = time.perf_counter()
    _validate_positive_dim("width", width)
    _validate_positive_dim("height", height)
    try:
        ImageColor.getrgb(color)
    except ValueError as exc:
        raise ValidationError(
            f"Invalid color: {color!r}",
            "INVALID_COLOR",
            {"hint": "Use a CSS color name or #RRGGBB / #RGB hex value"},
        ) from exc

    out = _resolve_output(input_path, output_path)
    if _should_skip(input_path, out, force):
        return _skip_result(command, input_path, out, started)

    img = _load(input_path)
    img = ImageOps.contain(img, (width, height), method=Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (width, height), color)
    offset = ((width - img.size[0]) // 2, (height - img.size[1]) // 2)
    canvas.paste(img, offset)

    if dry_run:
        return _result(command, input_path, out, started, canvas, out.suffix.lstrip("."), None, dry_run=True)

    size_bytes = _save(canvas, out, out.suffix.lstrip(".") or "png")
    return _result(command, input_path, out, started, canvas, out.suffix.lstrip("."), size_bytes)


def convert(
    input_path: Path,
    output_path: Path,
    *,
    format: str = "webp",
    quality: int = 85,
    force: bool = False,
    dry_run: bool = False,
) -> OpResult:
    command = "image.convert"
    started = time.perf_counter()
    fmt = _validate_format(format)
    _validate_quality(quality)
    out = _resolve_output(input_path, output_path, fmt)
    if _should_skip(input_path, out, force):
        return _skip_result(command, input_path, out, started, fmt=fmt)

    img = _load(input_path)
    if fmt in ("jpg", "jpeg") and img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    if dry_run:
        return _result(command, input_path, out, started, img, fmt, None, dry_run=True)

    size_bytes = _save(img, out, fmt, quality)
    return _result(command, input_path, out, started, img, fmt, size_bytes)


def compress(
    input_path: Path,
    output_path: Path,
    *,
    quality: int = 80,
    max_kb: int | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> OpResult:
    command = "image.compress"
    started = time.perf_counter()
    _validate_quality(quality)
    out = _resolve_output(input_path, output_path)
    if _should_skip(input_path, out, force):
        return _skip_result(command, input_path, out, started)

    img = _load(input_path)
    fmt = out.suffix.lstrip(".") or "jpg"

    if dry_run:
        return _result(command, input_path, out, started, img, fmt, None, dry_run=True)

    if max_kb:
        size_bytes = 0
        buf = io.BytesIO()
        pil_fmt = FORMAT_EXT.get(fmt, fmt).upper()
        # Step quality down to 1 so quality ≤ 9 always produces a buffer
        for q in range(quality, 0, -5):
            buf = io.BytesIO()
            img.save(buf, format=pil_fmt, quality=q)
            size_bytes = buf.tell()
            if size_bytes <= max_kb * 1024:
                break
        out.write_bytes(buf.getvalue())
    else:
        size_bytes = _save(img, out, fmt, quality)

    final_img = _load(out)
    return _result(command, input_path, out, started, final_img, fmt, size_bytes if max_kb else out.stat().st_size)


def strip_exif(
    input_path: Path,
    output_path: Path,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> OpResult:
    command = "image.strip-exif"
    started = time.perf_counter()
    out = _resolve_output(input_path, output_path)
    if _should_skip(input_path, out, force):
        return _skip_result(command, input_path, out, started)

    img = _load(input_path)
    clean = Image.new(img.mode, img.size)
    clean.putdata(list(img.getdata()))
    clean.info.clear()

    if dry_run:
        return _result(command, input_path, out, started, clean, out.suffix.lstrip("."), None, dry_run=True)

    fmt = out.suffix.lstrip(".") or "png"
    size_bytes = _save(clean, out, fmt)
    return _result(command, input_path, out, started, clean, fmt, size_bytes)


def thumbnail(
    input_path: Path,
    output_path: Path,
    *,
    max_edge: int = 256,
    crop: bool = False,
    force: bool = False,
    dry_run: bool = False,
) -> OpResult:
    if crop:
        return crop_square(input_path, output_path, anchor="center", size=max_edge, force=force, dry_run=dry_run)
    return resize(input_path, output_path, width=max_edge, height=max_edge, fit="contain", force=force, dry_run=dry_run)
