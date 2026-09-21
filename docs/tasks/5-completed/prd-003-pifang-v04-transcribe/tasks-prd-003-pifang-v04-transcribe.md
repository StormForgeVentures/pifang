# Tasks — Pifang v0.4 (Transcribe)

**Status:** Completed (archived). Historical checklist from the private build wave.

## Relevant Files

- `src/pifang/domains/transcribe/` — engine, formats, orchestration
- `src/pifang/cli/main.py` — `transcribe`, `video transcribe`, `audio transcribe`
- `src/pifang/core/doctor.py` — `--transcribe`
- `pyproject.toml` — `[transcribe]` extra
- `tests/test_transcribe.py`
- `README.md`

## Tasks

- [x] 1.0 Core + extras (maps to: AC-v04-01, AC-v04-02)
  - [x] 1.1 `pyproject.toml` optional-deps `transcribe = ["faster-whisper>=1.0.0"]`
  - [x] 1.2 `domains/transcribe/engine.py` — load model, run, normalize segments
  - [x] 1.3 MissingDependencyError with install hint

- [x] 2.0 Artifacts (maps to: AC-v04-03, AC-v04-06)
  - [x] 2.1 Write `{stem}.transcript.json` (stable key order)
  - [x] 2.2 Write SRT; optional VTT
  - [x] 2.3 Sanitize stem (whitespace → `_`)

- [x] 3.0 Media paths (maps to: AC-v04-03, AC-v04-04)
  - [x] 3.1 Audio path: direct Faster-Whisper
  - [x] 3.2 Video path: ffmpeg extract temp WAV → transcribe → cleanup
  - [x] 3.3 `transcribe_one` / dry-run / force skip

- [x] 4.0 CLI + doctor (maps to: all AC)
  - [x] 4.1 `pifang transcribe`
  - [x] 4.2 `video transcribe` + `audio transcribe` aliases
  - [x] 4.3 `doctor --transcribe`

- [x] 5.0 Verification (maps to: all AC)
  - [x] 5.1 Unit tests for SRT/VTT writers (no model required)
  - [x] 5.2 Integration tests skip without faster-whisper/ffmpeg
  - [x] 5.3 README transcribe section

**Wave 4:** 1.0 → 2.0 → 3.0 → 4.0 → 5.0 (serial)
