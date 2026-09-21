"""Transcription via Faster-Whisper (timeline JSON + SRT/VTT)."""

from pifang.domains.transcribe.formats import segments_to_srt, segments_to_vtt
from pifang.domains.transcribe.ops import transcribe_media

__all__ = ["segments_to_srt", "segments_to_vtt", "transcribe_media"]
