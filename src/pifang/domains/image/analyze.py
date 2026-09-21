"""Image analysis — shape, orientation, crop hints."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pifang.domains.image import ops
from pifang.domains.image.platforms import Anchor, PlatformTarget

Shape = Literal["square", "portrait", "landscape", "ultrawide", "tall"]
Orientation = Literal["square", "portrait", "landscape"]
FitQuality = Literal["ideal", "good", "heavy_crop"]


@dataclass
class ImageAnalysis:
    path: str
    width: int
    height: int
    aspect_ratio: float
    orientation: Orientation
    shape: Shape
    megapixels: float
    is_large: bool
    recommended_anchor: Anchor
    notes: list[str]

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "width": self.width,
            "height": self.height,
            "aspect_ratio": round(self.aspect_ratio, 4),
            "orientation": self.orientation,
            "shape": self.shape,
            "megapixels": round(self.megapixels, 2),
            "is_large": self.is_large,
            "recommended_anchor": self.recommended_anchor,
            "notes": self.notes,
        }


def _classify_shape(ratio: float) -> Shape:
    if 0.95 <= ratio <= 1.05:
        return "square"
    if ratio >= 2.2:
        return "ultrawide"
    if ratio >= 1.2:
        return "landscape"
    if ratio <= 0.55:
        return "tall"
    if ratio < 0.95:
        return "portrait"
    return "landscape"


def _classify_orientation(width: int, height: int) -> Orientation:
    if width == height:
        return "square"
    return "landscape" if width > height else "portrait"


def _recommended_anchor(width: int, height: int, shape: Shape) -> Anchor:
    """Heuristic focal anchor when cover-cropping to unlike aspect ratios."""
    if shape in ("portrait", "tall"):
        return "top"  # keep headroom / subject top for vertical sources → banners
    if shape == "ultrawide":
        return "center"
    return "center"


def _analysis_notes(width: int, height: int, shape: Shape, orientation: Orientation) -> list[str]:
    notes: list[str] = []
    mp = (width * height) / 1_000_000
    if mp >= 8:
        notes.append("High-resolution source; all platform exports will downscale cleanly.")
    elif mp < 0.5:
        notes.append("Low-resolution source; some large banner targets may look soft.")

    if shape == "ultrawide":
        notes.append("Ultrawide source: vertical story targets will crop left/right edges.")
    elif orientation == "portrait":
        notes.append("Portrait source: landscape banners and thumbnails will crop top/bottom.")
    elif orientation == "landscape":
        notes.append("Landscape source: square posts and vertical story formats will crop sides.")
    elif shape == "square":
        notes.append("Square source: widescreen thumbnails will crop top/bottom; stories will crop sides.")

    return notes


def analyze_path(input_path: Path) -> ImageAnalysis:
    info = ops.info(input_path)
    width = int(info["width"])
    height = int(info["height"])
    ratio = width / height if height else 1.0
    shape = _classify_shape(ratio)
    orientation = _classify_orientation(width, height)
    mp = (width * height) / 1_000_000

    return ImageAnalysis(
        path=str(input_path.resolve()),
        width=width,
        height=height,
        aspect_ratio=ratio,
        orientation=orientation,
        shape=shape,
        megapixels=mp,
        is_large=mp >= 2.0 or max(width, height) >= 2000,
        recommended_anchor=_recommended_anchor(width, height, shape),
        notes=_analysis_notes(width, height, shape, orientation),
    )


def fit_quality(analysis: ImageAnalysis, target: PlatformTarget) -> FitQuality:
    """How much aspect-ratio distortion cover-crop will need."""
    diff = abs(analysis.aspect_ratio - target.aspect_ratio) / max(analysis.aspect_ratio, target.aspect_ratio)
    if diff < 0.08:
        return "ideal"
    if diff < 0.35:
        return "good"
    return "heavy_crop"


def anchor_for_target(analysis: ImageAnalysis, target: PlatformTarget) -> Anchor:
    """Pick crop anchor from source shape + target category."""
    if target.anchor != "center":
        return target.anchor
    if analysis.orientation == "portrait" and target.aspect_ratio > 1.4:
        return "top"
    if analysis.orientation == "landscape" and target.aspect_ratio < 0.7:
        return "center"
    return analysis.recommended_anchor
