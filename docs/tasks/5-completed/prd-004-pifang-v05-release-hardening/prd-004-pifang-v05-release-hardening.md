---
type: prd
id: prd-004
slug: pifang-v05-release-hardening
owner: pkg-developer
verifier: pm-triage-2026-09-21
created: 2026-09-21
priority: 
submitter: 
blocked_ask:
---

> **Superseded (2026-09-21):** the output-mode decision in this PRD was replaced — plain text is the default and `--json` (root or any subcommand) is the agent contract; `--human` is removed. See `docs/api-design.md`.

# PRD — Pifang v0.5 (Release Hardening)

**Status:** Approved for build (plan gate: maintainer, 2026-07-16)
**Source:** Pre-PyPI four-track audit (CLI hands-on, source review, docs/AX cross-check, packaging build test), 2026-07-16.
**Goal:** Close every gap between pifang's agent-first promise and its actual behavior before the first PyPI upload. Scope is the FULL audit list — launch-gating and non-gating alike; everything ships in this wave.

## Overview

The audit confirmed the design is right (JSON stdout, error envelope with recovery hints, exit codes 0–4, dry-run, lazy optional deps) but found: (a) ~7 verified code paths that break the "stdout is always JSON" contract with raw tracebacks and empty stdout, (b) silent wrong-answer paths (unvalidated enums, pipe-DSL typos that succeed, skip responses reporting source dimensions), (c) a broken and redundant `--json/--human` flag pair that also breaks every README example, and (d) docs/packaging drift. All fixes are mechanical; no architecture changes.

## Personas

Agent (primary — parses stdout programmatically, learns the CLI from `--help` and SKILL.md), operator.

## Design decisions (binding)

1. **Single output mode.** Remove the root `--json/--human` option pair entirely. stdout is always exactly one JSON object. The `--human` formatting path (`_finish`/`emit_human` printing Python dict repr) is deleted. A hidden, accepted-and-ignored `--json` no-op flag IS added to every subcommand so agents with habits from other CLIs (`gh`, `aws`) don't error.
2. **Per-subcommand global flags.** `--force`, `--dry-run`, `--verbose` move onto the subcommands that use them (shared params helper to avoid repetition) so they work in trailing position and appear in each leaf `--help`. Root-level versions may remain for back-compat but leaf registration is the contract.
3. **No framework change.** Stay on Typer. All fixes are validation/error-handling inside pifang.
4. **Fail loud, never fall back.** Any string parameter with a closed value set becomes a real enum/Choice. Any unparseable DSL input is an error, never a silent partial run.
5. **Unexpected exceptions still emit the envelope.** A last-resort handler converts any non-`PifangError` exception into the standard JSON error envelope (`error_code: "INTERNAL"`, exit 3, exception class + message included; traceback to stderr only under `--verbose`). Known trigger paths listed below additionally get proper first-class validation/processing errors.

## P0 — Functional requirements

### R1 — JSON contract hardening (audit blockers)

- **R1.1 Global exception fallback.** Every CLI handler currently does `except PifangError` only (45 occurrences in `src/pifang/cli/main.py`). Add a shared wrapper/decorator so ANY exception produces the JSON envelope per design decision 5. Verified trigger paths that must each ALSO get a first-class error (not just the INTERNAL fallback):
  - Negative/zero `--width`/`--height` on `image resize`/`crop` → validation error, exit 1 (currently raw Pillow `ValueError`, empty stdout; `src/pifang/domains/image/ops.py:148` area).
  - Unknown `--format` on `image convert` → validation error listing supported formats (currently `KeyError` from Pillow save; `ops.py:61-70` catches only `OSError`).
  - Invalid `--color` on `image fit` → validation error (Pillow `ImageColor` `ValueError`).
  - Decompression-bomb PNG → processing error, exit 3 (`PIL.Image.DecompressionBombError` is not an `OSError`; `ops.py:28-36`).
  - Corrupt/truncated PDF in `doc info`/`doc split` → processing error (`pypdf.errors.PdfStreamError` uncaught; `src/pifang/domains/doc/pdf_ops.py`, `doc/info.py:21`).
  - Non-JSON line in `meta validate` manifest → validation error naming the line number (`src/pifang/domains/meta/index.py:50`).
  - Malformed YAML in ONE custom recipe file must not break all recipe commands: skip the bad file, warn on stderr, include it in a `warnings` field; a direct run of the broken recipe errors cleanly (`src/pifang/core/recipe.py:41`, eager `load_recipes()`).
- **R1.2 `image compress` crash.** `--max-kb` with `--quality` ≤ 9 hits `UnboundLocalError` (`for q in range(quality, 9, -5)` is empty; `ops.py:377-385`). Fix loop so `buf` always exists; validate quality range 1–100.

### R2 — Output-mode simplification & flag ergonomics

- **R2.1** Remove `--json/--human` per design decision 1; add hidden no-op `--json` on subcommands.
- **R2.2** Register `--force`/`--dry-run`/`--verbose` on subcommands per design decision 2.
- **R2.3** Add root `--version` flag (alias of the `version` subcommand).
- **R2.4** Scrub `--json`/`--human` from ALL docs and examples: `README.md`, `docs/agents-blurb.md`, `skills/pifang/SKILL.md`, `docs/oss-prepublic-checklist.md`, `docs/publishing.md`, `docs/glossary.md`, PRD acceptance snippets are historical — leave archived docs alone.

### R3 — Silent-failure fixes (validation & truthful reporting)

- **R3.1 Enum validation.** `--fit` (`contain|cover`), `--anchor` (`center|top|bottom|left|right` — confirm actual set from `ops.py`), and every other closed-set `str` param in `main.py` (audit found `main.py:206,239,856`; sweep all commands) become Typer enums so bad values exit 1 listing valid choices. Help text shows the value set (pattern to copy: `remove-bg --mode`).
- **R3.2 Pipe DSL strictness.** A stage with trailing unrecognized tokens (e.g. `"resize 512 to-webp"`, missing `|`) must error (`INVALID_PIPE_STAGE` or similar), never silently drop tokens (`src/pifang/core/pipe.py`). Also fix the fragile `compress` arg parse (`pipe.py:66`, dead `" " in t` branch). Same grammar strictness for `pipe video` (`core/video_pipe.py`).
- **R3.3 Truthful skip metadata.** Skip-if-unchanged responses must report the EXISTING OUTPUT file's dimensions/bytes, not the source image's (`ops.py:136-138` loads the input for metadata). Applies to every op with skip logic.
- **R3.4 Batch accounting.** On early stop (`continue_on_error=False`), `total` ≠ `succeeded + failed` and unattempted files vanish (`src/pifang/core/batch.py:156-171`). Add explicit accounting so `total == succeeded + failed + skipped + not_attempted`. Surface at least the first failure's `error_code`/`message` inline in the top-level batch JSON even without `--manifest`. Fix hardcoded `command=f"batch.image.{spec.command}"` mislabeling video batches (`batch.py:149`) → use `spec.domain`.

### R4 — Robustness (audit "worth fixing" — all in scope)

- **R4.1 Subprocess timeouts.** Add `timeout=` to every `subprocess.run`: `src/pifang/domains/video/ffmpeg.py:37,45`, `src/pifang/domains/doc/engines.py:156,244`, `src/pifang/domains/doc/ocr.py:37`, `src/pifang/core/setup_deps.py:88`. Short probes (ffprobe, `java -version`): 30s. Long jobs (ffmpeg transcode, marker, pip install): generous default (e.g. 1h) + `--timeout` override on the relevant commands. Timeout → structured error (`SUBPROCESS_TIMEOUT`), exit 3.
- **R4.2 ffmpeg quote escaping.** Filenames containing `'` break the concat list (`src/pifang/domains/video/ops.py:171` — use ffmpeg concat-format escaping `'\''`) and the subtitles filter for `captions --burn-in` (`ops.py:318-319` — escape `'` in the filter-graph string). Add tests with `o'brien.mp4`-style names.
- **R4.3 Temp-file cleanup on failure.** Failed multi-stage pipe/recipe runs leak `.pifang-pipe-*` intermediates: cleanup must run in `finally` (`core/pipe.py:112-114`, `core/recipe.py:233-234`, `core/video_pipe.py:113-115`).
- **R4.4 Per-pixel loop performance.** `remove-bg` and `recolor` use pure-Python nested pixel loops (~6s at 24MP, no progress; `src/pifang/domains/image/bg.py:97-108`, `src/pifang/domains/image/recolor.py:53-57`). Rework with Pillow C-level ops (`point`/`getdata`/channel math) where feasible; acceptance: 24MP image ≤ ~2s OR `--verbose` emits periodic progress AND help text warns about large images.
- **R4.5 JSON output readability.** `emit_json` uses default `ensure_ascii` — non-ASCII filenames become `\uXXXX` (`src/pifang/core/output.py:10`). Use `ensure_ascii=False`.
- **R4.6 Ingest resume warnings.** `doc ingest` silently drops corrupt JSONL lines on resume (`src/pifang/domains/doc/ingest.py:104-107`) — emit a warning (stderr + `warnings` field) with the line number.

### R5 — Docs / AX sync (the AI training materials)

- **R5.1 SKILL.md Rule 4 fix (audit blocker).** "Doc `-o` is always an output directory" is FALSE for `doc ocr` (file path; `main.py:1114`, `domains/doc/ocr.py:47-49`) and `doc merge` (file path; `main.py:1086`, `pdf_ops.py:39,54`). Scope the rule to `convert`/`ingest`/`split`/`extract-images`; call out `ocr`/`merge` explicitly.
- **R5.2 Glossary fix.** `remove-bg` modes are `white|black|auto|color|checker` (default `auto`) — glossary says "white, black, solid, checker" (`docs/glossary.md:41`).
- **R5.3 SKILL.md teaches the contract.** Add directly to SKILL.md: (a) the success and error JSON envelope shapes (`ok`, `error_code`, `message`, `recovery.hint`, exit code mapping), (b) the full pipe DSL grammar/stage table, (c) batch semantics (`--jobs`, `--continue-on-error`, manifest JSONL line shape, exit 4), (d) discovery commands (`pifang recipe list`, top-level `--help` group map). Keep it tight — it's a context-budget artifact.
- **R5.4 api-design.md.** Regenerate the command tree to cover doc/video/audio/transcribe/text/meta/setup + packs + video pipe + batch-run-video (currently ~70% of the surface is missing, and `batch run` syntax is stale), or demote it to a design-history doc and stop linking it from README as the reference.
- **R5.5 Coverage of real capabilities.** `pipe video "..."` and `batch run video <cmd>` exist but appear in no doc — add to README/SKILL/agents-blurb cheat sheets.
- **R5.6 Help-text completeness.** Every `image` subcommand gets a one-line description (currently `resize`, `crop`, `crop-square`, `fit`, `convert`, `compress`, `strip-exif`, `avatar`, `hero`, `social-square` have none in the group listing). Enum value sets in help come free from R3.1.
- **R5.7 README quickstart TTFS.** Reorder so the first command succeeds on a zero-extra install (an `image` command), before `doctor --doc --video --transcribe`. (Marketing copy for the agent-first contract was added to README at plan time — verify every claim in that section is true after this wave and adjust if any is not.)

### R6 — Packaging / release polish

- **R6.1 Trim the sdist.** Replace the bare `"docs"` entry in `[tool.hatch.build.targets.sdist]` with a curated list (`docs/project-brief.md`, `docs/glossary.md`, `docs/agents-blurb.md`, `docs/out-of-scope.md`, `docs/pkg-classification.md`, `docs/api-design.md` post-R5.4). Internal files must NOT ship: `docs/tasks/`, `docs/archive/`, `docs/oss-prepublic-checklist.md`, `docs/publishing.md`.
- **R6.2 README links.** All relative links (LICENSE badge target, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, CHANGELOG, docs/*, skills/*) become absolute `https://github.com/StormForgeVentures/pifang/blob/main/...` URLs so they work on the PyPI page.
- **R6.3 (nit)** Drop the redundant `License :: OSI Approved ::` classifier (SPDX `license` field already present), or consciously keep it — either way note the decision in CHANGELOG.
- **R6.4** CHANGELOG entry for 0.1.0 updated to reflect this wave (still releases as 0.1.0 — never published).

## Non-goals

- No framework migration off Typer/Click.
- No new commands or domains; no MCP server.
- No `--human` replacement formatter in this wave (may return later as a real feature).
- No Windows CI matrix (track separately).

## P0 acceptance criteria

| ID | Criterion |
|---|---|
| AC-v05-01 | For EVERY audit trigger (negative width, unknown format, bad color, bomb PNG, corrupt PDF, bad manifest line, malformed custom recipe, compress quality<10): stdout is exactly one JSON error envelope with `error_code` + `recovery.hint`, exit code ∈ {1,2,3}, no traceback on stdout |
| AC-v05-02 | Any uncontemplated exception still yields the JSON envelope (`error_code: "INTERNAL"`, exit 3); traceback only on stderr with `--verbose` |
| AC-v05-03 | `--json`/`--human` root options are gone; stdout is JSON always; trailing `--json` on any subcommand is accepted as a no-op |
| AC-v05-04 | `--force`, `--dry-run`, `--verbose` work in trailing position on every mutating subcommand and appear in that subcommand's `--help` |
| AC-v05-05 | `--fit bogus` / `--anchor bogus` (and all closed-set params) exit 1 listing valid values; valid sets visible in `--help` |
| AC-v05-06 | `pipe image "resize 512 to-webp"` (missing `\|`) errors; no silent stage drop; same for `pipe video` |
| AC-v05-07 | Skip-if-unchanged JSON reports the existing OUTPUT file's width/height/bytes (verified against disk) |
| AC-v05-08 | Batch early-stop: `total == succeeded + failed + skipped + not_attempted`; top-level JSON carries first failure's error_code/message without `--manifest`; video batch rows labeled `batch.video.*` |
| AC-v05-09 | Every subprocess call has a timeout; a forced timeout returns a structured JSON error, exit 3 |
| AC-v05-10 | `video concat` and `video captions --burn-in` succeed with `o'brien clip.mp4` / `o'brien.srt` filenames |
| AC-v05-11 | A failed multi-stage pipe/recipe leaves zero `.pifang-pipe-*`/temp intermediates on disk |
| AC-v05-12 | Every command/flag/example in README, SKILL.md, agents-blurb.md, glossary.md executes successfully verbatim on a fresh wheel install (scripted doc-example check in CI or tests) |
| AC-v05-13 | Built sdist contains no `docs/tasks/`, `docs/archive/`, `oss-prepublic-checklist.md`, `publishing.md`; `twine check` passes |
| AC-v05-14 | `pifang --version` prints version; README PyPI page has no dead relative links |
| AC-v05-15 | Full test suite green; new regression tests exist for AC-01, 05, 06, 07, 08, 10, 11 |

## Implementation priority

Wave plan: `handoff/wave-plan-v05.md`. Track A (CLI contract: R1–R3) and Track B (domain robustness: R4) run in parallel — file ownership is disjoint (Track A: `cli/main.py`, `core/{pipe,video_pipe,recipe,batch,result,output}.py`, `domains/image/ops.py`; Track B: `domains/video/*`, `domains/doc/*`, `domains/image/{bg,recolor}.py`, `core/setup_deps.py`). Wave 2 (R5 docs + R6 packaging) starts after Wave 1 merges so docs describe final behavior. Wave 3 is QA regression + packaging re-verification (rebuild, clean-venv install, scripted doc-example run).
