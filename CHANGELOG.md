# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-09-23

First public-facing release line (git dogfood → OSS). Includes **v0.5 release hardening** before first PyPI upload.

### Added

- Image domain: atoms, recipes (`avatar`, `hero`, `social-square`), pipe DSL, batch + JSONL manifests, social/blog/podcast/video-cover packs, remove-bg / flatten-bg / recolor
- Document domain: `doc convert` (markdown + images only), `doc ingest` (manifest + optional engine JSON), split/merge/extract-images/ocr, text chunk/frontmatter, meta index/validate
- Default doc engine `fast` (pymupdf4llm); optional OpenDataLoader via `pifang[doc-odl]` + JDK
- Video domain: ffmpeg-backed info/transcode/trim/extract-audio/concat/to-gif/extract-frames/resize/normalize-audio/captions + recipes; `pipe video` + `batch run video`
- Transcribe: Faster-Whisper via `pifang[transcribe]`; timeline JSON + SRT (+ optional VTT); `video`/`audio` aliases
- `pifang setup` for pip extras + printed system install hints (ffmpeg/Java)
- Agent consumer docs: `docs/agents-blurb.md`, `skills/pifang/SKILL.md`
- Root `--version` flag; leaf `--force` / `--dry-run` / `--verbose` on mutating commands
- Subprocess timeouts; structured `SUBPROCESS_TIMEOUT` errors

### Changed

- **Plain text by default, `--json` for agents** — with `--json` (root or any subcommand) stdout is exactly one JSON object, success or failure; `--human` removed
- Closed-set CLI params are real enums; pipe DSL rejects stray tokens (no silent stage drop)
- Batch early-stop accounting: `total == succeeded + failed + skipped + not_attempted`; first error inlined; domain-correct `batch.{image|video}.*` labels
- Skip-if-unchanged metadata reports the existing **output** file’s dimensions/bytes
- sdist ships a curated docs list (no internal tasks/archive/publishing checklists)
- README links are absolute GitHub URLs for PyPI rendering
- Dropped redundant `License :: OSI Approved :: …` classifier (SPDX `license = "Apache-2.0"` is authoritative)

### Fixed

- Doc ingest stem sanitization for filenames with spaces (fast engine)
- `ingest.jsonl` merge-by-input across runs; corrupt resume lines warn with line numbers
- WebM transcode codec defaults (VP9/Opus)
- Global exception fallback always emits the JSON error envelope (`INTERNAL`, exit 3)
- First-class validation/processing errors for bad dimensions, unknown formats, bad fit color, decompression bombs, corrupt PDFs, bad manifest lines, malformed custom recipes
- `image compress` crash when `--quality` ≤ 9 with `--max-kb`
- ffmpeg concat/subtitles escaping for filenames containing `'`
- Temp intermediates cleaned on failed multi-stage pipe/recipe runs
- `remove-bg` / `recolor` use Pillow C-level ops (no pure-Python pixel loops)
- Non-ASCII paths in JSON use `ensure_ascii=False`

[0.1.0]: https://github.com/StormForgeVentures/pifang/releases/tag/v0.1.0
