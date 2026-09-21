---
type: issue
id: issue-003
slug: ingest-manifest-overwritten-across-runs
owner: pkg-developer
verifier: pm-triage-2026-09-21
created: 2026-09-21
priority: 
submitter: 
blocked_ask:
---

# issue-003 — ingest manifest overwritten across runs

Legacy id: BUG-002 (from the retired `docs/tasks/bugs-backlog.md`). Fixed 2026-07-16.

`ingest.jsonl` was overwritten, not appended, across runs.

## Fix

Merge by resolved `input`, then rewrite the full JSONL.

## Acceptance

Covered by `test_ingest_manifest_merges_across_runs`.
