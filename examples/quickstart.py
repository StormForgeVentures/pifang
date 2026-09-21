#!/usr/bin/env python3
"""Pifang quickstart — avatar + batch convert."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from pifang.core.batch import BatchSpec, batch_run
from pifang.core.recipe import run_recipe


def main() -> None:
    root = Path(__file__).resolve().parent / "fixtures"
    root.mkdir(exist_ok=True)
    src = root / "sample.jpg"
    if not src.exists():
        Image.new("RGB", (640, 480), (200, 100, 50)).save(src)

    avatar_out = root / "avatar.webp"
    run_recipe("avatar", src, avatar_out, {"size": 256})
    print(f"avatar -> {avatar_out} ({avatar_out.stat().st_size} bytes)")

    batch_dir = root / "batch-in"
    batch_dir.mkdir(exist_ok=True)
    (batch_dir / "copy.jpg").write_bytes(src.read_bytes())
    out_dir = root / "batch-out"
    batch_run(
        BatchSpec(
            domain="image",
            command="convert",
            paths=[batch_dir],
            output_dir=out_dir,
            params={"format": "webp"},
        )
    )
    print(f"batch -> {list(out_dir.glob('*.webp'))}")


if __name__ == "__main__":
    main()
