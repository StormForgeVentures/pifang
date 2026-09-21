"""Platform pack and analysis tests."""

from pathlib import Path

import pytest

from pifang.domains.image.analyze import analyze_path, fit_quality
from pifang.domains.image.packs import run_pack
from pifang.domains.image.platforms import SOCIAL_PACK, parse_custom_target
from pifang.errors import ValidationError


def test_analyze_landscape(rect_image: Path) -> None:
    a = analyze_path(rect_image)
    assert a.width == 800
    assert a.height == 600
    assert a.orientation == "landscape"


def test_analyze_square(square_image: Path) -> None:
    a = analyze_path(square_image)
    assert a.shape == "square"
    assert a.orientation == "square"


def test_fit_quality_ideal(square_image: Path) -> None:
    a = analyze_path(square_image)
    ig = next(t for t in SOCIAL_PACK if t.id == "instagram-square")
    assert fit_quality(a, ig) == "ideal"


def test_instagram_tall_and_square(rect_image: Path, tmp_path: Path) -> None:
    out = tmp_path / "ig"
    result = run_pack("social", rect_image, out, only={"instagram-tall", "instagram-square"})
    ids = {e.target_id for e in result.exports}
    assert ids == {"instagram-tall", "instagram-square"}


def test_social_pack_outputs(rect_image: Path, tmp_path: Path) -> None:
    out = tmp_path / "social"
    result = run_pack("social", rect_image, out, only={"instagram", "youtube"})
    assert result.ok
    assert len(result.exports) >= 2
    assert (out / "manifest.json").exists()
    assert (out / "instagram-square.webp").exists()
    assert (out / "youtube-thumbnail.webp").exists()


def test_blog_pack(rect_image: Path, tmp_path: Path) -> None:
    out = tmp_path / "blog"
    result = run_pack("blog", rect_image, out, only={"blog-featured"})
    assert (out / "blog-featured.webp").exists()


def test_podcast_pack(square_image: Path, tmp_path: Path) -> None:
    out = tmp_path / "podcast"
    result = run_pack("podcast", square_image, out, only={"podcast-cover-standard"})
    assert (out / "podcast-cover-standard.webp").exists()
    assert result.exports[0].width == 1400


def test_custom_injector(rect_image: Path, tmp_path: Path) -> None:
    out = tmp_path / "custom"
    result = run_pack(
        "custom",
        rect_image,
        out,
        custom_specs=["1200x800:newsletter:top", "900x600:sidebar"],
    )
    assert (out / "custom-newsletter.webp").exists()
    assert (out / "custom-sidebar.webp").exists()
    assert result.exports[0].anchor == "top"


def test_custom_on_social_pack(rect_image: Path, tmp_path: Path) -> None:
    out = tmp_path / "mixed"
    result = run_pack(
        "social",
        rect_image,
        out,
        only={"instagram-square"},
        custom_specs=["640x480:preview"],
    )
    assert len(result.exports) == 2


def test_parse_custom_invalid() -> None:
    with pytest.raises(ValidationError):
        parse_custom_target("not-valid")


def test_video_cover_pack(rect_image: Path, tmp_path: Path) -> None:
    out = tmp_path / "video"
    result = run_pack("video-cover", rect_image, out)
    assert (out / "widescreen-thumbnail.webp").exists()


def test_social_pack_dry_run(rect_image: Path, tmp_path: Path) -> None:
    out = tmp_path / "dry"
    result = run_pack("social", rect_image, out, only={"instagram-square"}, dry_run=True)
    assert result.dry_run
    assert not (out / "instagram-square.webp").exists()


def test_social_pack_cli(rect_image: Path, tmp_path: Path) -> None:
    import json
    import subprocess
    import sys

    out = tmp_path / "cli-social"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pifang.cli.main",
            "--json",
            "image",
            "blog-pack",
            str(rect_image),
            "-o",
            str(out),
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    assert (out / "blog-featured.webp").exists()
