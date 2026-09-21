# API Design — Pifang

**Status:** Living reference (regenerated for v0.5 release hardening)  
**Inputs:** `docs/pkg-classification.md`, `docs/project-brief.md`, live CLI

---

## Command tree (CLI)

```
pifang [--dry-run] [--verbose] [--force] [--version]
├── doctor [--doc] [--video] [--transcribe]
├── setup [--extras LIST] [--install] [--system/--no-system]
├── version
├── transcribe INPUT -o OUT_DIR [--model M] [--language L] [--vtt] [--force] [--dry-run] [--verbose]
├── recipe
│   └── list
├── image
│   ├── resize INPUT -o OUT [--width W] [--height H] [--fit contain|cover]
│   ├── crop INPUT -o OUT --width W --height H [--x X] [--y Y]
│   ├── crop-square INPUT -o OUT [--anchor center|top|bottom|left|right] [--size N]
│   ├── fit INPUT -o OUT --width W --height H [--color HEX]
│   ├── convert INPUT -o OUT [--format png|jpg|webp|avif|gif] [--quality Q]
│   ├── compress INPUT -o OUT [--quality Q] [--max-kb N]
│   ├── strip-exif INPUT -o OUT
│   ├── remove-bg INPUT -o OUT [--mode white|black|auto|color|checker] …
│   ├── flatten-bg INPUT -o OUT [--color HEX]
│   ├── recolor INPUT -o OUT [--color …]
│   ├── info INPUT
│   ├── thumbnail INPUT -o OUT [--max-edge N] [--crop]
│   ├── analyze INPUT
│   ├── social-pack / video-cover-pack / blog-pack / podcast-pack / custom-pack …
│   ├── avatar INPUT -o OUT [--size N]
│   ├── hero INPUT -o OUT [--width W] [--height H] [--max-kb N]
│   └── social-square INPUT -o OUT [--size N] [--format F]
├── video
│   ├── info / transcode / trim / extract-audio / concat / to-gif
│   ├── extract-frames / resize / normalize-audio / captions
│   ├── social-clip / podcast-audio   # recipes
│   └── transcribe …                  # alias → shared transcribe
├── audio
│   └── transcribe …                  # audio-only inputs
├── pipe
│   ├── image "STAGES" INPUT -o OUT
│   └── video "STAGES" INPUT -o OUT
├── batch run
│   ├── image COMMAND PATHS… -o OUT_DIR [--glob G] [--recursive] [--jobs N]
│   │     [--manifest PATH] [--continue-on-error] [--format F] …
│   └── video COMMAND PATHS… -o OUT_DIR [same flags]
├── doc
│   ├── convert INPUT -o OUT_DIR [--engine fast|…]   # -o DIRECTORY
│   ├── ingest INPUT -o OUT_DIR […]                  # -o DIRECTORY
│   ├── info INPUT
│   ├── split INPUT -o OUT_DIR                       # -o DIRECTORY
│   ├── merge INPUTS… -o OUT_FILE                    # -o FILE
│   ├── extract-images INPUT -o OUT_DIR              # -o DIRECTORY
│   └── ocr INPUT -o OUT_FILE                        # -o FILE
├── text
│   ├── chunk INPUT -o OUT_DIR [--mode …]
│   └── frontmatter INPUT -o OUT [--fields JSON]
└── meta
    ├── index PATH -o index.jsonl
    └── validate MANIFEST
```

**Output mode:** plain text by default (results on stdout, errors on stderr). With `--json` — accepted at the root or on any subcommand — stdout is exactly one JSON object, success or failure. There is no `--human`. Mutating commands register leaf `--force` / `--dry-run` / `--verbose` (trailing position works).

---

## Exit codes

| Code | Constant | When |
|---|---|---|
| 0 | `SUCCESS` | OK |
| 1 | `VALIDATION` | Bad flags, missing file, bad enum/DSL |
| 2 | `MISSING_DEPENDENCY` | `doctor` / import failure |
| 3 | `PROCESSING` | Corrupt media, subprocess timeout, INTERNAL |
| 4 | `PARTIAL_BATCH` | Some batch items failed |

---

## JSON stdout schemas

### Success (single operation)

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

### Error

```json
{
  "ok": false,
  "error_code": "FILE_NOT_FOUND",
  "message": "Input file not found: missing.jpg",
  "exit_code": 1,
  "recovery": { "hint": "Check input path" }
}
```

### Batch summary (early stop)

```json
{
  "ok": false,
  "total": 10,
  "succeeded": 3,
  "failed": 1,
  "skipped": 0,
  "not_attempted": 6,
  "error_code": "…",
  "message": "…"
}
```

### Manifest line (JSONL)

```json
{"input":"/in/a.jpg","output":"/out/a.webp","command":"batch.image.convert","ok":true,"duration_ms":12,"error":null}
```

---

## Pipe DSL

### Image

Grammar: `STAGE [| STAGE ...]` — unrecognized tokens in a stage → `INVALID_PIPE_STAGE`.

| Stage | Args |
|---|---|
| `crop-square` | optional anchor |
| `resize` | `256` or `256x256` |
| `to-webp` / `to-png` / `to-jpg` | optional `q85` |
| `strip-exif` | none |
| `compress` | `max-kb 200` and/or `q80` |

Example: `crop-square | resize 512 | to-webp q85`

### Video

Stages include `trim` (`start=` / `duration=` / `end=` or `a-b`), `resize WxH`, `transcode`, `extract-audio` (see `pifang pipe video --help`).

---

## Recipe YAML spec

```yaml
name: avatar
domain: image
description: Center square crop, resize, export webp
params:
  size: { type: int, default: 256 }
steps:
  - crop-square: { anchor: center }
  - resize: { width: "{{ size }}", height: "{{ size }}" }
  - convert: { format: webp, quality: 85 }
```

Discovery order: `./.pifang/recipes/` → `~/.config/pifang/recipes/` → package `recipes/builtin/`. One malformed custom YAML is skipped with a warning; other recipes still load.

---

## Python library surface

```python
from pifang.errors import PifangError, ValidationError, ProcessingError
from pifang.core.result import OpResult
from pifang.core.recipe import load_recipes, run_recipe
from pifang.core.pipe import parse_image_pipe, run_image_pipe
from pifang.core.video_pipe import parse_video_pipe, run_video_pipe
from pifang.core.batch import batch_run, BatchSpec
from pifang.domains.image import ops
```

CLI and library call the same domain functions.

---

## Projection map

| Operation | CLI | Python SDK | MCP |
|---|---|---|---|
| `image.resize` | `pifang image resize` | `ops.resize()` | deferred |
| `image.avatar` | `pifang image avatar` | `run_recipe("avatar")` | deferred |
| `batch.run.image` | `pifang batch run image` | `batch_run(BatchSpec(domain="image", …))` | deferred |
| `batch.run.video` | `pifang batch run video` | `batch_run(BatchSpec(domain="video", …))` | deferred |
| `pipe.video` | `pifang pipe video` | `run_video_pipe(…)` | deferred |
| `transcribe` | `pifang transcribe` | `transcribe_media(…)` | deferred |

Single implementation in `domains/`; CLI and library share it.
