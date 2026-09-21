# Pifang

[![CI](https://github.com/StormForgeVentures/pifang/actions/workflows/ci.yml/badge.svg)](https://github.com/StormForgeVentures/pifang/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/StormForgeVentures/pifang/blob/main/LICENSE)

Agent-first Python CLI for deterministic image, document, and media processing.

Pifang gives AI agents stable commands instead of one-off scripts: resize/crop/convert images, run named recipes, chain pipe DSL stages, batch-process folders with JSONL manifests, convert PDFs to markdown, edit video via ffmpeg, and transcribe with Faster-Whisper.

## Built for agents

Most CLIs tolerate automation; pifang is designed for it.

- **One output contract.** Add `--json` and stdout is exactly one JSON object — success or failure, no tracebacks to parse around. Without it you get plain text for the terminal. Progress and logs go to stderr.
- **Errors that teach.** Every failure returns a stable `error_code`, a plain-language message, and a `recovery.hint` an agent can act on — down to the exact `pip install 'pifang[doc]'` to run.
- **Meaningful exit codes.** `0` ok · `1` validation · `2` missing dependency · `3` processing · `4` partial batch. Scriptable without parsing a word.
- **Strict by default.** Typos in flags, enum values, and pipe stages fail loudly with the valid options listed — never a silent fallback to something you didn't ask for.
- **Deterministic and idempotent.** Same input, same output. Unchanged work is skipped and reported as skipped; `--dry-run` previews any mutation without touching disk.
- **Discoverable.** `--help` at every level is the API doc, and `pifang doctor`, `pifang recipe list`, and `pifang setup` return JSON an agent can reason over before doing any work.

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

## For AI agents

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
