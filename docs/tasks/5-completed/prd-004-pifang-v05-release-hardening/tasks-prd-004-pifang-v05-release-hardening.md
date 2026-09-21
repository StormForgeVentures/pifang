# Tasks — Pifang v0.5 (Release Hardening)

**Status:** Completed 2026-07-16 (all 46 tasks; verified 2026-09-21 — 121 tests pass). Source PRD: `prd-004-pifang-v05-release-hardening.md` (this folder). Wave plan: `handoff/wave-plan-v05.md` (local, untracked).

## Relevant Files

- `src/pifang/cli/main.py` — handler exception wrapper, flag moves, enums, `--version`
- `src/pifang/core/pipe.py`, `core/video_pipe.py` — DSL strictness, temp cleanup
- `src/pifang/core/recipe.py` — malformed-YAML isolation, temp cleanup
- `src/pifang/core/batch.py` — accounting, inline first-error, domain label
- `src/pifang/core/output.py` — `ensure_ascii=False`
- `src/pifang/core/setup_deps.py` — pip timeout
- `src/pifang/domains/image/ops.py` — validation, compress fix, skip metadata
- `src/pifang/domains/image/bg.py`, `image/recolor.py` — pixel-loop perf
- `src/pifang/domains/video/ops.py`, `video/ffmpeg.py` — quote escaping, timeouts
- `src/pifang/domains/doc/pdf_ops.py`, `doc/info.py`, `doc/engines.py`, `doc/ocr.py`, `doc/ingest.py` — PDF errors, timeouts, resume warnings
- `src/pifang/domains/meta/index.py` — manifest line errors
- `skills/pifang/SKILL.md`, `docs/agents-blurb.md`, `docs/glossary.md`, `docs/api-design.md`, `README.md`
- `pyproject.toml` — sdist include list, classifier
- `tests/` — regression tests per AC

## Tasks

### Track A — CLI contract (Wave 1)

- [x] 1.0 Exception fallback + first-class errors (maps to: AC-v05-01, AC-v05-02)
  - [x] 1.1 Shared handler wrapper/decorator in `cli/main.py`: any non-`PifangError` → JSON envelope `error_code:"INTERNAL"`, exit 3; traceback to stderr only under `--verbose`; apply to all 45 handlers
  - [x] 1.2 Validate width/height > 0 before Pillow calls (resize/crop/fit) → exit 1
  - [x] 1.3 `image convert`: unknown format → validation error listing supported formats (fix `ops.py:61-70` KeyError path)
  - [x] 1.4 `image fit --color`: catch `ImageColor` ValueError → validation error
  - [x] 1.5 Catch `PIL.Image.DecompressionBombError` → processing error, exit 3
  - [x] 1.6 `doc info`/`doc split`: wrap `PdfReader` errors → processing error
  - [x] 1.7 `meta validate`: bad JSONL line → validation error with line number
  - [x] 1.8 `core/recipe.py`: one malformed custom recipe skips that file with stderr warning + `warnings` field; direct run of the broken recipe errors cleanly; other recipes unaffected
  - [x] 1.9 `image compress`: fix `UnboundLocalError` for quality ≤ 9 with `--max-kb`; validate quality 1–100

- [x] 2.0 Output mode + flag ergonomics (maps to: AC-v05-03, AC-v05-04, AC-v05-14)
  - [x] 2.1 Remove root `--json/--human`; delete `emit_human`/dict-repr path in `_finish`
  - [x] 2.2 Hidden no-op `--json` accepted on every subcommand
  - [x] 2.3 Shared params helper registering `--force`/`--dry-run`/`--verbose` on mutating subcommands (trailing position works; shows in leaf `--help`)
  - [x] 2.4 Root `--version` flag
  - [x] 2.5 Scrub `--json`/`--human` from README, agents-blurb, SKILL.md, oss-prepublic-checklist, publishing.md, glossary (non-archived docs only)

- [x] 3.0 Silent-failure fixes (maps to: AC-v05-05, AC-v05-06, AC-v05-07, AC-v05-08)
  - [x] 3.1 Enum types for `--fit`, `--anchor`; sweep `main.py` for every other closed-set `str` param and convert
  - [x] 3.2 Pipe DSL: reject stray/unparsed tokens in a stage (image + video pipes); fix `pipe.py:66` compress arg parse
  - [x] 3.3 Skip-path metadata reads existing output file (all ops with skip logic)
  - [x] 3.4 Batch: `total == succeeded + failed + skipped + not_attempted`; first error inline in top-level JSON; `batch.{domain}.*` labels (fix `batch.py:149`)

### Track B — Domain robustness (Wave 1, parallel with Track A)

- [x] 4.0 Subprocess + filesystem hygiene (maps to: AC-v05-09, AC-v05-10, AC-v05-11)
  - [x] 4.1 Timeouts on all `subprocess.run` calls (probes 30s; long jobs generous default + `--timeout` override where it bites); `SUBPROCESS_TIMEOUT` error, exit 3
  - [x] 4.2 ffmpeg concat list escaping for `'` in filenames (`video/ops.py:171`); subtitles filter-graph escaping (`video/ops.py:318-319`); tests with apostrophe filenames
  - [x] 4.3 Temp cleanup in `finally` for pipe/recipe/video-pipe failure paths
  - [x] 4.4 `remove-bg`/`recolor`: replace per-pixel loops with Pillow C-level ops (target ≤ ~2s @ 24MP) OR emit periodic `--verbose` progress + help-text warning
  - [x] 4.5 `emit_json(..., ensure_ascii=False)`
  - [x] 4.6 `doc ingest` resume: warn (stderr + `warnings` field) on corrupt JSONL lines with line numbers

### Wave 2 — Docs + packaging (after Wave 1 merges)

- [x] 5.0 AX docs sync (maps to: AC-v05-12)
  - [x] 5.1 SKILL.md Rule 4: `-o` is a directory for convert/ingest/split/extract-images; a FILE path for ocr/merge
  - [x] 5.2 Glossary `remove-bg` modes → `white|black|auto|color|checker`, default `auto`
  - [x] 5.3 SKILL.md additions: JSON success/error envelope examples, exit-code table, pipe DSL grammar/stage table, batch semantics (`--jobs`, `--continue-on-error`, manifest line shape, exit 4), discovery commands (`recipe list`, group map)
  - [x] 5.4 api-design.md: regenerate full command tree (doc/video/audio/transcribe/text/meta/setup/packs/video-pipe/batch-video; fix stale `batch run` syntax) or demote from README reference
  - [x] 5.5 Add `pipe video` + `batch run video` examples to README/SKILL/agents-blurb
  - [x] 5.6 One-line help descriptions for all bare `image` subcommands
  - [x] 5.7 README quickstart: zero-extra image command first; verify "Built for agents" marketing section claims all hold post-Wave-1
- [x] 6.0 Packaging polish (maps to: AC-v05-13, AC-v05-14)
  - [x] 6.1 pyproject sdist include: curated docs list; exclude docs/tasks, docs/archive, oss-prepublic-checklist.md, publishing.md
  - [x] 6.2 README links absolute (GitHub blob URLs) for PyPI rendering
  - [x] 6.3 License classifier decision + CHANGELOG note
  - [x] 6.4 CHANGELOG 0.1.0 entry updated for this wave

### Wave 3 — Verification (after Wave 2)

- [x] 7.0 Regression + release re-verification (maps to: AC-v05-15, AC-v05-01…14)
  - [x] 7.1 Regression tests: every AC-v05-01 trigger, enum rejection, DSL strictness, skip metadata, batch accounting, apostrophe filenames, temp cleanup
  - [x] 7.2 Scripted doc-example check: run every README/SKILL/agents-blurb command verbatim against a fresh wheel install in CI (or a `tests/test_docs_examples.py`)
  - [x] 7.3 Rebuild sdist+wheel; `twine check`; inspect sdist contents (no internal docs); clean-venv no-extras install smoke (`version`, `--version`, `doctor`, image op, doc/transcribe graceful failures)
  - [x] 7.4 Full `pytest` green

**Waves:** 1 (Tracks A ∥ B) → 2 (5.0 ∥ 6.0) → 3 (serial). File ownership between Tracks A/B is disjoint — see wave plan.
