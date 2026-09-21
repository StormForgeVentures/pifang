# Tasks — Pifang v0.3 (Video)

**Status:** Completed (archived). Historical checklist from the private build wave.

## Relevant Files

- `src/pifang/domains/video/` — ffmpeg wrapper + ops
- `src/pifang/recipes/builtin/` — social-clip, podcast-audio YAML
- `src/pifang/cli/main.py` — `video` typer group
- `src/pifang/core/doctor.py` — `--video` checks
- `tests/test_video.py` — pytest + CLI integration

## Tasks

- [ ] 1.0 ffmpeg runner (maps to: AC-v03-01, AC-v03-09)
  - [ ] 1.1 `domains/video/ffmpeg.py` — locate binaries, run ffmpeg with timeout, capture stderr
  - [ ] 1.2 `domains/video/info.py` — ffprobe JSON parse → stable summary dict
  - [ ] 1.3 MissingDependencyError when ffmpeg/ffprobe absent

- [ ] 2.0 Video atoms (maps to: AC-v03-02 through AC-v03-07, AC-v03-10)
  - [ ] 2.1 transcode, trim, extract-audio, concat
  - [ ] 2.2 to-gif, extract-frames, resize, normalize-audio
  - [ ] 2.3 captions (burn-in + sidecar export)
  - [ ] 2.4 OpResult + dry-run + force skip via mtime

- [ ] 3.0 Recipes + pipe (maps to: AC-v03-08)
  - [ ] 3.1 Builtin YAML: social-clip, podcast-audio
  - [ ] 3.2 Extend pipe DSL for video domain (trim, resize, transcode minimum)

- [ ] 4.0 CLI + doctor (maps to: all AC)
  - [ ] 4.1 `video_app` commands mirroring atoms
  - [ ] 4.2 `doctor --video` flag
  - [ ] 4.3 `batch run video …` wiring

- [ ] 5.0 Verification (maps to: all AC)
  - [ ] 5.1 Generate test clip via ffmpeg in pytest fixture (skip if no ffmpeg)
  - [ ] 5.2 CLI subprocess tests for info, trim, transcode
  - [ ] 5.3 README video section

**Wave 3:** 1.0 → 2.0 → 3.0 → 4.0 → 5.0 (serial)
