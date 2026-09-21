"""Transcription domain tests."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import pytest

from pifang.domains.transcribe.formats import (
    format_srt_timestamp,
    format_vtt_timestamp,
    segments_to_srt,
    segments_to_vtt,
)
from pifang.domains.transcribe.ops import sanitize_stem, transcribe_media
from pifang.errors import MissingDependencyError, ValidationError

HAS_FASTER_WHISPER = importlib.util.find_spec("faster_whisper") is not None
HAS_FFMPEG = shutil.which("ffmpeg") is not None

SAMPLE_SEGMENTS = [
    {"id": 0, "start": 0.0, "end": 2.4, "text": "Hello world"},
    {"id": 1, "start": 2.4, "end": 5.012, "text": "Second line"},
]


def test_format_srt_timestamp() -> None:
    assert format_srt_timestamp(0) == "00:00:00,000"
    assert format_srt_timestamp(2.4) == "00:00:02,400"
    assert format_srt_timestamp(3661.5) == "01:01:01,500"


def test_format_vtt_timestamp() -> None:
    assert format_vtt_timestamp(2.4) == "00:00:02.400"


def test_segments_to_srt() -> None:
    srt = segments_to_srt(SAMPLE_SEGMENTS)
    assert "1\n00:00:00,000 --> 00:00:02,400\nHello world\n" in srt
    assert "2\n00:00:02,400 --> 00:00:05,012\nSecond line\n" in srt


def test_segments_to_vtt() -> None:
    vtt = segments_to_vtt(SAMPLE_SEGMENTS)
    assert vtt.startswith("WEBVTT\n")
    assert "00:00:00.000 --> 00:00:02.400" in vtt
    assert "Hello world" in vtt


def test_sanitize_stem() -> None:
    assert sanitize_stem("my clip name") == "my_clip_name"
    assert sanitize_stem("already_ok") == "already_ok"


def _write_silent_wav(path: Path, *, duration_sec: float = 0.5, rate: int = 16000) -> None:
    nframes = int(duration_sec * rate)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b"\x00\x00" * nframes)


def test_transcribe_dry_run(tmp_path: Path) -> None:
    wav = tmp_path / "clip.wav"
    _write_silent_wav(wav)
    out = tmp_path / "out"
    result = transcribe_media(wav, out, dry_run=True)
    assert result["ok"] is True
    assert result["dry_run"] is True
    assert not out.exists()
    assert not list(out.glob("*")) if out.exists() else True


def test_audio_alias_rejects_video(tmp_path: Path) -> None:
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake")
    with pytest.raises(ValidationError) as exc:
        transcribe_media(video, tmp_path / "out", media_kind="audio", dry_run=True)
    assert exc.value.error_code == "NOT_AUDIO"


def test_missing_dep_hint() -> None:
    if HAS_FASTER_WHISPER:
        pytest.skip("faster-whisper installed")
    from pifang.domains.transcribe.engine import load_model

    with pytest.raises(MissingDependencyError) as exc:
        load_model("tiny")
    assert "pifang[transcribe]" in (exc.value.recovery or {}).get("hint", "")


@pytest.mark.skipif(not HAS_FASTER_WHISPER, reason="faster-whisper not installed")
def test_transcribe_audio_integration(tmp_path: Path) -> None:
    wav = tmp_path / "silent.wav"
    _write_silent_wav(wav, duration_sec=1.0)
    out = tmp_path / "out"
    result = transcribe_media(wav, out, model="tiny", force=True)
    assert result["ok"] is True
    transcript = Path(result["paths"]["transcript_json"])
    srt = Path(result["paths"]["srt"])
    assert transcript.exists()
    assert srt.exists()
    data = json.loads(transcript.read_text(encoding="utf-8"))
    assert data["engine"] == "faster-whisper"
    assert "segments" in data
    assert data["ok"] is True


@pytest.mark.skipif(not HAS_FASTER_WHISPER, reason="faster-whisper not installed")
def test_transcribe_vtt_flag(tmp_path: Path) -> None:
    wav = tmp_path / "silent.wav"
    _write_silent_wav(wav, duration_sec=1.0)
    out = tmp_path / "out"
    result = transcribe_media(wav, out, model="tiny", write_vtt=True, force=True)
    assert Path(result["paths"]["vtt"]).exists()


@pytest.mark.skipif(not (HAS_FASTER_WHISPER and HAS_FFMPEG), reason="faster-whisper or ffmpeg missing")
def test_transcribe_video_integration(tmp_path: Path) -> None:
    mp4 = tmp_path / "clip.mp4"
    proc = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            "-c:a",
            "aac",
            str(mp4),
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    out = tmp_path / "out"
    result = transcribe_media(mp4, out, model="tiny", force=True)
    assert result["ok"] is True
    assert Path(result["paths"]["transcript_json"]).exists()
    assert Path(result["paths"]["srt"]).exists()


def test_cli_audio_rejects_video(tmp_path: Path) -> None:
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake")
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pifang.cli.main",
            "--json",
            "audio",
            "transcribe",
            str(video),
            "-o",
            str(tmp_path / "out"),
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1
    data = json.loads(proc.stdout)
    assert data["ok"] is False
    assert data["error_code"] == "NOT_AUDIO"


def test_doctor_transcribe_cli() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "pifang.cli.main", "--json", "doctor", "--transcribe"],
        capture_output=True,
        text=True,
    )
    data = json.loads(proc.stdout)
    names = {c["name"] for c in data["checks"]}
    assert "faster-whisper" in names
    fw = next(c for c in data["checks"] if c["name"] == "faster-whisper")
    if HAS_FASTER_WHISPER:
        assert proc.returncode == 0
        assert fw["ok"] is True
    else:
        assert proc.returncode == 2
        assert fw["ok"] is False
        assert "pifang[transcribe]" in (fw.get("hint") or "")
