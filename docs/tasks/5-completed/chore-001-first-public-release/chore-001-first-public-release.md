---
type: chore
id: chore-001
slug: first-public-release
owner: maintainer
verified_by: pm-triage-2026-09-23
created: 2026-09-21
priority: p0
submitter: 
blocked_ask:
---

# chore-001 — first public release

Manual gates for flipping `StormForgeVentures/pifang` public and cutting the first PyPI release.
Replaces the retired `docs/oss-prepublic-checklist.md`. Everything automated (tests, twine check,
secret scan, history squash) is done; what remains needs a human with GitHub/PyPI admin.

## Repo

- [x] Repo visibility → **Public** (private as of 2026-09-21)
- [x] Enable **Private Vulnerability Reporting** (Settings → Code security) — `SECURITY.md` links to it
- [x] Topics set 2026-09-23
- [x] Branch protection on `main` (require CI)

## PyPI

- [x] Name `pifang` still free (404 on pypi.org/pypi/pifang as of 2026-09-21)
- [x] Add a **pending** Trusted Publisher (done 2026-09-21) on pypi.org (account → Publishing) — owner `StormForgeVentures`, repo `pifang`, workflow `publish.yml`, environment `pypi`. The project is created by the first publish; nothing to pre-create beyond this.
- [x] Create GitHub Environment `pypi` — done 2026-09-21, deployment rule: tags `v*` only
- [x] Maintainer 2FA enabled on PyPI
- [x] Set the `[0.1.0]` date in `CHANGELOG.md` to 2026-09-23
- [x] Tag `v0.1.0` and push (`git tag v0.1.0 && git push origin v0.1.0`). The `pypi` environment deploys only from `v*` tags; `workflow_dispatch` from a branch is rejected by design.

## Smoke after publish

```bash
uv tool install 'pifang[doc,transcribe]'
pifang --version
pifang doctor --doc --transcribe --json
pifang image avatar examples/fixtures/sample.jpg -o /tmp/avatar.webp --size 256 --json
pifang doc convert <a.pdf> -o /tmp/out/ --json
```

## Record

Published 2026-09-23: repo public, PVR enabled, main protected (CI checks required, no force-push), tag `v0.1.0` → publish run 35828377712 → https://pypi.org/project/pifang/0.1.0/. Smoke from a clean venv: `--version`, `doctor`, `image avatar`, `doc convert` all ok.

## Acceptance

- `https://pypi.org/project/pifang/` shows 0.1.0 published via Trusted Publishing.
- `uv tool install pifang` on a clean machine passes the smoke block above.
- `docs/publishing.md` is accurate for the next release.
