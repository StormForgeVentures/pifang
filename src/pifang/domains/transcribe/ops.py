"""Transcribe orchestration — audio direct, video via ffmpeg WAV extract."""

from __future__ import annotations

import json
import re
import tempfile
import time
from pathlib import Path
from typing import Any, Literal

from pifang.domains.transcribe.engine import transcribe_audio
from pifang.domains.transcribe.formats import segments_to_srt, segments_to_vtt
from pifang.domains.video.ffmpeg import run_ffmpeg
from pifang.errors import ValidationError

AUDIO_SUFFIXES = frozenset({".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus"})
VIDEO_SUFFIXES = frozenset({".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".mpeg", ".mpg", ".wmv", ".flv"})

MediaKind = Literal["auto", "audio", "video"]


def sanitize_stem(stem: str) -> str:
    """Normalize media stem for output paths (whitespace → ``_``)."""
    return re.sub(r"\s+", "_", stem)


def detect_media_kind(path: Path) -> Literal["audio", "video"]:
    suffix = path.suffix.lower()
    if suffix in AUDIO_SUFFIXES:
        return "audio"
    if suffix in VIDEO_SUFFIXES:
        return "video"
    raise ValidationError(
        f"Unsupported media type: {suffix or '(none)'} — expected audio or video",
        "UNSUPPORTED_MEDIA",
    )


def _resolve_kind(path: Path, media_kind: MediaKind) -> Literal["audio", "video"]:
    detected = detect_media_kind(path)
    if media_kind == "auto":
        return detected
    if media_kind == "audio" and detected != "audio":
        raise ValidationError(
            f"audio transcribe requires an audio file, got: {path.suffix.lower() or path.name}",
            "NOT_AUDIO",
        )
    if media_kind == "video" and detected != "video":
        raise ValidationError(
            f"video transcribe requires a video file, got: {path.suffix.lower() or path.name}",
            "NOT_VIDEO",
        )
    return media_kind


def _outputs_up_to_date(input_path: Path, paths: list[Path], force: bool) -> bool:
    if force:
        return False
    if not paths or not all(p.exists() for p in paths):
        return False
    in_mtime = input_path.stat().st_mtime
    return all(p.stat().st_mtime >= in_mtime for p in paths)


def _extract_temp_wav(video_path: Path) -> Path:
    """Extract 16 kHz mono WAV for Whisper; caller must delete."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()
    run_ffmpeg(
        [
            "-i",
            str(video_path),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(tmp_path),
        ]
    )
    return tmp_path


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def transcribe_media(
    path: Path,
    output_dir: Path,
    *,
    model: str = "base",
    language: str | None = None,
    write_vtt: bool = False,
    force: bool = False,
    dry_run: bool = False,
    media_kind: MediaKind = "auto",
) -> dict[str, Any]:
    """Transcribe audio or video; write timeline JSON + SRT (optional VTT)."""
    if not path.exists():
        raise ValidationError(f"File not found: {path}", "FILE_NOT_FOUND")
    if not path.is_file():
        raise ValidationError(f"Not a file: {path}", "NOT_A_FILE")

    kind = _resolve_kind(path, media_kind)
    stem = sanitize_stem(path.stem)
    started = time.perf_counter()

    transcript_path = output_dir / f"{stem}.transcript.json"
    srt_path = output_dir / f"{stem}.srt"
    vtt_path = output_dir / f"{stem}.vtt" if write_vtt else None

    out_paths = [transcript_path, srt_path]
    if vtt_path is not None:
        out_paths.append(vtt_path)

    if _outputs_up_to_date(path, out_paths, force):
        return {
            "ok": True,
            "command": "transcribe",
            "input": str(path.resolve()),
            "media_kind": kind,
            "model": model,
            "language": language,
            "paths": {
                "transcript_json": str(transcript_path.resolve()),
                "srt": str(srt_path.resolve()),
                "vtt": str(vtt_path.resolve()) if vtt_path else None,
            },
            "skipped": True,
            "dry_run": False,
            "duration_ms": int((time.perf_counter() - started) * 1000),
        }

    if dry_run:
        return {
            "ok": True,
            "command": "transcribe",
            "input": str(path.resolve()),
            "media_kind": kind,
            "model": model,
            "language": language,
            "paths": {
                "transcript_json": str(transcript_path),
                "srt": str(srt_path),
                "vtt": str(vtt_path) if vtt_path else None,
            },
            "skipped": False,
            "dry_run": True,
            "duration_ms": int((time.perf_counter() - started) * 1000),
        }

    output_dir.mkdir(parents=True, exist_ok=True)

    temp_wav: Path | None = None
    try:
        if kind == "video":
            temp_wav = _extract_temp_wav(path)
            audio_path = temp_wav
        else:
            audio_path = path

        result = transcribe_audio(audio_path, model=model, language=language)
    finally:
        if temp_wav is not None:
            temp_wav.unlink(missing_ok=True)

    timeline: dict[str, Any] = {
        "ok": True,
        "input": str(path.resolve()),
        "engine": result["engine"],
        "model": result["model"],
        "language": result["language"],
        "duration_sec": result["duration_sec"],
        "segments": result["segments"],
    }

    _write_json(transcript_path, timeline)
    srt_path.write_text(segments_to_srt(result["segments"]), encoding="utf-8")
    if vtt_path is not None:
        vtt_path.write_text(segments_to_vtt(result["segments"]), encoding="utf-8")

    return {
        "ok": True,
        "command": "transcribe",
        "input": str(path.resolve()),
        "media_kind": kind,
        "engine": result["engine"],
        "model": result["model"],
        "language": result["language"],
        "duration_sec": result["duration_sec"],
        "segment_count": len(result["segments"]),
        "paths": {
            "transcript_json": str(transcript_path.resolve()),
            "srt": str(srt_path.resolve()),
            "vtt": str(vtt_path.resolve()) if vtt_path else None,
        },
        "skipped": False,
        "dry_run": False,
        "duration_ms": int((time.perf_counter() - started) * 1000),
    }
