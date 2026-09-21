# Contributing to Pifang

Thanks for helping improve an agent-first media CLI.

## Development setup

```bash
git clone https://github.com/StormForgeVentures/pifang.git
cd pifang
uv venv && source .venv/bin/activate
uv pip install -e ".[dev,doc,transcribe]"
# optional system tools — printed, not auto-installed:
pifang setup
```

Requires Python 3.11+.

## Checks

```bash
pytest tests -q
pifang doctor --doc --video --transcribe
```

Video/transcribe integration tests skip when `ffmpeg` or `faster-whisper` is missing.

## Project layout

- `src/pifang/` — library + CLI
- `tests/` — pytest
- `docs/` — product docs, glossary, agent blurb
- `examples/` — quickstart + fixtures
- `skills/pifang/` — optional Agent Skill drop-in for consumer projects

## Pull requests

1. Prefer a focused branch (`fix/…`, `feature/…`).
2. Add/adjust tests for behavior changes.
3. Keep the public CLI stable; widen surfaces only with docs updates.
4. Run `pytest` before opening the PR.
5. Fill out the PR template checklist.

## Coding notes

- Default stdout is plain text for terminals. With `--json`, stdout is exactly one JSON object — that is the agent contract and must stay stable.
- Exit codes: 0 success · 1 validation · 2 missing dep · 3 processing · 4 partial batch.
- Prefer extending atoms/recipes over one-off scripts in docs/examples.
- Doc default engine is `fast` (pure Python). OpenDataLoader is opt-in (`doc-odl` + JDK).

## License

By contributing, you agree your contributions are licensed under the Apache License 2.0.
