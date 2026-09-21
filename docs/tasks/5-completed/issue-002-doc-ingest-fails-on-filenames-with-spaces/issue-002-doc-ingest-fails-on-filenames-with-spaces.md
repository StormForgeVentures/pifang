---
type: issue
id: issue-002
slug: doc-ingest-fails-on-filenames-with-spaces
owner: pkg-developer
verifier: pm-triage-2026-09-21
created: 2026-09-21
priority: 
submitter: 
blocked_ask:
---

# issue-002 — doc ingest fails on filenames with spaces

Legacy id: BUG-001 (from the retired `docs/tasks/bugs-backlog.md`). Fixed 2026-07-16.

`doc ingest` failed on PDF filenames containing spaces with the `fast` engine.

## Fix

Sanitize the stem (whitespace → `_`) in `ingest_one` before path derivation.

## Acceptance

Covered by `test_ingest_space_named_pdf`.
