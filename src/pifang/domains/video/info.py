"""Video metadata via ffprobe."""

from __future__ import annotations

import json
from pathlib import Path

from pifang.domains.video.ffmpeg import ensure_input, run_ffprobe


def video_info(path: Path) -> dict:
    ensure_input(path)
    proc = run_ffprobe(
        [
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
    )
    data = json.loads(proc.stdout)
    fmt = data.get("format") or {}
    streams = data.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)

    duration = float(fmt.get("duration") or 0)
    width = int(video["width"]) if video and video.get("width") else None
    height = int(video["height"]) if video and video.get("height") else None

    return {
        "path": str(path.resolve()),
        "duration_sec": round(duration, 3),
        "width": width,
        "height": height,
        "format": fmt.get("format_name"),
        "size_bytes": int(fmt.get("size") or 0),
        "video_codec": video.get("codec_name") if video else None,
        "audio_codec": audio.get("codec_name") if audio else None,
        "fps": _parse_fps(video) if video else None,
    }


def _parse_fps(stream: dict) -> float | None:
    rate = stream.get("avg_frame_rate") or stream.get("r_frame_rate")
    if not rate or rate == "0/0":
        return None
    if "/" in rate:
        num, den = rate.split("/", 1)
        if float(den) == 0:
            return None
        return round(float(num) / float(den), 3)
    return float(rate)
