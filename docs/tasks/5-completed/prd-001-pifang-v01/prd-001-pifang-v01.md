---
type: prd
id: prd-001
slug: pifang-v01
owner: pkg-developer
verifier: pm-triage-2026-09-21
created: 2026-09-21
priority: 
submitter: 
blocked_ask:
---

> **Superseded (2026-09-21):** the output-mode decision in this PRD was replaced — plain text is the default and `--json` (root or any subcommand) is the agent contract; `--human` is removed. See `docs/api-design.md`.

# PRD — Pifang v0.1 (Image MVP)

**Status:** Approved  
**Source:** `docs/project-brief.md`, `docs/api-design.md`

## Overview & goals

Pifang v0.1 ships an agent-first Python CLI and library for deterministic image processing: resize, crop, convert, named recipes, pipe DSL, and folder batch with JSONL manifests. Success means agents invoke `pifang image avatar … --json` and folder batch without writing custom Python.

## Personas

Agent (primary), operator, downstream RAG/vision pipeline.

## P0 — v0.1 functional requirements

### Global contract
- JSON stdout by default; `--human` for operator-readable output
- Exit codes 0–4 per api-design
- `--dry-run`, `--force`, `--verbose` on all mutating commands
- Layered `--help` via Typer command groups

### Image atoms
- resize, crop, crop-square, fit, convert, compress, strip-exif, info, thumbnail

### Recipes
- Built-in: avatar, hero, social-square
- Custom YAML in `./.pifang/recipes/` and `~/.config/pifang/recipes/`
- `pifang recipe list --json`

### Composition
- `pifang pipe image "…" INPUT -o OUT`
- Same executor as atoms/recipes

### Batch
- `pifang batch run image <command> PATH -o OUT_DIR`
- `--glob`, `--recursive`, `--jobs`, `--manifest`, `--continue-on-error`

### Doctor
- Verify Pillow; report version; exit 2 if missing

## Non-goals (v0.1)

Doc ingest, video, audio, plugins, MCP, pyvips `[fast]` extra.

## P0 acceptance criteria

| ID | Criterion |
|---|---|
| AC-v01-01 | Given Pillow installed, when `pifang doctor`, then exit 0 and JSON/human reports Pillow version |
| AC-v01-02 | Given valid JPEG, when `pifang image avatar photo.jpg -o out.webp --size 512 --json`, then exit 0, stdout JSON has ok=true, output 512×512 webp |
| AC-v01-03 | Given same input, when pipe `crop-square \| resize 512 \| to-webp`, then output matches avatar recipe |
| AC-v01-04 | Given folder of JPGs, when `pifang batch run image convert photos/ -o out/ --format webp --manifest m.jsonl`, then all converted and manifest has one line per file |
| AC-v01-05 | Given YAML in `~/.config/pifang/recipes/`, when `pifang recipe list --json`, then custom recipe appears |
| AC-v01-06 | Given any P0 command, when `--dry-run`, then no output file written and stdout indicates planned action |
| AC-v01-07 | Given missing input file, when any image command, then exit 1 and JSON error envelope |

## Implementation priority

Wave 1 (single wave): scaffold → core → image → CLI → tests → docs.
