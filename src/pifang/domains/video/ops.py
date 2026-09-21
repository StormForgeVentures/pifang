"""Video processing operations (ffmpeg-backed)."""

from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path

from pifang.core.result import OpResult
from pifang.domains.video import info as video_info_mod
from pifang.domains.video.ffmpeg import (
    ensure_input,
    escape_concat_path,
    escape_filter_path,
    parse_time,
    resolve_output,
    run_ffmpeg,
    should_skip,
)
from pifang.errors import ValidationError


def _result(
    command: str,
    input_path: Path,
    output_path: Path | None,
    started: float,
    *,
    dry_run: bool = False,
    skipped: bool = False,
    fmt: str | None = None,
) -> OpResult:
    width = height = nbytes = None
    if output_path and output_path.exists() and not dry_run:
        nbytes = output_path.stat().st_size
        try:
            meta = video_info_mod.video_info(output_path)
            width = meta.get("width")
            height = meta.get("height")
            fmt = fmt or (output_path.suffix.lstrip(".") or meta.get("format"))
        except Exception:
            fmt = fmt or output_path.suffix.lstrip(".")
    return OpResult(
        ok=True,
        command=command,
        input_path=input_path,
        output_path=output_path,
        duration_ms=int((time.perf_counter() - started) * 1000),
        width=width,
        height=height,
        format=fmt,
        bytes=nbytes,
        dry_run=dry_run,
        skipped=skipped,
    )


def transcode(
    input_path: Path,
    output: Path,
    *,
    codec: str = "libx264",
    audio_codec: str = "aac",
    crf: int = 23,
    preset: str = "medium",
    format: str | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> OpResult:
    ensure_input(input_path)
    fmt = format or output.suffix.lstrip(".") or "mp4"
    out = resolve_output(input_path, output, fmt)
    started = time.perf_counter()
    if should_skip(input_path, out, force):
        return _result("video.transcode", input_path, out, started, skipped=True)

    # WebM containers reject H.264/AAC — pick VP9/Opus when caller left defaults.
    vcodec, acodec = codec, audio_codec
    if fmt.lower() == "webm":
        if vcodec in ("libx264", "h264"):
            vcodec = "libvpx-vp9"
        if acodec in ("aac", "libmp3lame"):
            acodec = "libopus"

    args = ["-i", str(input_path), "-c:v", vcodec, "-crf", str(crf), "-preset", preset]
    if acodec:
        args.extend(["-c:a", acodec])
    args.append(str(out))
    if dry_run:
        run_ffmpeg(args, dry_run=True)
        return _result("video.transcode", input_path, out, started, dry_run=True)
    run_ffmpeg(args)
    return _result("video.transcode", input_path, out, started, fmt=fmt)


def trim(
    input_path: Path,
    output: Path,
    *,
    start: str | float = 0,
    end: str | float | None = None,
    duration: str | float | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> OpResult:
    ensure_input(input_path)
    out = resolve_output(input_path, output, output.suffix.lstrip(".") or "mp4")
    started = time.perf_counter()
    if should_skip(input_path, out, force):
        return _result("video.trim", input_path, out, started, skipped=True)

    ss = parse_time(start)
    args = ["-ss", str(ss), "-i", str(input_path)]
    if duration is not None:
        args.extend(["-t", str(parse_time(duration))])
    elif end is not None:
        args.extend(["-t", str(parse_time(end) - ss)])
    args.extend(["-c", "copy", str(out)])

    if dry_run:
        run_ffmpeg(args, dry_run=True)
        return _result("video.trim", input_path, out, started, dry_run=True)
    run_ffmpeg(args)
    return _result("video.trim", input_path, out, started)


def extract_audio(
    input_path: Path,
    output: Path,
    *,
    format: str = "mp3",
    force: bool = False,
    dry_run: bool = False,
) -> OpResult:
    ensure_input(input_path)
    out = resolve_output(input_path, output, format)
    started = time.perf_counter()
    if should_skip(input_path, out, force):
        return _result("video.extract-audio", input_path, out, started, skipped=True)

    codec_map = {"mp3": "libmp3lame", "aac": "aac", "wav": "pcm_s16le", "m4a": "aac"}
    acodec = codec_map.get(format.lower(), format)
    args = ["-i", str(input_path), "-vn", "-acodec", acodec, str(out)]
    if dry_run:
        run_ffmpeg(args, dry_run=True)
        return _result("video.extract-audio", input_path, out, started, dry_run=True)
    run_ffmpeg(args)
    return _result("video.extract-audio", input_path, out, started, fmt=format)


def concat(
    inputs: list[Path],
    output: Path,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> OpResult:
    if len(inputs) < 2:
        raise ValidationError("Concat requires at least two inputs", "CONCAT_INPUTS")
    for p in inputs:
        ensure_input(p)

    out = output
    out.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    if should_skip(inputs[0], out, force) and out.exists():
        return _result("video.concat", inputs[0], out, started, skipped=True)

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as fh:
        list_path = Path(fh.name)
        for p in inputs:
            fh.write(f"file '{escape_concat_path(p)}'\n")

    args = ["-f", "concat", "-safe", "0", "-i", str(list_path), "-c", "copy", str(out)]
    try:
        if dry_run:
            run_ffmpeg(args, dry_run=True)
            return _result("video.concat", inputs[0], out, started, dry_run=True)
        run_ffmpeg(args)
    finally:
        list_path.unlink(missing_ok=True)
    return _result("video.concat", inputs[0], out, started)


def to_gif(
    input_path: Path,
    output: Path,
    *,
    fps: int = 10,
    width: int | None = 320,
    force: bool = False,
    dry_run: bool = False,
) -> OpResult:
    ensure_input(input_path)
    out = resolve_output(input_path, output, "gif")
    started = time.perf_counter()
    if should_skip(input_path, out, force):
        return _result("video.to-gif", input_path, out, started, skipped=True)

    scale = f"fps={fps},scale={width}:-1:flags=lanczos" if width else f"fps={fps}"
    args = ["-i", str(input_path), "-vf", scale, str(out)]
    if dry_run:
        run_ffmpeg(args, dry_run=True)
        return _result("video.to-gif", input_path, out, started, dry_run=True)
    run_ffmpeg(args)
    return _result("video.to-gif", input_path, out, started, fmt="gif")


def extract_frames(
    input_path: Path,
    output: Path,
    *,
    fps: float = 1.0,
    format: str = "png",
    force: bool = False,
    dry_run: bool = False,
) -> OpResult:
    ensure_input(input_path)
    out_dir = output if output.is_dir() or str(output).endswith("/") else output.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = out_dir / f"{input_path.stem}-frame-%04d.{format.lstrip('.')}"
    started = time.perf_counter()

    args = ["-i", str(input_path), "-vf", f"fps={fps}", str(pattern)]
    if dry_run:
        run_ffmpeg(args, dry_run=True)
        return _result("video.extract-frames", input_path, out_dir, started, dry_run=True)
    run_ffmpeg(args)
    return _result("video.extract-frames", input_path, out_dir, started, fmt=format)


def resize(
    input_path: Path,
    output: Path,
    *,
    width: int,
    height: int,
    fit: str = "contain",
    force: bool = False,
    dry_run: bool = False,
) -> OpResult:
    ensure_input(input_path)
    out = resolve_output(input_path, output, output.suffix.lstrip(".") or "mp4")
    started = time.perf_counter()
    if should_skip(input_path, out, force):
        return _result("video.resize", input_path, out, started, skipped=True)

    if fit == "cover":
        vf = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}"
    else:
        vf = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
    args = ["-i", str(input_path), "-vf", vf, "-c:a", "copy", str(out)]
    if dry_run:
        run_ffmpeg(args, dry_run=True)
        return _result("video.resize", input_path, out, started, dry_run=True)
    run_ffmpeg(args)
    return _result("video.resize", input_path, out, started)


def normalize_audio(
    input_path: Path,
    output: Path,
    *,
    target_lufs: float = -16.0,
    force: bool = False,
    dry_run: bool = False,
) -> OpResult:
    ensure_input(input_path)
    out = resolve_output(input_path, output, output.suffix.lstrip(".") or "mp4")
    started = time.perf_counter()
    if should_skip(input_path, out, force):
        return _result("video.normalize-audio", input_path, out, started, skipped=True)

    af = f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11"
    meta = video_info_mod.video_info(input_path)
    if meta.get("width"):
        args = ["-i", str(input_path), "-af", af, "-c:v", "copy", str(out)]
    else:
        args = ["-i", str(input_path), "-af", af, str(out)]
    if dry_run:
        run_ffmpeg(args, dry_run=True)
        return _result("video.normalize-audio", input_path, out, started, dry_run=True)
    run_ffmpeg(args)
    return _result("video.normalize-audio", input_path, out, started)


def captions(
    input_path: Path,
    output: Path,
    *,
    srt: Path | None = None,
    vtt: Path | None = None,
    burn_in: bool = False,
    force: bool = False,
    dry_run: bool = False,
) -> OpResult:
    ensure_input(input_path)
    sub = srt or vtt
    if not sub:
        raise ValidationError("Provide --srt or --vtt", "CAPTIONS_INPUT")
    if not sub.exists():
        raise ValidationError(f"Subtitle file not found: {sub}", "FILE_NOT_FOUND")

    out = resolve_output(input_path, output, output.suffix.lstrip(".") or "mp4")
    started = time.perf_counter()

    if not burn_in:
        out = resolve_output(input_path, output, sub.suffix.lstrip("."))
        if should_skip(sub, out, force):
            return _result("video.captions", input_path, out, started, skipped=True)
        if dry_run:
            return _result("video.captions", input_path, out, started, dry_run=True)
        shutil.copy2(sub, out)
        return _result("video.captions", input_path, out, started)

    if should_skip(input_path, out, force):
        return _result("video.captions", input_path, out, started, skipped=True)

    # Do not wrap in single quotes — quotes fight multi-level ' escaping.
    # Spaces are fine unquoted inside the filter path; ' : \ are escaped.
    escaped = escape_filter_path(sub)
    args = ["-i", str(input_path), "-vf", f"subtitles={escaped}", "-c:a", "copy", str(out)]
    if dry_run:
        run_ffmpeg(args, dry_run=True)
        return _result("video.captions", input_path, out, started, dry_run=True)
    run_ffmpeg(args)
    return _result("video.captions", input_path, out, started)
