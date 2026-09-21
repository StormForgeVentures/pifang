# Domain context

> Living glossary for this project. roster scaffolds it once and never overwrites it. Agents read it
> to use the project's own vocabulary instead of inventing synonyms. Full definitions live in
> [`docs/glossary.md`](docs/glossary.md); this file pins the handful of terms agents most often get wrong.

## Glossary

### Atom
- **Means:** one primitive operation on one file (`image resize`, `video trim`, `doc split`)
- **Not:** a recipe or a pipe stage, though recipes and pipes are built from atoms

### Recipe
- **Means:** a named, YAML-defined sequence of atoms with parameters (`avatar`, `hero`, `social-clip`); built-in under `src/pifang/recipes/builtin/`, custom under `./.pifang/recipes/` or `~/.config/pifang/recipes/`
- **Aliases:** preset (avoid)

### Pipe
- **Means:** an inline chain of stages given on the command line, `"crop-square | resize 512 | to-webp q85"`; same atoms as recipes, no YAML
- **Aliases:** pipe DSL, stages

### Pack
- **Means:** a batch of platform-sized exports from one image (`social-pack`, `blog-pack`, `podcast-pack`, `video-cover-pack`, `custom-pack`)

### Manifest
- **Means:** the JSONL record a batch or ingest run writes, one line per input (`ingest.jsonl`); merged by resolved input path across runs
- **Not:** the doc engine's own JSON output

### Engine
- **Means:** a delegated backend pifang wraps rather than reimplements: doc engines `fast` (pymupdf4llm, default) · `opendataloader` · `marker` · `docling`; transcription via Faster-Whisper; video via ffmpeg

### Output contract
- **Means:** plain text on stdout by default; with `--json`, exactly one JSON object on stdout (success or error envelope); exit codes 0 ok · 1 validation · 2 missing dep · 3 processing · 4 partial batch

## Actors / roles

- **Agent** — primary caller; passes `--json`, parses stdout, honors exit codes, never parses stderr
- **Operator** — a person at a terminal; reads the text output, runs `pifang doctor`

## Key entities

- **Input / output path** — every mutating command takes one input (or a folder for batch/ingest) and `-o`; doc commands' `-o` is always a directory
- **Result envelope** — `ok`, `command`, `input`, `output`, `result`, `duration_ms` on success; `ok: false`, `error_code`, `message`, `exit_code`, `recovery.hint` on error
