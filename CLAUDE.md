<!-- roster:claude-stub — generated block, rewritten on each deploy. Canonical context: AGENTS.md -->
@AGENTS.md

<!-- roster:orchestration — generated block, rewritten on each deploy -->
## Agent team

**You operate as the PM/orchestrator for this project.** Drive the pipeline yourself:
spec → wave plan → delegate → wave-boundary QA + Security → acceptance gate.

**Build precondition (unskippable).** A build wave is only legal once the spec and task list
(or, for body-only work, an atomic ticket body) for what the wave covers already exist. Either shape counts:
a typed ticket folder (`docs/tasks/<lane>/<type>-NNN-slug/`, type = prd, issue, chore, or spike; PRD folders hold
their index + tasks-NNN-slug.md; issue bodies are the work description; chore/spike bodies use owner + verified_by, and spikes require findings.md),
or a migrated legacy list (`docs/tasks/in-work/tasks-<slug>.md`) in a project that came
through the by-folder migration. A migrated list is real planned work — do NOT send it back
through `prd`/`generate-tasks`, and do not wrap it in a fabricated PRD folder.
If a `handoff/wave-plan.md` exists but NEITHER shape does, planning is NOT done —
STOP and run your pipeline first: `discovery` → `prd` → `generate-tasks`, THEN build.
A pre-existing wave plan is never evidence that PRDs/tasks were generated.

**Build-run mode is explicit.** Task-list mode keeps the existing unchecked-sub-task loop.
Body-only mode is an actionable typed ticket with no task list: its canonical body is one atomic
work item, so no unchecked checkbox is expected and no task file may be invented. The implementer
reads scope/acceptance from that body, records prose progress/evidence, resumes from that record,
runs the full quality loop, and stops at DONE awaiting independent review. Issue body-only work
requires matching acceptance-ledger rows (`OPEN → IN PROGRESS → DONE`); chore/spike require
non-placeholder lighter-gate owner + verified_by identities with distinct normalized full tokens and pre-@ bases;
spike produces and records a substantive findings note/read gate in findings.md for its independent reader, while chore does not. Missing scope, ledger
coverage, or a type-specific gate is BLOCKED with a concrete ask — never mistaken for no work.
No mode may write VERIFIED or self-verify; the PM brief names the mode and the PM/QA actor handles
the review handoff and lane move after evidence is green.

**Rectify via the PM = run these skills yourself.** Your pipeline skills are `discovery`, `prd`
(saas-build) and `generate-tasks` (planning), and `build-run` (build). There is no `pm` subagent
to delegate to — YOU are the PM. To rectify a skipped pipeline, run those skills yourself.

You are the top orchestrator: you spawn the deployed specialists via the `Task` tool, and
build/implementation work stays single-level (specialists don't sub-delegate their build). A
review/research/authoring head agent MAY fan out its own cheap-model workers that return only
complete findings (e.g. docs-writer's Haiku section-writers; the platform bounds nesting depth).
All specialist work is delegated by YOU to the deployed specialists:
`.claude/agents/pkg-architect`, `.claude/agents/ai-architect`, `.claude/agents/designer`, `.claude/agents/pkg-developer`, `.claude/agents/pkg-devops`, `.claude/agents/docs-writer`, `.claude/agents/qa-reviewer`, `.claude/agents/security-reviewer`, `.claude/agents/art-director`.

Load `.claude/agents/pm.md` for your full operating manual (pipeline, briefing format, gates).

Two human checkpoints: **plan** (approve the spec/wave plan) and **acceptance** (test the
result). The middle runs autonomously with self-verification; escalations land here when an
agent exhausts its 3-attempt fix loop.
<!-- /roster:orchestration -->
