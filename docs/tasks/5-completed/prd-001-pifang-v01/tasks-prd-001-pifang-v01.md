# Tasks — Pifang v0.1

**Status:** Completed (archived). Historical checklist from the private build wave.

## Relevant Files

- `pyproject.toml` — package config
- `src/pifang/` — library + CLI
- `tests/` — pytest suite
- `examples/` — quickstart scripts

## Tasks

- [ ] 1.0 Project scaffold (maps to: AC-v01-01)
  - [ ] 1.1 pyproject.toml, hatchling, typer, pillow deps
  - [ ] 1.2 Package layout src/pifang with errors, output helpers
  - [ ] 1.3 Apache-2.0 LICENSE, README skeleton

- [ ] 2.0 Image domain + library (maps to: AC-v01-02, AC-v01-07)
  - [ ] 2.1 Image ops: resize, crop, crop-square, fit, convert, compress, strip-exif, info, thumbnail
  - [ ] 2.2 OpResult + idempotent skip unless --force

- [ ] 3.0 Composition layer (maps to: AC-v01-03, AC-v01-05)
  - [ ] 3.1 Recipe loader + builtin YAML (avatar, hero, social-square)
  - [ ] 3.2 Pipe DSL parser + executor
  - [ ] 3.3 Custom recipe discovery paths

- [ ] 4.0 Batch + manifest (maps to: AC-v01-04, AC-v01-06)
  - [ ] 4.1 Folder walk, glob, parallel jobs
  - [ ] 4.2 JSONL manifest writer, partial failure exit 4

- [ ] 5.0 CLI surface (maps to: all AC)
  - [ ] 5.1 Typer app: global flags, doctor, version, recipe, image, pipe, batch
  - [ ] 5.2 JSON/human output routing

- [ ] 6.0 Verification (maps to: all AC)
  - [ ] 6.1 pytest with fixture images
  - [ ] 6.2 CLI integration tests via subprocess
  - [ ] 6.3 examples/quickstart.py runnable

**Wave 1:** 1.0 → 2.0 → 3.0 → 4.0 → 5.0 → 6.0 (serial, shared abstractions)
