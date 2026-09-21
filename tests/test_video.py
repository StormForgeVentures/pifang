"""Video domain tests (skip if ffmpeg absent)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from pifang.domains.video import ops
from pifang.domains.video.info import video_info

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


@pytest.fixture
def sample_mp4(tmp_path: Path) -> Path:
    out = tmp_path / "sample.mp4"
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
            "testsrc=duration=2:size=640x480:rate=24",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-shortest",
            str(out),
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    return out


def test_video_info(sample_mp4: Path) -> None:
    info = video_info(sample_mp4)
    assert info["duration_sec"] > 0
    assert info["width"] == 640
    assert info["height"] == 480


def test_video_trim(sample_mp4: Path, tmp_path: Path) -> None:
    out = tmp_path / "trim.mp4"
    result = ops.trim(sample_mp4, out, start=0, duration=1, force=True)
    assert result.ok
    assert out.exists()
    trimmed = video_info(out)
    assert trimmed["duration_sec"] <= 1.5


def test_video_transcode(sample_mp4: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.webm"
    result = ops.transcode(sample_mp4, out, format="webm", force=True)
    assert result.ok
    assert out.exists()


def test_video_extract_audio(sample_mp4: Path, tmp_path: Path) -> None:
    out = tmp_path / "audio.mp3"
    result = ops.extract_audio(sample_mp4, out, force=True)
    assert result.ok
    assert out.exists()


def test_social_clip_recipe(sample_mp4: Path, tmp_path: Path) -> None:
    from pifang.core.recipe import run_recipe

    out = tmp_path / "social.mp4"
    result = run_recipe("social-clip", sample_mp4, out, force=True)
    assert result.ok
    assert out.exists()
    meta = video_info(out)
    assert meta["width"] == 1080
    assert meta["height"] == 1920


def test_video_info_cli(sample_mp4: Path) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "pifang.cli.main", "--json", "video", "info", str(sample_mp4)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    assert data["info"]["width"] == 640


def test_doctor_video() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "pifang.cli.main", "--json", "doctor", "--video"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    names = {c["name"] for c in data["checks"]}
    assert "ffmpeg" in names and "ffprobe" in names


def test_escape_concat_path_apostrophe() -> None:
    from pifang.domains.video.ffmpeg import escape_concat_path

    escaped = escape_concat_path("/tmp/o'brien clip.mp4")
    # Single quote becomes end-quote, escaped quote, reopen
    assert r"'\''" in f"file '{escaped}'"
    assert "o'\\''brien" in f"file '{escaped}'"


def test_escape_filter_path_apostrophe() -> None:
    from pifang.domains.video.ffmpeg import escape_filter_path

    escaped = escape_filter_path("/tmp/o'brien.srt")
    # Three backslashes before the apostrophe (option + filtergraph layers)
    assert "\\\\\\'" in escaped or escaped.count("\\") >= 3
    assert "o" in escaped and "brien" in escaped


def test_concat_apostrophe_filename(sample_mp4: Path, tmp_path: Path) -> None:
    a = tmp_path / "o'brien clip.mp4"
    b = tmp_path / "second.mp4"
    shutil.copy2(sample_mp4, a)
    shutil.copy2(sample_mp4, b)
    out = tmp_path / "merged.mp4"
    result = ops.concat([a, b], out, force=True)
    assert result.ok
    assert out.exists()
    assert out.stat().st_size > 0


def test_captions_burn_in_apostrophe_srt(sample_mp4: Path, tmp_path: Path) -> None:
    srt = tmp_path / "o'brien.srt"
    srt.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nHello\n\n",
        encoding="utf-8",
    )
    out = tmp_path / "captioned.mp4"
    result = ops.captions(sample_mp4, out, srt=srt, burn_in=True, force=True)
    assert result.ok
    assert out.exists()
    assert out.stat().st_size > 0


def test_ffmpeg_timeout_raises(monkeypatch, tmp_path: Path) -> None:
    from pifang.domains.video import ffmpeg as ff
    from pifang.errors import ProcessingError

    def _fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0] if args else "ffmpeg", timeout=0.01)

    monkeypatch.setattr(ff.subprocess, "run", _fake_run)
    monkeypatch.setattr(ff, "ffmpeg_path", lambda: "ffmpeg")
    with pytest.raises(ProcessingError) as ei:
        ff.run_ffmpeg(["-i", "x", "y.mp4"], timeout=0.01)
    assert ei.value.error_code == "SUBPROCESS_TIMEOUT"
    assert ei.value.exit_code == 3
