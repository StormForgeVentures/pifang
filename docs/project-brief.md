# Project Brief — Pifang

**Status:** Approved (plan gate 2026-06-27)  
**Stage:** production (quality bar; phased delivery)  
**Workflow:** pkg-build  
**Owner:** StormForge Ventures

---

## What & why

**Pifang** is an agent-first Python CLI for deterministic media and document processing. AI agents repeatedly reinvent one-off scripts for image resize/crop, ffmpeg transcodes, PDF-to-markdown ingestion, and folder batch jobs. Pifang replaces that improvisation with stable commands, predictable exit codes, JSON output, and manifest files agents can parse without reading stderr.

The long-term purpose is **data ingestion pipelines**: walk a folder of mixed assets, normalize them (images, video, documents), and emit structured outputs (markdown + extracted images, transcoded media, JSONL manifests) ready for RAG or vision-LLM workflows.

Pifang is **not** a general Python script runner. It is a curated toolkit with three composition layers — **atoms** (single operations), **recipes** (named multi-step pipelines), and **pipe DSL** (inline stage chains) — plus a shared **batch runner** for folder-scale work.

---

## Users & personas

| Persona | Role | Success looks like |
|---|---|---|
| **Agent (primary)** | Cursor/Claude Code subagent executing media/doc prep | Calls `pifang … --json`, gets structured stdout + manifest; no custom Python per task |
| **Operator** | Human running pipelines locally (WSL/Linux) | `pifang doctor` passes; copy-paste examples in `--help` work first try |
| **Downstream pipeline** | RAG indexer, vision model, CMS import | Consumes `{doc}.md` + `{doc}_images/` + `ingest.jsonl` without path guessing |

---

## Capability priorities

### P0 — MVP (v0.1)

**Image domain (Pillow backend)**

| Capability | Notes |
|---|---|
| Image resize (aspect-preserving) | `--width`, `--height`, `--fit contain\|cover` |
| Image crop (rect) | `--x`, `--y`, `--width`, `--height` |
| Image crop-square | `--anchor center\|top\|bottom\|left\|right` (default: center) |
| Image fit / letterbox | Pad to exact dimensions |
| Format convert | png, jpg, webp, avif, gif |
| Compress | `--quality`, `--max-kb` |
| Strip EXIF | Metadata removal |
| Image info | JSON: dimensions, format, color mode, EXIF summary |
| Thumbnail | Max-edge resize + optional crop |

**Built-in image recipes**

| Recipe | Pipeline |
|---|---|
| `avatar` | crop-square (center) → resize N×N → webp |
| `hero` | resize cover to WxH → compress to max-kb |
| `social-square` | crop-square → resize → convert |

**Composition (image-only in MVP; shell shared with future domains)**

| Capability | Notes |
|---|---|
| Pipe DSL | e.g. `crop-square \| resize 256 \| to-webp` |
| Recipe registry | Built-in recipes + user YAML in search paths |
| Custom recipe folders | `./.pifang/recipes/` then `~/.config/pifang/recipes/` |
| `recipe list` | Built-in + custom, JSON output |

**Batch**

| Capability | Notes |
|---|---|
| Folder walk | `--glob`, `--recursive`, `--jobs N` |
| Apply atom/recipe/pipe per match | |
| JSONL manifest | input, output, operations, duration, errors |
| `--dry-run`, `--continue-on-error` | |

**Agent contract (global)**

| Capability | Notes |
|---|---|
| JSON stdout by default | Human-readable via `--human` or stderr progress |
| Exit codes | 0 success · 1 validation · 2 missing dep · 3 processing · 4 partial batch |
| Layered `--help` | L0 root → L1 domain → L2 command → L3 recipe (expanded steps) |
| `pifang doctor` | Verify Pillow + report versions |
| Idempotent writes | Skip unchanged unless `--force` |

**CLI**

| Decision | Value |
|---|---|
| Binary name | `pifang` only — **no alias** |
| PyPI package name | `pifang` (available) |

---

### P1 — Document ingestion (v0.2)

Pifang **does not reimplement PDF parsing**. It delegates to pluggable engines and normalizes output for agents.

| Capability | Notes |
|---|---|
| `doc ingest` | Folder or file batch |
| Engine: PyMuPDF4LLM (default) | `--engine fast` — pure Python; simple digital PDFs |
| Engine: OpenDataLoader (optional) | `--engine opendataloader` — needs `pifang[doc-odl]` + JDK 11+ |
| Engine: Marker | `--engine marker` for hard/complex docs |
| Engine: Docling | `--engine docling` |
| Normalized output layout | `{name}.md` + `{name}_images/` + optional `{name}.json` |
| Markdown image refs | Relative paths for vision-LLM pairing |
| `doc info`, `doc extract-images` | Lightweight atoms |
| `doc split` / `doc merge` | Basic PDF ops via pypdf |
| `doc ocr` | Tesseract wrapper for scanned paths |

**Default path is pure Python.** OpenDataLoader stays available as an opt-in engine; `pifang setup` prints JDK/ffmpeg install commands (never auto-installs system packages).

**Post-ingest helpers**

| Capability | Notes |
|---|---|
| `text chunk` | Split markdown by headings/token budget |
| `text frontmatter` | YAML frontmatter from manifest fields |
| `meta index` | JSONL index of processed folder |
| `meta validate` | Manifest completeness vs disk |

---

### P1 — Video (v0.3, ffmpeg-backed)

| Capability | Notes |
|---|---|
| Transcode, trim, extract-audio | |
| Concat, to-gif, extract-frames | |
| Add captions (burn-in or sidecar SRT/VTT) | |
| Normalize audio, resize | |
| `video info` | ffprobe summary as JSON |
| Recipes | e.g. `social-clip`, `podcast-audio` |

`pifang doctor` verifies ffmpeg/ffprobe on PATH.

**Thesis:** video is for **LLM-friendly editing of existing media**, not scene/animation engines. Agents trim, concat, caption, and work from transcripts.

---

### P1 — Transcribe (v0.4, Faster-Whisper)

Shared transcription for **video and audio** — wrapper only (same pattern as OCR / PDF engines).

| Capability | Notes |
|---|---|
| `transcribe` (shared CLI) | Primary surface; `video transcribe` / `audio transcribe` aliases |
| Engine | Faster-Whisper via `pifang[transcribe]` |
| Primary artifact | Timeline JSON: `segments[]` with `start`, `end`, `text` (optional `speaker` later) |
| Interop | Also write SRT (+ optional VTT); existing `video captions` consumes SRT/VTT |
| Video path | ffmpeg extract audio → transcribe → write into `-o` dir |
| Doctor | `pifang doctor --transcribe` |

Out of this wave: diarization UI, live streaming, GPU bundling, cut-from-transcript (follow-on), Revideo/Manim/Remotion, generative image→video.

---

### P2 — Later

| Domain | Examples |
|---|---|
| Audio edit atoms | transcode, trim, concat, normalize (beyond extract/transcribe) |
| Timeline-driven edit | cut/keep segments from transcript JSON |
| Archive / fs | hash, dedupe, zip extract/pack |
| Performance | optional `pifang[fast]` pyvips backend; benchmark spike before changing batch default |
| Light stills→video | Ken Burns / slideshow / hold-frame via ffmpeg (not generative AI) |
| Plugins | `pifang plugin run` — user Python extensions with pinned API |
| MCP server | Expose atoms as agent tools (design only until v1.0) |
| Generative video | Scene engines / image→video models — separate AI track, not core CLI |

---

## Surfaces

| Surface | Shape | Notes |
|---|---|---|
| CLI | Python package, console script `pifang` | Primary and only user-facing surface for MVP |
| Distribution | PyPI (OSS) | `uv tool install pifang` and `pipx install pifang` documented |
| Config | YAML recipes on disk | No config server; no GUI |

---

## Non-goals

| Exclusion | Reason |
|---|---|
| Arbitrary Python script execution (`pifang run script.py`) | Deferred to P2/P3 plugin system; avoids becoming an unsafe eval harness |
| Reimplementing OpenDataLoader / Marker / Docling parsing | Delegate via `--engine`; Pifang owns orchestration and output contract |
| GUI or web UI | CLI-only tool |
| Cloud upload / CDN integration | Out of scope; consumers handle storage |
| LLM inference inside Pifang | OCR/transcription are tool wrappers, not model hosting |
| Real-time streaming video | Batch/file-oriented only |
| Windows-first packaging | Linux/macOS (WSL) first; Windows best-effort later |
| CLI alias (`pf`, `pfang`) | Single command `pifang`; avoids PyPI/PATH collisions (`pf` taken on PyPI) |
| Competing with OpenDataLoader | Optional engine only; default is pure-Python `fast` |

---

## Constraints

| Constraint | Detail |
|---|---|
| Primary consumer | Agents — JSON stdout, stable flags, documented exit codes |
| MVP image backend | Pillow only; pyvips optional later via extras |
| External deps | System tools not bundled — ffmpeg (video/transcribe), Tesseract (OCR optional); Java only if using OpenDataLoader |
| `doctor` command | Must check deps per installed extras and print install instructions |
| Dependency model | Optional PyPI extras: `pifang[doc]`, `pifang[video]`, `pifang[fast]` |
| Composition | Atoms + recipes + pipe DSL from v0.1 (image domain only until v0.2+) |
| Custom recipes | User YAML merges with built-ins; project-local overrides global |
| License | OSS intent — exact license TBD in pkg-classify (recommend MIT or Apache-2.0) |
| Never ship mock | Every command runs real processing; dry-run previews only |

---

## Technical decisions (locked in discovery)

### Distribution

Publish to PyPI as `pifang`. Document:

```bash
uv tool install pifang          # recommended
pipx install pifang             # alternative
```

Private dogfood: install from git URL or private index — same package artifact.

### Image backends

| Phase | Backend | Rationale |
|---|---|---|
| MVP | Pillow | Light install, covers resize/crop/convert/thumbnail |
| v0.2+ | pyvips (optional `[fast]`) | Same engine as Node Sharp; faster batch/large images |

No Node/sharp dependency in the Python CLI.

### PDF engines

| Engine | When | Trade-off |
|---|---|---|
| **PyMuPDF4LLM** (default) | Fast digital PDFs, pure Python | Default agent path |
| **OpenDataLoader** (optional) | RAG ingestion, images + markdown + bboxes | Requires Java 11+ + `pifang[doc-odl]` |
| Marker | Complex layout, equations, multi-format | Heavy ML deps |
| Docling | Alternative/hybrid paths | Medium weight; used by ODL hybrid mode |
| PyMuPDF4LLM | Simple digital PDFs | Fast, light, weaker on scans |

Normalized ingest output:

```
output/
  report.md
  report_images/
  report.json          # optional, engine-dependent
  ingest.jsonl         # pifang manifest
```

### Recipe discovery order

1. `./.pifang/recipes/*.yaml` (project)
2. `~/.config/pifang/recipes/*.yaml` (user)
3. Built-in recipes (package)

---

## Success criteria

### v0.1 acceptance (MVP)

1. `pifang doctor` passes with Pillow; exits 2 with clear message if missing.
2. `pifang image avatar photo.jpg --size 512 -o out/photo.webp --json` emits JSON result on stdout.
3. Pipe DSL produces identical output to the `avatar` recipe for the same inputs.
4. `pifang batch run image convert ./photos/ --to webp --manifest out.jsonl` processes a real folder.
5. Custom recipe in `~/.config/pifang/recipes/` appears in `pifang recipe list --json`.
6. Every P0 command supports `--dry-run` and documented exit codes.
7. Help at root, domain, and command levels includes copy-paste examples.

### v0.2 acceptance (doc ingestion)

1. `pifang doc ingest ./corpus/` (default `fast`) produces markdown + `_images/` per PDF.
2. Manifest JSONL lists all outputs; agent can parse without stderr.
3. `pifang doctor` with `[doc]` extra verifies Java 11+.

### Product success (v1.0)

Agents in the maintainers' projects prefer `pifang` over ad-hoc Python for covered operations; zero custom scripts needed for avatar crop, folder webp convert, and PDF corpus ingest.

---

## Phasing

| Version | Ships | Gate |
|---|---|---|
| **0.1** | Image atoms, recipes, pipe, batch, doctor, JSON contract, custom recipes | Operator runs avatar + batch on real photos |
| **0.2** | Doc ingest (`fast` default; ODL optional), chunk/index helpers | Operator ingests a PDF corpus |
| **0.3** | Video atoms + ffmpeg doctor | Operator runs transcode + captions on one clip |
| **0.4** | Transcribe (Faster-Whisper) for video + audio; JSON timeline + SRT | Operator smokes one video + one audio → JSON + SRT |
| **1.0** | Semver-stable API, full help layers, OSS PyPI publish | Agent team dogfoods across projects |

---

## Next steps (post brief approval)

1. **pkg-classify** — archetype, shape (CLI), 7-knob interview (license, error model, distribution tier, etc.)
2. **pkg-api-design** — command tree, JSON schemas, exit codes, recipe YAML spec
3. **prd** + **generate-tasks** — vertical slices for v0.1
4. **Build v0.1** — pkg-developer
