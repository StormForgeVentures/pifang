"""Subtitle format writers — unit-testable without a model."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def _as_float(value: Any) -> float:
    return float(value)


def format_srt_timestamp(seconds: float) -> str:
    """Format seconds as SRT timestamp ``HH:MM:SS,mmm``."""
    if seconds < 0:
        seconds = 0.0
    total_ms = int(round(seconds * 1000))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def format_vtt_timestamp(seconds: float) -> str:
    """Format seconds as WebVTT timestamp ``HH:MM:SS.mmm``."""
    if seconds < 0:
        seconds = 0.0
    total_ms = int(round(seconds * 1000))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{ms:03d}"


def segments_to_srt(segments: Sequence[Mapping[str, Any]]) -> str:
    """Convert segment dicts to a standard SRT string."""
    blocks: list[str] = []
    for i, seg in enumerate(segments):
        idx = int(seg.get("id", i))
        start = format_srt_timestamp(_as_float(seg["start"]))
        end = format_srt_timestamp(_as_float(seg["end"]))
        text = str(seg.get("text", "")).strip()
        blocks.append(f"{idx + 1}\n{start} --> {end}\n{text}\n")
    return "\n".join(blocks)


def segments_to_vtt(segments: Sequence[Mapping[str, Any]]) -> str:
    """Convert segment dicts to a WebVTT string."""
    lines = ["WEBVTT", ""]
    for seg in segments:
        start = format_vtt_timestamp(_as_float(seg["start"]))
        end = format_vtt_timestamp(_as_float(seg["end"]))
        text = str(seg.get("text", "")).strip()
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)
