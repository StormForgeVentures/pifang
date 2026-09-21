"""Background removal and flatten tests."""

from pathlib import Path

from PIL import Image

from pifang.domains.image.bg import flatten_background, parse_color, remove_background


def _white_bg_with_red_dot(path: Path) -> None:
    img = Image.new("RGB", (100, 100), (255, 255, 255))
    px = img.load()
    for y in range(40, 60):
        for x in range(40, 60):
            px[x, y] = (200, 30, 30)
    img.save(path)


def _transparent_logo(path: Path) -> None:
    img = Image.new("RGBA", (80, 80), (0, 0, 0, 0))
    px = img.load()
    for y in range(20, 60):
        for x in range(20, 60):
            px[x, y] = (50, 100, 200, 255)
    img.save(path)


def _checker_with_icon(path: Path) -> None:
    img = Image.new("RGB", (100, 100))
    px = img.load()
    for y in range(100):
        for x in range(100):
            if ((x // 10) + (y // 10)) % 2 == 0:
                px[x, y] = (255, 255, 255)
            else:
                px[x, y] = (204, 204, 204)
    for y in range(35, 65):
        for x in range(35, 65):
            px[x, y] = (0, 128, 255)
    img.save(path)


def test_remove_white_bg(tmp_path: Path) -> None:
    src = tmp_path / "white.jpg"
    out = tmp_path / "out.png"
    _white_bg_with_red_dot(src)
    result = remove_background(src, out, mode="white", tolerance=10)
    assert result.ok
    out_img = Image.open(out).convert("RGBA")
    assert out_img.getpixel((10, 10))[3] == 0  # corner transparent
    assert out_img.getpixel((50, 50))[3] == 255  # red dot opaque


def test_flatten_to_black(tmp_path: Path) -> None:
    src = tmp_path / "logo.png"
    out = tmp_path / "flat.png"
    _transparent_logo(src)
    result = flatten_background(src, out, color="black")
    assert result.ok
    px = Image.open(out).convert("RGB").getpixel((10, 10))
    assert px == (0, 0, 0)


def test_flatten_to_custom_hex(tmp_path: Path) -> None:
    src = tmp_path / "logo.png"
    out = tmp_path / "flat.webp"
    _transparent_logo(src)
    flatten_background(src, out, color="#ff00aa")
    px = Image.open(out).convert("RGB").getpixel((5, 5))
    assert px == (255, 0, 170)


def test_remove_checker_mode(tmp_path: Path) -> None:
    src = tmp_path / "check.png"
    out = tmp_path / "cut.png"
    _checker_with_icon(src)
    remove_background(src, out, mode="checker", tolerance=20)
    out_img = Image.open(out).convert("RGBA")
    assert out_img.getpixel((5, 5))[3] == 0
    assert out_img.getpixel((50, 50))[3] == 255


def test_parse_color() -> None:
    assert parse_color("white") == (255, 255, 255)
    assert parse_color("#ff00aa") == (255, 0, 170)


def test_recolor_preserves_alpha(tmp_path: Path) -> None:
    from pifang.domains.image.recolor import recolor_foreground

    src = tmp_path / "logo.png"
    out = tmp_path / "white.png"
    img = Image.new("RGBA", (60, 60), (0, 0, 0, 0))
    px = img.load()
    px[30, 30] = (128, 0, 200, 255)  # purple
    px[35, 30] = (0, 180, 50, 255)  # green
    px[10, 10] = (0, 0, 0, 0)  # transparent
    img.save(src)

    recolor_foreground(src, out, color="white")
    result = Image.open(out).convert("RGBA")
    assert result.getpixel((10, 10))[3] == 0
    assert result.getpixel((30, 30))[:3] == (255, 255, 255)
    assert result.getpixel((30, 30))[3] == 255
    assert result.getpixel((35, 30))[:3] == (255, 255, 255)


def test_remove_bg_cli(tmp_path: Path) -> None:
    import json
    import subprocess
    import sys

    src = tmp_path / "w.jpg"
    out = tmp_path / "o.png"
    _white_bg_with_red_dot(src)
    proc = subprocess.run(
        [sys.executable, "-m", "pifang.cli.main", "--json", "image", "remove-bg", str(src), "-o", str(out), "--mode", "white"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["ok"] is True
    assert out.exists()


def test_remove_bg_large_image_perf(tmp_path: Path) -> None:
    """Regression: per-pixel loops must not dominate at multi-megapixel sizes.

    Full 24MP is heavy for CI disk/memory; 4MP (≈2000x2000) exercises the
    bytearray path and should finish well under 2s on modern CPUs.
    """
    import time

    src = tmp_path / "big.png"
    out = tmp_path / "big-out.png"
    # White field with a solid red block
    img = Image.new("RGB", (2000, 2000), (255, 255, 255))
    img.paste(Image.new("RGB", (200, 200), (200, 30, 30)), (900, 900))
    img.save(src)

    t0 = time.perf_counter()
    result = remove_background(src, out, mode="white", tolerance=10)
    elapsed = time.perf_counter() - t0
    assert result.ok
    assert elapsed < 2.0, f"remove-bg took {elapsed:.2f}s at 4MP (budget 2s)"
    out_img = Image.open(out).convert("RGBA")
    assert out_img.getpixel((10, 10))[3] == 0
    assert out_img.getpixel((1000, 1000))[3] == 255


def test_recolor_large_image_perf(tmp_path: Path) -> None:
    import time

    from pifang.domains.image.recolor import recolor_foreground

    src = tmp_path / "logo-big.png"
    out = tmp_path / "white-big.png"
    img = Image.new("RGBA", (2000, 2000), (0, 0, 0, 0))
    img.paste(Image.new("RGBA", (1000, 1000), (128, 0, 200, 255)), (500, 500))
    img.save(src)

    t0 = time.perf_counter()
    result = recolor_foreground(src, out, color="white")
    elapsed = time.perf_counter() - t0
    assert result.ok
    assert elapsed < 2.0, f"recolor took {elapsed:.2f}s at 4MP (budget 2s)"
    result_img = Image.open(out).convert("RGBA")
    assert result_img.getpixel((10, 10))[3] == 0
    assert result_img.getpixel((1000, 1000))[:3] == (255, 255, 255)
