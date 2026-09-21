# Publishing (PyPI)

First public upload is a **maintainer gate**. This repo scaffolds Trusted Publishing; do not hand-run `twine upload` with a long-lived token when OIDC is available.

## Prerequisites

1. Create the PyPI project `pifang` (name checked available as of 2026-07-16).
2. On PyPI → project → Publishing → add a trusted publisher:
   - Owner: `StormForgeVentures`
   - Repo: `pifang`
   - Workflow: `publish.yml`
   - Environment: `pypi` (create matching GitHub Environment)
3. Enable GitHub Environment `pypi` with optional required reviewers.
4. Ensure maintainers have 2FA on PyPI.

## Local dry-run (no upload)

```bash
pip install -e ".[dev]"
python -m build
twine check dist/*
```

## Release flow

1. Update `CHANGELOG.md` and bump `version` in `pyproject.toml` if needed.
2. Tag `vX.Y.Z` and push, **or** run Actions → **Publish** → `workflow_dispatch`.
3. Workflow builds the sdist/wheel and publishes via OIDC (see [`.github/workflows/publish.yml`](../.github/workflows/publish.yml)).

## Verify

```bash
uv tool install pifang
pifang --version
pifang doctor
```
