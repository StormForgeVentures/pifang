"""Social and video platform target sizes."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from pifang.errors import ValidationError

Anchor = Literal["center", "top", "bottom", "left", "right"]
ANCHORS = {"center", "top", "bottom", "left", "right"}


@dataclass(frozen=True)
class PlatformTarget:
    """One export size for a specific platform surface."""

    id: str
    platform: str
    label: str
    width: int
    height: int
    anchor: Anchor = "center"
    category: str = "post"  # post | cover | story | thumbnail | banner | featured

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height

    @property
    def filename(self) -> str:
        return f"{self.id}.webp"


# Instagram: square feed + tall 4:5 (page-like, slightly shorter than story)
SOCIAL_PACK: tuple[PlatformTarget, ...] = (
    PlatformTarget("instagram-square", "instagram", "Feed square (1:1)", 1080, 1080),
    PlatformTarget("instagram-tall", "instagram", "Feed tall portrait (4:5, page-like)", 1080, 1350),
    PlatformTarget("instagram-story", "instagram", "Story / Reel full screen (9:16)", 1080, 1920, category="story"),
    PlatformTarget("facebook-post", "facebook", "Shared link / post", 1200, 630),
    PlatformTarget("facebook-cover", "facebook", "Page cover", 820, 312, category="cover"),
    PlatformTarget("linkedin-post", "linkedin", "Feed post", 1200, 627),
    PlatformTarget("linkedin-cover", "linkedin", "Profile / page banner", 1584, 396, category="cover"),
    PlatformTarget("x-post", "x", "Post image (16:9)", 1200, 675),
    PlatformTarget("x-header", "x", "Profile header", 1500, 500, category="cover"),
    PlatformTarget("youtube-thumbnail", "youtube", "Video thumbnail", 1280, 720, category="thumbnail"),
    PlatformTarget("pinterest-pin", "pinterest", "Standard pin (2:3)", 1000, 1500),
    PlatformTarget("tiktok-cover", "tiktok", "Cover / vertical", 1080, 1920, category="cover"),
)

VIDEO_COVER_PACK: tuple[PlatformTarget, ...] = (
    PlatformTarget("widescreen-thumbnail", "video", "16:9 thumbnail (YouTube, embeds)", 1280, 720, category="thumbnail"),
    PlatformTarget("cover-square", "video", "Square cover (podcast / album art)", 1080, 1080, category="cover"),
    PlatformTarget("cover-portrait", "video", "Portrait cover (mobile feeds)", 1080, 1350, category="cover"),
    PlatformTarget("story-promo", "video", "Vertical story / Shorts promo", 1080, 1920, category="story"),
    PlatformTarget("og-preview", "video", "Link preview (Open Graph)", 1200, 630, category="post"),
    PlatformTarget("channel-banner", "video", "Channel / banner wide", 2560, 1440, category="banner"),
)

# Blog / CMS featured images
BLOG_PACK: tuple[PlatformTarget, ...] = (
    PlatformTarget("blog-featured", "blog", "Featured image (WordPress / OG, 1.91:1)", 1200, 630, category="featured"),
    PlatformTarget("blog-featured-wide", "blog", "Featured wide (16:9)", 1200, 675, category="featured"),
    PlatformTarget("blog-hero", "blog", "Hero / full-width header", 1920, 1080, category="featured"),
    PlatformTarget("blog-medium", "blog", "Medium-style header", 1400, 788, category="featured"),
    PlatformTarget("blog-card", "blog", "Card / archive thumbnail", 800, 450, category="thumbnail"),
)

# Podcast directories (Apple Podcasts, Spotify) — square artwork
PODCAST_PACK: tuple[PlatformTarget, ...] = (
    PlatformTarget("podcast-cover", "podcast", "Cover art (Apple/Spotify, 3000×3000 max)", 3000, 3000, category="cover"),
    PlatformTarget("podcast-cover-standard", "podcast", "Cover art standard (1400×1400)", 1400, 1400, category="cover"),
    PlatformTarget("podcast-episode", "podcast", "Episode artwork", 1400, 1400, category="cover"),
    PlatformTarget("podcast-spotify-min", "podcast", "Spotify minimum (640×640)", 640, 640, category="cover"),
)

PACKS: dict[str, tuple[PlatformTarget, ...]] = {
    "social": SOCIAL_PACK,
    "video-cover": VIDEO_COVER_PACK,
    "blog": BLOG_PACK,
    "podcast": PODCAST_PACK,
    "custom": (),  # --custom specs only
}

# Backward-compatible ids (deprecated aliases in filter only)
_ID_ALIASES: dict[str, str] = {
    "instagram-post": "instagram-square",
    "instagram-portrait": "instagram-tall",
}


def parse_custom_target(spec: str) -> PlatformTarget:
    """
    Parse --custom specs: WIDTHxHEIGHT:slug[:anchor]

    Examples:
      1200x800:newsletter-featured
      1600x900:hero:top
    """
    match = re.match(
        r"^(\d+)x(\d+):([a-z0-9][a-z0-9-]*)(?::([a-z]+))?$",
        spec.strip().lower(),
    )
    if not match:
        raise ValidationError(
            f"Invalid --custom spec: {spec!r}",
            "INVALID_CUSTOM_SPEC",
            {"hint": "Use WIDTHxHEIGHT:slug or WIDTHxHEIGHT:slug:anchor (e.g. 1200x800:featured:top)"},
        )
    width, height, slug, anchor_raw = match.groups()
    anchor: Anchor = "center"
    if anchor_raw:
        if anchor_raw not in ANCHORS:
            raise ValidationError(f"Unknown anchor: {anchor_raw}", "INVALID_ANCHOR")
        anchor = anchor_raw  # type: ignore[assignment]
    w, h = int(width), int(height)
    if w < 16 or h < 16 or w > 10000 or h > 10000:
        raise ValidationError("Custom dimensions must be between 16 and 10000", "INVALID_DIMENSION")
    return PlatformTarget(
        id=f"custom-{slug}",
        platform="custom",
        label=f"Custom ({w}×{h})",
        width=w,
        height=h,
        anchor=anchor,
        category="featured",
    )


def parse_custom_targets(specs: list[str] | None) -> list[PlatformTarget]:
    if not specs:
        return []
    return [parse_custom_target(s) for s in specs]


def targets_for_pack(
    pack: str,
    only: set[str] | None = None,
    custom: list[PlatformTarget] | None = None,
) -> list[PlatformTarget]:
    if pack not in PACKS:
        raise KeyError(pack)
    targets = list(PACKS[pack])
    if only:
        allowed = {s.strip().lower() for s in only}
        expanded = set(allowed)
        for alias, canonical in _ID_ALIASES.items():
            if alias in allowed or canonical in allowed:
                expanded.add(alias)
                expanded.add(canonical)
        targets = [
            t
            for t in targets
            if t.id in expanded
            or t.platform in expanded
            or any(part in t.id for part in expanded)
        ]
    if custom:
        targets = [*targets, *custom]
    return targets
