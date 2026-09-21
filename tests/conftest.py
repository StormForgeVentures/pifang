"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture
def rect_image(tmp_path: Path) -> Path:
    path = tmp_path / "rect.jpg"
    img = Image.new("RGB", (800, 600), color=(120, 80, 200))
    img.save(path, format="JPEG")
    return path


@pytest.fixture
def square_image(tmp_path: Path) -> Path:
    path = tmp_path / "square.png"
    img = Image.new("RGB", (400, 400), color=(50, 150, 250))
    img.save(path, format="PNG")
    return path
