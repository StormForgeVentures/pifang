# Glossary

Project vocabulary for contributors and agents. Keep it short and current.

### Atom
- **Means:** A single CLI operation with a fixed flag contract (e.g. `pifang image resize`).
- **Aliases:** command, subcommand
- **Not:** A recipe or pipe chain

### Recipe
- **Means:** A named multi-step pipeline built from atoms, with override knobs (e.g. `pifang image avatar`).
- **Aliases:** preset, macro
- **Not:** A user Python script

### Pipe DSL
- **Means:** Inline stage chain syntax (e.g. `crop-square | resize 256 | to-webp`) parsed into atom calls.
- **Aliases:** pipe, pipeline
- **Not:** Unix shell pipe to another process

### Manifest
- **Means:** JSONL file listing inputs, outputs, operations applied, timing, and errors for batch/pipe runs.
- **Aliases:** ingest.jsonl, batch manifest
- **Not:** The PDF engine's internal JSON (though pifang may reference it)

### Engine (doc)
- **Means:** Delegated PDF parser backend selected via `--engine` (default: `fast` / pymupdf4llm).
- **Aliases:** backend, parser
- **Not:** Pifang's own PDF implementation

### Pack
- **Means:** Multi-output pipeline that analyzes source dimensions then exports all platform targets (e.g. `social-pack`, `video-cover-pack`).
- **Aliases:** platform pack, social export
- **Not:** A single atom or single-recipe call

### Fit quality
- **Means:** How well source aspect ratio matches a target: `ideal`, `good`, or `heavy_crop`.
- **Aliases:** crop severity
- **Not:** JPEG quality

### remove-bg / flatten-bg / recolor
- **remove-bg:** strips a background → transparent PNG. Modes: `white|black|auto|color|checker` (default `auto`).
- **flatten-bg:** fills **transparent** pixels with a solid color; foreground unchanged.
- **recolor:** changes **foreground** pixels to one color (white/black/hex); **transparency preserved**.
- **Not:** AI segmentation; recolor does not fill transparent areas (use flatten-bg for that).

## Actors / roles

- **Agent** — primary caller; expects JSON stdout always (one object), stable exit codes, no stderr parsing.
- **Operator** — a person who runs pipelines locally, verifies via `doctor` and copy-paste examples.
- **Downstream pipeline** — RAG indexer or vision LLM; consumes markdown + images folder + manifest.

## Key entities

- **Job** — one CLI invocation (single file or batch).
- **Stage** — one atom step inside a recipe or pipe.
- **Ingest bundle** — `{name}.md` + `{name}_images/` (+ optional JSON) produced by doc ingest.
- **Chunk manifest** — `{stem}-chunks.jsonl` listing RAG chunk files from `text chunk`.
- **Corpus index** — `index.jsonl` from `meta index` mapping markdown stems to image dirs.
- **Recipe file** — YAML in `./.pifang/recipes/` or `~/.config/pifang/recipes/`.
