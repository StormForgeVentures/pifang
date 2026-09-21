---
type: issue
id: issue-001
slug: dry-run-fails-on-multi-step-recipes
owner:
verifier:
created: 2026-09-21
priority: p2
submitter: 
blocked_ask:
---

# issue-001 — dry run fails on multi step recipes

`--dry-run` fails on any multi-step recipe or pipe. Found 2026-09-21; present before and after the v0.5 hardening.

## Repro

```bash
pifang image avatar examples/fixtures/sample.jpg -o /tmp/out.webp --dry-run --json
# exit 1, error_code FILE_NOT_FOUND, message names /tmp/.pifang-tmp-sample-0.webp
```

Single-step commands (`image convert --dry-run`) work.

## Root cause

`run_recipe` chains steps through temp files. Under dry-run step 1 writes nothing, so step 2 validates an input path that does not exist.

## Suggested fix

Under dry-run, validate the original input once and plan the remaining steps without touching the filesystem (or skip the input-exists check for intermediate temp paths). Same treatment for `pipe image` / `pipe video` if they share the chaining.

## Acceptance

- `pifang image avatar <file> -o <out> --dry-run --json` exits 0 with `"dry_run": true` and writes nothing.
- Same for `image hero`, `image social-square`, `pipe image "a | b"`, and the video recipes.
- A test covers a multi-step dry run.
