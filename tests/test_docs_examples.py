"""Scripted doc-example check (AC-v05-12).

Runs representative commands from README / SKILL / agents-blurb so docs cannot
drift from the CLI. Image examples use fixtures and require only the core install.
Doc/video/transcribe examples skip when optional deps are missing.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "examples" / "fixtures"


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pifang.cli.main", *args, "--json"],
        capture_output=True,
        text=True,
        check=False,
        cwd=cwd or REPO,
    )


def _assert_json_ok(proc: subprocess.CompletedProcess[str], *, allow_nonzero: bool = False) -> dict:
    assert proc.stdout.strip(), f"empty stdout\nstderr={proc.stderr}\nargs failed"
    data = json.loads(proc.stdout)
    if not allow_nonzero:
        assert proc.returncode == 0, f"rc={proc.returncode}\nstdout={proc.stdout}\nstderr={proc.stderr}"
        assert data.get("ok") is True, data
    return data


@pytest.fixture
def photo(tmp_path: Path) -> Path:
    """photo.jpg as used in README examples."""
    src = FIXTURES / "sample.jpg"
    dest = tmp_path / "photo.jpg"
    if src.exists():
        shutil.copy(src, dest)
    else:
        Image.new("RGB", (640, 480), color=(90, 120, 180)).save(dest, format="JPEG")
    return dest


def test_docs_version_and_doctor() -> None:
    """Discovery commands from README / SKILL / agents-blurb."""
    proc = _run("--version")
    # typer --version may print plain version or JSON depending on implementation
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.strip()

    proc = _run("version")
    data = _assert_json_ok(proc)
    assert "version" in data

    proc = _run("doctor")
    _assert_json_ok(proc)

    proc = _run("recipe", "list")
    data = _assert_json_ok(proc)
    names = {r["name"] for r in data["recipes"]}
    assert "avatar" in names


def test_docs_image_quickstart(photo: Path, tmp_path: Path) -> None:
    """README quickstart image block (zero-extra)."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    social = tmp_path / "social"
    photos = tmp_path / "photos"
    photos.mkdir()
    shutil.copy(photo, photos / "a.jpg")
    photos_webp = tmp_path / "photos-webp"

    # pifang image avatar photo.jpg -o out/photo.webp --size 512
    proc = _run("image", "avatar", str(photo), "-o", str(out_dir / "photo.webp"), "--size", "512")
    _assert_json_ok(proc)
    assert (out_dir / "photo.webp").exists()

    # pifang image social-pack photo.jpg -o ./social/
    proc = _run("image", "social-pack", str(photo), "-o", str(social))
    _assert_json_ok(proc)

    # pifang pipe image "crop-square | resize 512 | to-webp q85" photo.jpg -o out/photo.webp
    pipe_out = out_dir / "pipe.webp"
    proc = _run(
        "pipe",
        "image",
        "crop-square | resize 512 | to-webp q85",
        str(photo),
        "-o",
        str(pipe_out),
    )
    _assert_json_ok(proc)
    assert pipe_out.exists()

    # pifang batch run image convert ./photos/ -o ./photos-webp/ --format webp --manifest ingest.jsonl
    manifest = tmp_path / "ingest.jsonl"
    proc = _run(
        "batch",
        "run",
        "image",
        "convert",
        str(photos),
        "-o",
        str(photos_webp),
        "--format",
        "webp",
        "--manifest",
        str(manifest),
    )
    data = _assert_json_ok(proc)
    assert data.get("succeeded", data.get("total", 0)) >= 1
    assert manifest.exists()


def test_docs_agents_blurb_image_lines(photo: Path, tmp_path: Path) -> None:
    """agents-blurb cheat sheet image lines."""
    out = tmp_path / "out.webp"
    proc = _run("image", "avatar", str(photo), "-o", str(out), "--size", "512")
    _assert_json_ok(proc)

    proc = _run(
        "pipe",
        "image",
        "crop-square | resize 512 | to-webp",
        str(photo),
        "-o",
        str(tmp_path / "pipe2.webp"),
    )
    _assert_json_ok(proc)


def test_docs_skill_contract_enum_strictness(photo: Path, tmp_path: Path) -> None:
    """SKILL.md: closed enums fail loud with valid options."""
    proc = _run(
        "image",
        "resize",
        str(photo),
        "-o",
        str(tmp_path / "x.webp"),
        "--width",
        "100",
        "--fit",
        "bogus",
    )
    assert proc.returncode == 1
    data = json.loads(proc.stdout)
    assert data["ok"] is False


def test_docs_agent_examples_pass_json() -> None:
    """Agent-facing docs must pass --json on every example and never mention --human."""
    agent_docs = [REPO / "docs" / "agents-blurb.md", REPO / "skills" / "pifang" / "SKILL.md"]
    consumer_docs = [*agent_docs, REPO / "README.md", REPO / "docs" / "glossary.md", REPO / "docs" / "publishing.md"]
    for path in consumer_docs:
        assert "--human" not in path.read_text(encoding="utf-8"), f"{path.name}: --human was removed"
    for path in agent_docs:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("pifang ") and "--help" not in line:
                assert "--json" in line, f"{path.name}: agent example missing --json: {line}"


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_docs_video_info_if_ffmpeg(tmp_path: Path) -> None:
    """agents-blurb: pifang video info — needs a tiny clip; skip if ffmpeg missing."""
    clip = tmp_path / "clip.mp4"
    # 1-frame black video via ffmpeg lavfi
    gen = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=320x240:d=0.5",
            "-c:v",
            "libx264",
            "-t",
            "0.5",
            str(clip),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if gen.returncode != 0:
        pytest.skip(f"could not generate clip: {gen.stderr[-200:]}")

    proc = _run("video", "info", str(clip))
    _assert_json_ok(proc)
