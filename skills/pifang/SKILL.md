---
name: pifang
description: >-
  Use the pifang CLI for agent-first image, PDF-to-markdown, video, and
  transcription jobs. Trigger when the user needs resize/crop/convert, social
  image packs, doc convert/ingest, ffmpeg trim/transcode/captions, or
  Faster-Whisper transcripts (timeline JSON + SRT) instead of ad-hoc scripts.
---

# Pifang

Prefer the `pifang` CLI over one-off Python/ffmpeg/Pillow scripts for deterministic media and document ops.

## Read first

- Consumer paste-block: [docs/agents-blurb.md](../../docs/agents-blurb.md)
- Human docs: [README.md](../../README.md)
- Glossary: [docs/glossary.md](../../docs/glossary.md)

## Install / doctor

```bash
pip install 'pifang[doc,transcribe]'
pifang setup --json
pifang doctor --doc --video --transcribe --json
```

## Rules

1. **Always pass `--json`** — stdout is then exactly one JSON object, success or failure. Without it the CLI prints plain text meant for people. The flag works before or after the subcommand. Progress goes to stderr (`--verbose`).
2. Honor exit codes 0–4; surface the JSON error envelope on failure (`error_code`, `message`, `recovery.hint`).
3. Use `doc convert` for markdown-only export; `doc ingest` for corpus/RAG prep with `ingest.jsonl`.
4. **Doc `-o` semantics:** directory for `convert` / `ingest` / `split` / `extract-images`; **file path** for `ocr` and `merge`.
5. Default doc engine is `fast`; do not require Java unless `--engine opendataloader`.
6. Never invent flags — run `pifang <group> <cmd> --help`. Closed enums and pipe stages fail loud with valid options listed.

## Contract (machine-readable)

### Exit codes

| Code | Meaning |
|---|---|
| 0 | ok |
| 1 | validation (bad flags, missing file, bad enum/DSL) |
| 2 | missing dependency |
| 3 | processing (corrupt media, subprocess timeout, INTERNAL) |
| 4 | partial batch |

### Success envelope (typical atom)

```json
{
  "ok": true,
  "command": "image.avatar",
  "input": "/abs/path/in.jpg",
  "output": "/abs/path/out.webp",
  "duration_ms": 42,
  "width": 512,
  "height": 512,
  "format": "webp",
  "bytes": 12345
}
```

### Error envelope

```json
{
  "ok": false,
  "error_code": "FILE_NOT_FOUND",
  "message": "Input file not found: missing.jpg",
  "exit_code": 1,
  "recovery": { "hint": "Check input path" }
}
```

Unexpected exceptions use `error_code: "INTERNAL"` (exit 3). Tracebacks appear on stderr only with `--verbose`.

### Pipe DSL (image)

Grammar: `STAGE [| STAGE ...]` — stages separated by `|`. Stray tokens inside a stage error (`INVALID_PIPE_STAGE`).

| Stage | Args |
|---|---|
| `crop-square` | optional `center` / anchor |
| `resize` | `512` or `512x256` |
| `to-webp` / `to-png` / `to-jpg` | optional `q85` |
| `compress` | `q80` and/or `max-kb 200` |
| `strip-exif` | none |

Example: `crop-square | resize 512 | to-webp q85`

Video pipe (`pifang pipe video "…"`): stages such as `trim`, `resize WxH`, `transcode`, `extract-audio` (see `pifang pipe video --help`).

### Batch

```bash
pifang batch run image convert ./photos/ -o ./out/ --format webp --manifest m.jsonl --json
pifang batch run video transcode ./clips/ -o ./out/ --format mp4 --json
```

- `--jobs N` parallel workers
- `--continue-on-error` process remaining files after a failure
- Manifest is JSONL (one object per file)
- Early stop without continue: `total == succeeded + failed + skipped + not_attempted`; first error is inlined in top-level JSON; exit 4 on partial failure when applicable

### Discovery

```bash
pifang --help              # top-level groups
pifang recipe list --json         # builtin + custom recipes
pifang doctor --json              # dependency report
pifang image --help        # atoms + packs
```

## Quick commands

```bash
# Images (zero extras)
pifang image avatar photo.jpg -o out.webp --size 512 --json
pifang image social-pack photo.jpg -o ./social/ --json
pifang pipe image "crop-square | resize 512 | to-webp q85" in.jpg -o out.webp --json
pifang batch run image convert ./photos/ -o ./out/ --format webp --manifest m.jsonl --json

# PDF → markdown. -o is a DIRECTORY for convert/ingest/split/extract-images.
pifang doc convert paper.pdf -o ./out/ --json
pifang doc ingest ./corpus/ -o ./corpus-md/ --json
pifang doc merge a.pdf b.pdf -o ./merged.pdf --json   # -o is a FILE
pifang doc ocr scan.pdf -o ./scan.md --json           # -o is a FILE

# Video (ffmpeg on PATH)
pifang video trim clip.mp4 -o trim.mp4 --start 5 --duration 10 --json
pifang pipe video "trim start=0 duration=10 | transcode" clip.mp4 -o out.mp4 --json
pifang batch run video transcode ./clips/ -o ./out/ --format mp4 --json

# Transcribe (pifang[transcribe]; video needs ffmpeg)
pifang transcribe clip.mp4 -o ./out/ --json
```

Also see the cheat sheet in `docs/agents-blurb.md`.
