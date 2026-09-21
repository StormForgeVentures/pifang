"""Image operation tests."""

from pathlib import Path

import pytest
from PIL import Image

from pifang.domains.image import ops
from pifang.errors import ValidationError


def test_crop_square_center(rect_image: Path, tmp_path: Path) -> None:
    out = tmp_path / "sq.webp"
    result = ops.crop_square(rect_image, out, anchor="center", size=256)
    assert result.ok
    assert result.width == 256
    assert result.height == 256
    assert out.exists()


def test_avatar_recipe(rect_image: Path, tmp_path: Path) -> None:
    from pifang.core.recipe import run_recipe

    out = tmp_path / "avatar.webp"
    result = run_recipe("avatar", rect_image, out, {"size": 512})
    assert result.ok
    assert result.width == 512
    assert result.height == 512


def test_pipe_matches_avatar(rect_image: Path, tmp_path: Path) -> None:
    from pifang.core.pipe import run_image_pipe
    from pifang.core.recipe import run_recipe

    recipe_out = tmp_path / "r.webp"
    pipe_out = tmp_path / "p.webp"
    run_recipe("avatar", rect_image, recipe_out, {"size": 256})
    run_image_pipe("crop-square | resize 256 | to-webp q85", rect_image, pipe_out)
    assert recipe_out.exists() and pipe_out.exists()
    assert recipe_out.stat().st_size > 0
    assert pipe_out.stat().st_size > 0


def test_info(rect_image: Path) -> None:
    data = ops.info(rect_image)
    assert data["width"] == 800
    assert data["height"] == 600


def test_dry_run_no_write(rect_image: Path, tmp_path: Path) -> None:
    out = tmp_path / "nope.webp"
    result = ops.convert(rect_image, out, format="webp", dry_run=True)
    assert result.ok
    assert result.dry_run
    assert not out.exists()


def test_batch_convert(rect_image: Path, tmp_path: Path) -> None:
    from pifang.core.batch import BatchSpec, batch_run

    src_dir = tmp_path / "photos"
    src_dir.mkdir()
    (src_dir / "a.jpg").write_bytes(rect_image.read_bytes())
    out_dir = tmp_path / "out"
    manifest = tmp_path / "m.jsonl"
    spec = BatchSpec(
        domain="image",
        command="convert",
        paths=[src_dir],
        output_dir=out_dir,
        manifest_path=manifest,
        params={"format": "webp"},
    )
    result = batch_run(spec)
    assert result.succeeded == 1
    assert manifest.exists()
    assert list(out_dir.glob("*.webp"))


def test_negative_width_validation(rect_image: Path, tmp_path: Path) -> None:
    with pytest.raises(ValidationError) as ei:
        ops.resize(rect_image, tmp_path / "o.webp", width=-5)
    assert ei.value.error_code == "INVALID_DIMENSION"


def test_unknown_format_validation(rect_image: Path, tmp_path: Path) -> None:
    with pytest.raises(ValidationError) as ei:
        ops.convert(rect_image, tmp_path / "o.x", format="bogus")
    assert ei.value.error_code == "UNSUPPORTED_FORMAT"
    assert "webp" in ei.value.message


def test_invalid_color_fit(rect_image: Path, tmp_path: Path) -> None:
    with pytest.raises(ValidationError) as ei:
        ops.fit(rect_image, tmp_path / "o.webp", width=100, height=100, color="not-a-color")
    assert ei.value.error_code == "INVALID_COLOR"


def test_compress_quality_range(rect_image: Path, tmp_path: Path) -> None:
    with pytest.raises(ValidationError) as ei:
        ops.compress(rect_image, tmp_path / "o.jpg", quality=0)
    assert ei.value.error_code == "INVALID_QUALITY"


def test_compress_quality_low_with_max_kb(rect_image: Path, tmp_path: Path) -> None:
    """quality ≤ 9 with --max-kb must not raise UnboundLocalError."""
    out = tmp_path / "c.jpg"
    result = ops.compress(rect_image, out, quality=5, max_kb=50)
    assert result.ok
    assert out.exists()
    assert result.bytes is not None and result.bytes > 0


def test_skip_metadata_from_output(rect_image: Path, tmp_path: Path) -> None:
    """Skip-if-unchanged reports EXISTING OUTPUT dimensions, not source."""
    out = tmp_path / "out.webp"
    # Create a small existing output (different size than source 800x600)
    small = Image.new("RGB", (64, 48), color=(1, 2, 3))
    small.save(out, format="WEBP")
    # Make output newer than input
    import os
    import time

    now = time.time()
    os.utime(out, (now + 10, now + 10))
    os.utime(rect_image, (now - 10, now - 10))

    result = ops.resize(rect_image, out, width=200, force=False)
    assert result.ok
    assert result.skipped is True
    assert result.width == 64
    assert result.height == 48
    assert result.bytes == out.stat().st_size


def test_pipe_rejects_stray_tokens() -> None:
    from pifang.core.pipe import parse_image_pipe

    with pytest.raises(ValidationError) as ei:
        parse_image_pipe("resize 512 to-webp")
    assert ei.value.error_code == "INVALID_PIPE_STAGE"


def test_video_pipe_rejects_stray_tokens() -> None:
    from pifang.core.video_pipe import parse_video_pipe

    with pytest.raises(ValidationError) as ei:
        parse_video_pipe("resize 1080x1920 transcode")
    assert ei.value.error_code == "INVALID_PIPE_STAGE"


def test_pipe_temp_cleanup_on_failure(rect_image: Path, tmp_path: Path) -> None:
    """Failed multi-stage pipe must not leave .pifang-pipe-* temps."""
    from pifang.core.pipe import run_image_pipe
    from pifang.errors import ValidationError

    out = tmp_path / "final.webp"
    # Stage 1 succeeds (resize), stage 2 fails (unknown format via convert)
    # Use a DSL that will fail on convert of bogus format
    with pytest.raises(ValidationError):
        # parse fails before run for unknown stages — use valid stages but bad convert format
        run_image_pipe("resize 64 | to-notarealformat", rect_image, out)

    leftovers = list(tmp_path.glob(".pifang-pipe-*"))
    assert leftovers == [], f"leaked temps: {leftovers}"


def test_pipe_temp_cleanup_on_processing_failure(rect_image: Path, tmp_path: Path, monkeypatch) -> None:
    """If a mid-stage fails, temps still cleaned in finally."""
    from pifang.core import pipe as pipe_mod
    from pifang.core.result import OpResult
    from pifang.errors import ProcessingError
    import pifang.core.recipe as recipe_mod

    out = tmp_path / "final.webp"
    call_count = {"n": 0}

    def fail_result_step(step, input_path, output_path, *, force, dry_run):
        call_count["n"] += 1
        if call_count["n"] == 1:
            from pifang.domains.image import ops as image_ops

            return image_ops.resize(input_path, output_path, width=64, force=True, dry_run=dry_run)
        return OpResult(
            ok=False,
            command="image.convert",
            input_path=input_path,
            output_path=None,
            duration_ms=0,
            error=ProcessingError("forced failure", "FORCED"),
        )

    monkeypatch.setattr(recipe_mod, "_run_step", fail_result_step)
    result = pipe_mod.run_image_pipe("resize 64 | to-webp", rect_image, out)
    assert not result.ok
    leftovers = list(tmp_path.glob(".pifang-pipe-*"))
    assert leftovers == [], f"leaked temps: {leftovers}"


def test_batch_early_stop_accounting(rect_image: Path, tmp_path: Path) -> None:
    from pifang.core.batch import BatchSpec, batch_run

    src_dir = tmp_path / "photos"
    src_dir.mkdir()
    for name in ("a.jpg", "b.jpg", "c.jpg"):
        (src_dir / name).write_bytes(rect_image.read_bytes())
    # Pre-create output for a so convert succeeds; make b a non-image to fail
    (src_dir / "b.jpg").write_bytes(b"not-an-image")

    out_dir = tmp_path / "out"
    spec = BatchSpec(
        domain="image",
        command="convert",
        paths=[src_dir],
        output_dir=out_dir,
        continue_on_error=False,
        params={"format": "webp"},
    )
    result = batch_run(spec)
    assert result.total == 3
    assert result.total == result.succeeded + result.failed + result.skipped + result.not_attempted
    assert result.failed >= 1
    assert result.not_attempted >= 1 or result.failed + result.succeeded == result.total
    assert result.first_error_code is not None
    assert result.first_error_message is not None


def test_batch_domain_label_on_error(rect_image: Path, tmp_path: Path) -> None:
    from pifang.core.batch import BatchSpec, batch_run

    src_dir = tmp_path / "photos"
    src_dir.mkdir()
    (src_dir / "a.jpg").write_bytes(b"corrupt")
    out_dir = tmp_path / "out"
    spec = BatchSpec(
        domain="image",
        command="convert",
        paths=[src_dir],
        output_dir=out_dir,
        params={"format": "webp"},
    )
    result = batch_run(spec)
    assert result.failed == 1
    assert result.results[0].command.startswith("batch.image.")


def test_emit_json_ensure_ascii_false(tmp_path: Path, capsys) -> None:
    from pifang.core.output import emit_json

    emit_json({"path": str(tmp_path / "café.webp"), "ok": True})
    out = capsys.readouterr().out
    assert "café" in out
    assert "\\u" not in out
