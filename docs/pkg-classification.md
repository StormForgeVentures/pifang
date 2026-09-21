# Package Classification — Pifang

**Status:** Approved  
**Date:** 2026-06-27  
**Inputs:** `docs/project-brief.md` (plan gate approved)

---

## Archetype

**`archetype: library`**

Pifang is a library/SDK you invoke — via CLI (`pifang …`) or Python import (`from pifang.image import resize`). It does not invert control (not a framework) and does not ship a hosted runtime or admin console (not a platform).

Call direction: **you call Pifang**; Pifang calls Pillow, ffmpeg, OpenDataLoader, etc.

---

## End-user UX

**`ships-end-user-UX: no`**  
**`UX-weight: none`**

CLI-only surface. No web UI, no design phase, no Designer role. Help text and `--human` output serve the operator persona; agents use `--json`.

---

## Shape(s)

| Shape | Ships? | Notes |
|---|---|---|
| **CLI** | Yes | Primary surface — `pifang` console script |
| **API-library** | Yes | Importable core: atoms, recipes, pipe executor, batch runner, manifest writer |
| **UI drop-ins** | No | — |
| **compoza-module** | No | — |

**CLI craft:** `.claude/references/cli/cli-shape.md`  
**Library craft:** `.claude/references/pkg/api-surface.md`, `packaging-mechanics.md` (adapted for Python)

**Layout (planned):**

```
src/pifang/
  cli/           # Typer/Click dispatch — thin, no business logic
  core/          # Atoms, pipe parser, recipe registry, batch, manifest
  domains/
    image/       # MVP
    doc/         # P1
    video/       # P1
  errors.py      # Structured PifangError + exit codes
```

CLI entry: `[project.scripts] pifang = "pifang.cli:main"` in `pyproject.toml`.

---

## The 7 build knobs

| Knob | Answer | Rationale |
|---|---|---|
| **Error model** | Structured `PifangError` hierarchy + exit codes; JSON error envelope on `--json` | Agent-first: predictable failures without parsing tracebacks. Business/processing errors return, don't crash the interpreter. |
| **Build orchestrator** | None — single Python package | No monorepo; `uv` for env/lock, `hatchling` (or equivalent) for build |
| **License** | **Apache-2.0** | Maintainer choice; aligns with OpenDataLoader and other ingestion deps |
| **Module format** | Python src layout (`src/pifang/`); `pyproject.toml` PEP 621 | Python equivalent of ESM-only single package — no dual CJS/ESM concern |
| **Distribution tier** | **OSS** (PyPI) with git dogfood pre-publish | Brief: public OSS intent; install via `uv tool install pifang` / `pipx install pifang`; dogfood from git URL until v1.0 |
| **Versioning mode** | **Fixed** — single package, single semver line | One `pifang` on PyPI; optional extras `[doc]`, `[video]`, `[fast]` share version |
| **Ship MCP server** | **No** (v0.1–v0.3) | P2 design note in brief; CLI is the agent interface for now. Revisit at v1.0 if agents need tool discovery without shell. |

---

## Error model detail

Exit codes (from brief — binding):

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Validation / user error (bad flags, missing input file) |
| `2` | Missing dependency (`doctor` failure, optional extra not installed) |
| `3` | Processing failure (corrupt file, ffmpeg error) |
| `4` | Partial batch failure (some files failed, manifest lists errors) |

**JSON error envelope** (stdout when `--json`, or dedicated error object):

```json
{
  "ok": false,
  "error_code": "MISSING_DEPENDENCY",
  "message": "Pillow is not installed",
  "exit_code": 2,
  "recovery": { "hint": "pip install pifang" }
}
```

Python API: raise `PifangError` subclasses; CLI catches and maps to exit code + envelope.

---

## Optional extras (PyPI)

| Extra | Pulls in | System deps checked by `doctor` |
|---|---|---|
| `(none)` | Pillow, Typer, PyYAML | — |
| `[doc]` | pymupdf4llm, pypdf (default engine `fast`) | — |
| `[doc-odl]` | opendataloader-pdf | JDK 11+ (optional engine) |
| `[doc-heavy]` | docling, marker-pdf | — |
| `[transcribe]` | faster-whisper | ffmpeg for video inputs |
| `[video]` | marker extra (no pip deps) | ffmpeg, ffprobe |
| `[fast]` | pyvips | libvips |

---

## Cross-workflow pulls

| Role | Fielded? | Why |
|---|---|---|
| **Designer** | No | UX-weight none |
| **AI Architect** | No | No LLM inference, RAG, or model routing in Pifang — delegates to external engines |
| **saas-build design craft** | No | — |

**Active specialists for pkg-build:**

| Phase | Role |
|---|---|
| API design | pkg-architect |
| Build v0.1 | pkg-developer |
| Docs | docs-writer |
| QA contract | qa-reviewer |
| Security | security-reviewer |
| Release | pkg-devops |

---

## Public API-library surface (preview — full design in `docs/api-design.md`)

Importable modules agents and scripts can use without subprocess:

| Module | Exports (illustrative) |
|---|---|
| `pifang.core.recipe` | `load_recipes()`, `resolve_recipe(name)`, `Recipe` |
| `pifang.core.pipe` | `parse_pipe(dsl)`, `execute_pipe(stages, input)` |
| `pifang.core.batch` | `batch_run(spec, paths)`, `ManifestWriter` |
| `pifang.domains.image` | `resize`, `crop_square`, `convert`, … |
| `pifang.errors` | `PifangError`, `MissingDependencyError`, … |

CLI is a thin wrapper over the same functions — no duplicated logic.

---

## Constraints for downstream

1. **Binary name:** `pifang` only — no alias.
2. **Apache-2.0** — LICENSE file required before OSS publish.
3. **CLI + library** — domain logic never lives only in CLI layer; must be importable and unit-testable.
4. **Agents first** — JSON stdout default; human output via `--human`.
5. **Delegate, don't reimplement** — PDF/video heavy lifting stays in external engines.
6. **Byte-stable writers** — manifests and JSON output: stable key order, trailing newline, locked indent (per cli-shape craft).

---

## Next step

**pkg-api-design** → `docs/api-design.md` (command tree, JSON schemas, recipe YAML spec, library types)
