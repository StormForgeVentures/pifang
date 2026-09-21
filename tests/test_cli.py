"""CLI integration tests."""

import json
import subprocess
import sys
from pathlib import Path


def _run_raw(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pifang.cli.main", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    """Run with --json: most tests here assert the agent JSON contract."""
    return _run_raw("--json", *args)


def _json_out(proc: subprocess.CompletedProcess[str]) -> dict:
    assert proc.stdout.strip(), f"empty stdout; stderr={proc.stderr}"
    return json.loads(proc.stdout)


def test_doctor_json() -> None:
    proc = _run("doctor")
    assert proc.returncode == 0, proc.stderr + proc.stdout
    data = _json_out(proc)
    assert data["ok"] is True


def test_trailing_json(rect_image: Path, tmp_path: Path) -> None:
    out = tmp_path / "av.webp"
    proc = _run_raw("image", "avatar", str(rect_image), "-o", str(out), "--size", "128", "--json")
    assert proc.returncode == 0, proc.stderr + proc.stdout
    data = _json_out(proc)
    assert data["ok"] is True


def test_root_json(rect_image: Path, tmp_path: Path) -> None:
    proc = _run_raw("--json", "doctor")
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert _json_out(proc)["ok"] is True


def test_default_output_is_text(rect_image: Path, tmp_path: Path) -> None:
    out = tmp_path / "av.webp"
    proc = _run_raw("image", "avatar", str(rect_image), "-o", str(out))
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert proc.stdout.startswith("OK image.avatar -> ")


def test_default_text_for_info_commands() -> None:
    proc = _run_raw("recipe", "list")
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "- name: avatar" in proc.stdout
    assert "{" not in proc.stdout


def test_text_error_goes_to_stderr(tmp_path: Path) -> None:
    proc = _run_raw("image", "avatar", "nope.jpg", "-o", str(tmp_path / "x.webp"))
    assert proc.returncode == 1
    assert proc.stdout == ""
    assert "FILE_NOT_FOUND" in proc.stderr
    assert "Hint:" in proc.stderr


def test_text_usage_error_goes_to_stderr(rect_image: Path, tmp_path: Path) -> None:
    proc = _run_raw("image", "resize", str(rect_image), "-o", str(tmp_path / "r.webp"), "--fit", "bogus")
    assert proc.returncode == 1
    assert proc.stdout == ""
    assert "VALIDATION_ERROR" in proc.stderr


def test_avatar_cli(rect_image: Path, tmp_path: Path) -> None:
    out = tmp_path / "av.webp"
    proc = _run("image", "avatar", str(rect_image), "-o", str(out), "--size", "128")
    assert proc.returncode == 0, proc.stderr + proc.stdout
    data = _json_out(proc)
    assert data["ok"] is True
    assert out.exists()


def test_recipe_list() -> None:
    proc = _run("recipe", "list")
    assert proc.returncode == 0, proc.stderr + proc.stdout
    data = _json_out(proc)
    names = {r["name"] for r in data["recipes"]}
    assert "avatar" in names


def test_version_flag() -> None:
    proc = _run("--version")
    assert proc.returncode == 0, proc.stderr + proc.stdout
    data = _json_out(proc)
    assert data["ok"] is True
    assert "version" in data


def test_version_command() -> None:
    proc = _run("version")
    assert proc.returncode == 0, proc.stderr + proc.stdout
    data = _json_out(proc)
    assert data["ok"] is True
    assert "version" in data


def test_negative_width_json_error(rect_image: Path, tmp_path: Path) -> None:
    out = tmp_path / "x.webp"
    proc = _run("image", "resize", str(rect_image), "-o", str(out), "--width", "-1")
    assert proc.returncode == 1
    data = _json_out(proc)
    assert data["ok"] is False
    assert data["error_code"] == "INVALID_DIMENSION"
    assert "recovery" in data
    assert "hint" in data["recovery"]


def test_zero_height_crop(rect_image: Path, tmp_path: Path) -> None:
    out = tmp_path / "x.webp"
    proc = _run("image", "crop", str(rect_image), "-o", str(out), "--width", "10", "--height", "0")
    assert proc.returncode == 1
    data = _json_out(proc)
    assert data["error_code"] == "INVALID_DIMENSION"


def test_unknown_format_validation(rect_image: Path, tmp_path: Path) -> None:
    out = tmp_path / "x.bogus"
    proc = _run("image", "convert", str(rect_image), "-o", str(out), "--format", "bogus")
    assert proc.returncode == 1
    data = _json_out(proc)
    assert data["ok"] is False
    assert data["error_code"] == "VALIDATION_ERROR"
    assert "webp" in data["message"].lower() or "png" in data["message"].lower()


def test_enum_fit_rejection(rect_image: Path, tmp_path: Path) -> None:
    out = tmp_path / "x.webp"
    proc = _run("image", "resize", str(rect_image), "-o", str(out), "--width", "100", "--fit", "bogus")
    assert proc.returncode == 1
    data = _json_out(proc)
    assert data["ok"] is False
    assert data["error_code"] == "VALIDATION_ERROR"
    assert "contain" in data["message"]


def test_enum_anchor_rejection(rect_image: Path, tmp_path: Path) -> None:
    out = tmp_path / "x.webp"
    proc = _run("image", "crop-square", str(rect_image), "-o", str(out), "--anchor", "bogus")
    assert proc.returncode == 1
    data = _json_out(proc)
    assert data["ok"] is False
    assert "center" in data["message"]


def test_invalid_fit_color(rect_image: Path, tmp_path: Path) -> None:
    out = tmp_path / "x.webp"
    proc = _run(
        "image", "fit", str(rect_image), "-o", str(out),
        "--width", "100", "--height", "100", "--color", "not-a-color",
    )
    assert proc.returncode == 1
    data = _json_out(proc)
    assert data["error_code"] == "INVALID_COLOR"


def test_pipe_dsl_strictness(rect_image: Path, tmp_path: Path) -> None:
    out = tmp_path / "x.webp"
    proc = _run("pipe", "image", "resize 512 to-webp", str(rect_image), "-o", str(out))
    assert proc.returncode == 1
    data = _json_out(proc)
    assert data["error_code"] == "INVALID_PIPE_STAGE"


def test_pipe_video_dsl_strictness(tmp_path: Path) -> None:
    # No real video needed — parser fails before open
    fake = tmp_path / "v.mp4"
    fake.write_bytes(b"not-a-video")
    out = tmp_path / "out.mp4"
    proc = _run("pipe", "video", "resize 1080x1920 transcode", str(fake), "-o", str(out))
    assert proc.returncode == 1
    data = _json_out(proc)
    assert data["error_code"] == "INVALID_PIPE_STAGE"


def test_trailing_force_dry_run_help() -> None:
    proc = _run("image", "resize", "--help")
    assert proc.returncode == 0
    assert "--force" in proc.stdout
    assert "--dry-run" in proc.stdout
    assert "--verbose" in proc.stdout


def test_trailing_dry_run(rect_image: Path, tmp_path: Path) -> None:
    out = tmp_path / "dry.webp"
    proc = _run("image", "convert", str(rect_image), "-o", str(out), "--format", "webp", "--dry-run")
    assert proc.returncode == 0, proc.stderr + proc.stdout
    data = _json_out(proc)
    assert data["ok"] is True
    assert data.get("dry_run") is True
    assert not out.exists()


def test_human_flag_removed() -> None:
    proc = _run("--human", "doctor")
    assert proc.returncode == 1
    data = _json_out(proc)
    assert data["ok"] is False
    assert data["error_code"] == "VALIDATION_ERROR"


def test_compress_quality_low_max_kb(rect_image: Path, tmp_path: Path) -> None:
    out = tmp_path / "c.jpg"
    proc = _run("image", "compress", str(rect_image), "-o", str(out), "--quality", "5", "--max-kb", "50")
    assert proc.returncode == 0, proc.stderr + proc.stdout
    data = _json_out(proc)
    assert data["ok"] is True
    assert out.exists()


def test_compress_quality_out_of_range(rect_image: Path, tmp_path: Path) -> None:
    out = tmp_path / "c.jpg"
    proc = _run("image", "compress", str(rect_image), "-o", str(out), "--quality", "0")
    assert proc.returncode == 1
    data = _json_out(proc)
    assert data["error_code"] == "INVALID_QUALITY"


def test_malformed_custom_recipe_list(tmp_path: Path, monkeypatch) -> None:
    recipes = tmp_path / ".pifang" / "recipes"
    recipes.mkdir(parents=True)
    (recipes / "broken.yaml").write_text(": this: is: not: valid: yaml: [[[\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    proc = _run("recipe", "list")
    assert proc.returncode == 0, proc.stderr + proc.stdout
    data = _json_out(proc)
    assert data["ok"] is True
    names = {r["name"] for r in data["recipes"]}
    assert "avatar" in names  # builtins still load
    assert "warnings" in data
    assert any("broken" in w for w in data["warnings"])


def test_meta_validate_bad_jsonl(tmp_path: Path) -> None:
    manifest = tmp_path / "ingest.jsonl"
    manifest.write_text('{"markdown": "/nope"}\nnot-json\n', encoding="utf-8")
    proc = _run("meta", "validate", str(manifest))
    assert proc.returncode == 1
    data = _json_out(proc)
    assert data["error_code"] == "INVALID_MANIFEST_LINE"
    assert "line 2" in data["message"]


def test_ensure_ascii_false_unicode_path(rect_image: Path, tmp_path: Path) -> None:
    named = tmp_path / "café.jpg"
    named.write_bytes(rect_image.read_bytes())
    out = tmp_path / "out.webp"
    proc = _run("image", "convert", str(named), "-o", str(out), "--format", "webp")
    assert proc.returncode == 0, proc.stderr + proc.stdout
    # Literal non-ASCII in stdout (not \uXXXX)
    assert "café" in proc.stdout or "caf" in proc.stdout
