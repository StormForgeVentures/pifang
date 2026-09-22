# Pifang

[![CI](https://github.com/StormForgeVentures/pifang/actions/workflows/ci.yml/badge.svg)](https://github.com/StormForgeVentures/pifang/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/StormForgeVentures/pifang/blob/main/LICENSE)

One CLI for the media chores that usually end up as one-off scripts: resize and convert images, export every social/blog/podcast size from one photo, turn PDFs into markdown, trim and transcode video, transcribe audio. Plain Python, runs locally, no cloud.

Built so AI agents can drive it too: add `--json` and every command returns one JSON object with stable exit codes.

## What it does

| Domain | Commands |
|---|---|
| **Image** (core, Pillow) | `resize` `crop` `crop-square` `fit` `convert` `compress` `thumbnail` `strip-exif` `info` `analyze` · `remove-bg` `flatten-bg` `recolor` · recipes `avatar` `hero` `social-square` |
| **Image packs** | `social-pack` (Instagram square/tall/story, Facebook, LinkedIn, X, YouTube…) · `blog-pack` (OG, hero, Medium, card) · `podcast-pack` (Apple/Spotify covers) · `video-cover-pack` · `custom-pack` (your own `WxH:slug` list) |
| **Document** (`[doc]`) | `doc convert` PDF → markdown + images · `doc ingest` a folder → markdown + `ingest.jsonl` for RAG · `split` `merge` `extract-images` `ocr` `info` · `text chunk` `text frontmatter` · `meta index` `meta validate` |
| **Video** (system ffmpeg) | `trim` `transcode` `resize` `concat` `to-gif` `extract-frames` `extract-audio` `normalize-audio` `captions` `info` · recipes `social-clip` `podcast-audio` |
| **Transcribe** (`[transcribe]`) | `transcribe` any audio/video → `.transcript.json` + `.srt` (+ `.vtt`) with Faster-Whisper, local |
| **Pipelines** | `pipe image "crop-square \| resize 512 \| to-webp q85"` · `pipe video "trim 0-30 \| resize 1080x1920 \| transcode"` · `batch run image\|video <command> ./folder/` with a JSONL manifest · custom YAML recipes |

Every mutating command supports `--dry-run` and skips unchanged work; `pifang doctor` tells you which optional pieces are installed.

## Install

```bash
uv tool install 'pifang[doc,transcribe]'
# or
pipx install 'pifang[doc,transcribe]'
# or
pip install 'pifang[doc,transcribe]'

# guided extras (pip) + printed system commands for ffmpeg/Java
pifang setup
pifang setup --extras doc,transcribe --install
```

| Extra | What you get |
|---|---|
| *(core)* | Pillow image CLI |
| `doc` | Pure-Python PDF path (default engine `fast`) |
| `doc-odl` | Optional OpenDataLoader (needs JDK 11+) |
| `doc-heavy` | marker + docling |
| `transcribe` | Faster-Whisper |
| `video` | Marker only — install system ffmpeg/ffprobe |
| `fast` | optional pyvips |

Default doc engine is pure-Python `fast`. OpenDataLoader is opt-in: `--engine opendataloader`.

## Quickstart

```bash
# works on a bare install — no extras, no system deps
pifang image avatar photo.jpg -o out/photo.webp --size 512
pifang image social-pack photo.jpg -o ./social/
pifang pipe image "crop-square | resize 512 | to-webp q85" photo.jpg -o out/photo.webp
pifang batch run image convert ./photos/ -o ./photos-webp/ --format webp --manifest ingest.jsonl

# check what the optional surfaces need
pifang doctor --doc --video --transcribe

pifang doc convert paper.pdf -o ./out/          # md + _images/ only
pifang doc ingest ./corpus/ -o ./corpus-md/     # + ingest.jsonl

pifang video trim clip.mp4 -o trim.mp4 --start 5 --duration 10
pifang pipe video "trim start=0 duration=10 | transcode" clip.mp4 -o out.mp4
pifang batch run video transcode ./clips/ -o ./out/ --format mp4
pifang transcribe clip.mp4 -o ./out/            # .transcript.json + .srt
```

Output is plain text by default; add `--json` (before or after the subcommand) for one JSON object on stdout — agents should always pass it. Exit codes: 0 ok · 1 validation · 2 missing dep · 3 processing · 4 partial batch.

```console
$ pifang image avatar photo.jpg -o out/photo.webp --size 512
OK image.avatar -> out/photo.webp

$ pifang image avatar photo.jpg -o out/photo.webp --size 512 --json
{"ok": true, "command": "image.avatar", "input": "/abs/photo.jpg", "output": "/abs/out/photo.webp",
 "result": {"width": 512, "height": 512, "format": "webp", "bytes": 550}, "duration_ms": 18}

$ pifang image avatar missing.jpg -o out/x.webp --json; echo "exit=$?"
{"ok": false, "error_code": "FILE_NOT_FOUND", "message": "Input file not found: missing.jpg",
 "exit_code": 1, "recovery": {"hint": "Check input path"}}
exit=1
```

## For AI agents

Most CLIs tolerate automation; pifang is designed for it. With `--json`, stdout is exactly one JSON object, success or failure; errors carry a stable `error_code`, a plain message and a `recovery.hint` down to the exact `pip install` to run. Exit codes mean something (`0` ok · `1` validation · `2` missing dependency · `3` processing · `4` partial batch). Typos in flags, enum values and pipe stages fail loudly with the valid options listed. Same input gives the same output; unchanged work is reported as skipped. `--help` at every level is the API doc.

Paste **[docs/agents-blurb.md](https://github.com/StormForgeVentures/pifang/blob/main/docs/agents-blurb.md)** into your project’s `AGENTS.md` / `CLAUDE.md`.

Optional Agent Skill: copy or symlink [`skills/pifang/SKILL.md`](https://github.com/StormForgeVentures/pifang/blob/main/skills/pifang/SKILL.md) into your runtime’s skills directory.

## Custom recipes

Drop YAML in `./.pifang/recipes/` or `~/.config/pifang/recipes/`.

## Library use

```python
from pathlib import Path
from pifang.core.recipe import run_recipe

run_recipe("avatar", Path("photo.jpg"), Path("out.webp"), {"size": 256})
```

## Non-goals

No GUI, no bundled Java/ffmpeg, no MCP server in 0.1.x, no generative/scene video engines. See [docs/out-of-scope.md](https://github.com/StormForgeVentures/pifang/blob/main/docs/out-of-scope.md).

## Docs

- [Contributing](https://github.com/StormForgeVentures/pifang/blob/main/CONTRIBUTING.md) · [Code of Conduct](https://github.com/StormForgeVentures/pifang/blob/main/CODE_OF_CONDUCT.md) · [Security](https://github.com/StormForgeVentures/pifang/blob/main/SECURITY.md) · [Changelog](https://github.com/StormForgeVentures/pifang/blob/main/CHANGELOG.md)
- [Project brief](https://github.com/StormForgeVentures/pifang/blob/main/docs/project-brief.md) · [API design](https://github.com/StormForgeVentures/pifang/blob/main/docs/api-design.md) · [Glossary](https://github.com/StormForgeVentures/pifang/blob/main/docs/glossary.md)
- [Publishing (PyPI)](https://github.com/StormForgeVentures/pifang/blob/main/docs/publishing.md)

## License

Apache-2.0 — see [LICENSE](https://github.com/StormForgeVentures/pifang/blob/main/LICENSE).
