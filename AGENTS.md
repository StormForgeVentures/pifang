# pifang

> Canonical project-context home. This file is yours — roster created it once (2026-09-21) and will
> never overwrite it. Every runtime reads it: Cursor / OpenCode / Codex / Hermes / ZCode read it directly,
> and Claude loads it through the `@AGENTS.md` import in `CLAUDE.md`. Everything agents need to know
> about THIS project lives here; everything about how agents work lives in their generated files
> (regenerate with `roster deploy`). roster maintains only the `roster:team` block at the bottom.

## Identity

- **What this is:** Python CLI and importable library for deterministic image, document, and media processing — image resize/crop/convert and platform packs, PDF-to-markdown conversion and corpus ingest (delegated engines), ffmpeg video ops, Faster-Whisper transcription, a pipe DSL, named recipes, and folder batch runs with JSONL manifests. Built for AI agents (stable `--json` contract, exit codes 0–4) and usable by people at a terminal (plain text by default).
- **Client / owner:** StormForge Ventures (open source, Apache-2.0)
- **Stage:** production
- **Workflow:** pkg-build
- **Lifecycle:** by-folder
- **Vault project:** 1. Projects/pifang

Allowed values — `Stage`: production (default) · mvp · prototype · client-facing.
`Workflow`: saas-build · brand-website · pkg-build. `Lifecycle`: by-folder, the only one.
`Vault project`: a canonical alpha-vault subpath such as `1. Projects/<slug>` or `2. Areas/<x>`
(or another explicitly nested path), or `(none — no vault bridge)`. PARA roots are numeric: `0. Inbox/`,
`1. Projects/`, `2. Areas/`, `3. Resources/`, `4. Archive/`.

## Stack

Detected: Python CLI package (pkg-build)

- **Language:** Python 3.11+ · build backend hatchling · env/lock via `uv`
- **CLI framework:** Typer
- **Image:** Pillow (core) · optional pyvips via `pifang[fast]`
- **PDF:** pymupdf4llm + pypdf via `pifang[doc]` (default engine `fast`) · optional OpenDataLoader (`doc-odl`, needs JDK 11+) · marker/docling (`doc-heavy`) — delegated, not reimplemented
- **Video:** system ffmpeg/ffprobe (never bundled)
- **Transcription:** Faster-Whisper via `pifang[transcribe]`
- **Distribution:** PyPI via Trusted Publishing (`.github/workflows/publish.yml`)
- **Shapes:** CLI + importable API-library (see `docs/pkg-classification.md`)

## Conventions

- **Output contract.** Plain text is the default. With `--json` (root or any subcommand) stdout is exactly one JSON object, success or failure; errors carry `error_code`, `message`, `recovery.hint`. Exit codes: 0 ok · 1 validation · 2 missing dep · 3 processing · 4 partial batch. The JSON shape is public API — change it only with a CHANGELOG entry.
- **Docs cannot drift.** Every command shown in `README.md`, `docs/agents-blurb.md`, or `skills/pifang/SKILL.md` must run; `tests/test_docs_examples.py` enforces it. Agent-facing examples always pass `--json`.
- **Optional deps are lazy.** Core install is Pillow + Typer + PyYAML. Anything else is an extra, imported inside the function that needs it, and reported by `pifang doctor`.
- **Never install system tools.** `pifang setup` prints ffmpeg/Java commands; it does not run them.
- **Never ship mock.** A command is done when it runs on real files and is covered by a test that does so.
- Tests: `uv run --extra dev --extra transcribe pytest tests -q`. Video/transcribe tests skip without ffmpeg / faster-whisper.

## Layout

- `src/pifang/cli/main.py` — Typer app, every command, output/exception handling
- `src/pifang/core/` — recipes, pipe DSL, batch, manifests, doctor, setup, result/output types
- `src/pifang/domains/` — `image/`, `doc/`, `video/`, `transcribe/`, `text/`, `meta/`
- `src/pifang/recipes/builtin/` — built-in YAML recipes
- `tests/` — pytest · `examples/` — quickstart + fixtures · `skills/pifang/` — Agent Skill for consumer projects
- `docs/` — product docs (`api-design.md`, `agents-blurb.md`, `glossary.md`, `out-of-scope.md`, `publishing.md`, `project-brief.md`)

## Key paths

- Tickets (PRDs, issues, chores, spikes): `docs/tasks/{1-backlog,2-ready,3-in-progress,4-review,5-completed}/<type>-NNN-slug/` (location is status)
- A GitHub issue is an attribute, not a location — `github_issue:` frontmatter, one queue for everything
- Wave plan + handoff artifacts: `handoff/`
- Project memory (agents write lessons here): `.roster/memory/`

<!-- roster:team — generated block, rewritten on each deploy -->
## Agent team

Runtime-neutral team roster for **pifang** (mode: production). Each role's full
definition is materialized per runtime — `.cursor/rules/<role>.mdc`, `.opencode/agents/<role>.md`,
`.hermes/agents/<role>.md`, `.codex/agents/<role>.toml`, `.pi/agents/<role>.md`; Claude loads `.claude/agents/<role>.md` plus its orchestration block in CLAUDE.md.

| Role | Responsibility |
|---|---|
| PM | The pipeline entry point — use FIRST for any new feature, page, build phase, or scope change before any specialist works. Plans the build, decomposes it into maximally parallel waves, tracks progress against the spec, owns the acceptance gate. |
| Package Architect | Designs reusable packages: classifies archetype (library/SDK · framework · platform), package shape (CLI · API-library · UI drop-ins · compoza-module), and UX-weight, then designs the smallest explicitly-typed public API surface — the API is the product — and the one-source→many-projections map (typed op + description → REST/SDK/agent-tool). |
| AI Architect | Designs the AI features of the product: prompt architecture, model routing, RAG, memory, evals, observability. Domain specialist, not a meta-agent. |
| Designer | Owns the visual system on the Figma canvas: tokens, components with full state matrices, screen compositions grounded in real data fields. |
| Package Developer | Implements a reusable package against the pinned API contract: writes the typed surface, fires shape-specific craft (CLI/API/UI drop-in/compoza-module) at the step it bites, derives many projections from one source (no parallel specs), and conforms to the existing design system for light UX. |
| Package DevOps | Owns the package release/distribution/maintenance axis: build/bundle + type emit, Changesets versioning and CHANGELOG, the distribution-tier decision (dogfood/private-registry/OSS), publish gates and CI, multi-package version coordination, dogfood-wiring into consumer repos, and the private→OSS ramp. |
| Technical Docs Writer | Owns the full documentation surface as a product across three audiences — DX (README/TTFS, Diátaxis spine, API reference scaffold, quickstart, migration guides), UX (help articles, onboarding guides, feature explainers), and AX (AGENTS.md, markdown-first structure). Orchestrates cheap-model section-writers in parallel, then assembles and accuracy-gates the result. |
| QA Reviewer | Adversarial counterweight. Tests the implementation against the spec, hunts for what's wrong, reports with repro steps. Never fixes. |
| Security Reviewer | Adversarial security counterweight. Reviews auth, data access, input handling, dependencies, secrets. Assumes breach until proven otherwise. |
| Art Director | Impact judge for anything visual that ships: web pages, social visuals, video thumbnails, graphic design, and application UI (composure variant — restraint, not drama). Reviews rendered artifacts with fresh eyes against a forced 0-10 rubric, prescribes the bolder (or on app UI, the calmer) move, never fixes. |

**Coordination.** The main session operates as the PM/orchestrator: spec → wave plan → delegate →
wave-boundary QA + Security → acceptance gate. Two human checkpoints — **plan** (approve the spec/wave
plan) and **acceptance** (test the result); the middle runs autonomously with self-verification.

Claude and Codex delegate independent work through their native project subagents; Pi delegates through
its installed subagent extension with project scope. Cursor, OpenCode, and Hermes adopt the relevant role's
definition for each slice and pass artifacts through `handoff/`. Honor every role's Tool Access section.
For headless `codex exec` delegation, fill a copy of `handoff/codex-exec-prompt.md` per task — it inlines
the definition-of-done and sandbox bounds a headless run can't ask about.

## Handoff Protocol

Artifacts pass between roles as files in `handoff/`, named `{wave}/{from}-to-{to}.md`, each with the
standard header (Task, Status, Blockers, Decisions made, Open questions). Lead with a **tl;dr under 20
lines**; full detail below it. Binding decisions that still constrain downstream work go in
`handoff/project-state.md` (every agent's startup read). Completed/superseded rows append to
`handoff/project-state-history.md` — load history only for provenance or an explicit historical question.
<!-- /roster:team -->
