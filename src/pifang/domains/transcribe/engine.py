"""Faster-Whisper engine wrapper."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pifang.errors import MissingDependencyError, ValidationError

INSTALL_HINT = "pip install pifang[transcribe]"


def _import_whisper() -> Any:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise MissingDependencyError(
            "faster-whisper not installed",
            {"hint": INSTALL_HINT},
        ) from exc
    return WhisperModel


def load_model(model_size: str = "base", *, device: str = "cpu", compute_type: str = "int8") -> Any:
    """Load a Faster-Whisper model (lazy import)."""
    WhisperModel = _import_whisper()
    return WhisperModel(model_size, device=device, compute_type=compute_type)


def transcribe_audio(
    audio_path: Path,
    *,
    model: str = "base",
    language: str | None = None,
    whisper_model: Any | None = None,
) -> dict[str, Any]:
    """Transcribe an audio file; return language, duration, and normalized segments."""
    if not audio_path.exists():
        raise ValidationError(f"File not found: {audio_path}", "FILE_NOT_FOUND")

    loaded = whisper_model if whisper_model is not None else load_model(model)
    kwargs: dict[str, Any] = {}
    if language:
        kwargs["language"] = language

    segments_iter, info = loaded.transcribe(str(audio_path), **kwargs)
    segments: list[dict[str, Any]] = []
    for i, seg in enumerate(segments_iter):
        segments.append(
            {
                "id": i,
                "start": float(seg.start),
                "end": float(seg.end),
                "text": (seg.text or "").strip(),
            }
        )

    detected = getattr(info, "language", None) or language
    duration = getattr(info, "duration", None)
    if duration is None and segments:
        duration = float(segments[-1]["end"])
    elif duration is None:
        duration = 0.0

    return {
        "engine": "faster-whisper",
        "model": model,
        "language": detected,
        "duration_sec": float(duration),
        "segments": segments,
    }
