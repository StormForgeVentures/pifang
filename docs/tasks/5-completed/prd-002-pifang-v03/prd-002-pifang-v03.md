---
type: prd
id: prd-002
slug: pifang-v03
owner: pkg-developer
verifier: pm-triage-2026-09-21
created: 2026-09-21
priority: 
submitter: 
blocked_ask:
---

> **Superseded (2026-09-21):** the output-mode decision in this PRD was replaced — plain text is the default and `--json` (root or any subcommand) is the agent contract; `--human` is removed. See `docs/api-design.md`.

# PRD — Pifang v0.3 (Video / ffmpeg)

**Status:** Approved for build  
**Source:** `docs/project-brief.md` P1 Video, `docs/api-design.md` patterns

## Overview & goals

Pifang v0.3 adds an ffmpeg-backed **video domain**: transcode, trim, audio extract, concat, GIF export, frame extraction, caption burn-in/sidecar, audio normalize, resize, and `video info`. Agents get the same JSON contract, exit codes, dry-run/force flags, pipe/batch compatibility where sensible, and built-in recipes for common social/podcast workflows.

## Personas

Agent (primary), operator, downstream CMS/social pipeline.

## P0 — v0.3 functional requirements

### Global contract (unchanged)

- JSON stdout default; exit codes 0–4
- `--dry-run`, `--force`, `--verbose` on mutating video commands
- `pifang doctor --video` checks ffmpeg + ffprobe on PATH

### Video atoms

| Command | Purpose | Key flags |
|---|---|---|
| `video info` | ffprobe summary JSON | input path |
| `video transcode` | Re-encode to target format | `-o`, `--codec`, `--crf`, `--preset` |
| `video trim` | Cut segment | `--start`, `--end` or `--duration` |
| `video extract-audio` | Audio-only output | `-o`, `--format mp3\|aac\|wav` |
| `video concat` | Join clips in order | multiple inputs, `-o` |
| `video to-gif` | Animated GIF | `-o`, `--fps`, `--width` |
| `video extract-frames` | PNG/JPG sequence | `-o` dir, `--fps`, `--format` |
| `video resize` | Scale video | `--width`, `--height`, `--fit contain\|cover` |
| `video normalize-audio` | Loudness normalize (EBU R128 via ffmpeg loudnorm) | `-o`, `--target-lufs` |
| `video captions` | Burn-in or emit sidecar | `--srt`/`--vtt`, `--burn-in` or sidecar `-o` |

### Built-in recipes

| Recipe | Pipeline |
|---|---|
| `social-clip` | trim → resize cover 1080×1920 → transcode h264+aac mp4 |
| `podcast-audio` | extract-audio → normalize-audio → mp3 |

Recipes live in `src/pifang/recipes/builtin/` and register under `video` domain.

### Composition

- `pifang pipe video "trim 0:30-1:00 | resize 1080x1920 | transcode mp4"` (subset of atoms)
- `pifang batch run video transcode ./clips/ -o ./out/ --format mp4 --manifest clips.jsonl`

### Dependencies

- **System:** ffmpeg + ffprobe on PATH (not bundled)
- **PyPI extra:** `pifang[video]` is a marker extra (no pip deps) documenting intent; doctor verifies binaries

## Non-goals (v0.3)

- Real-time streaming, GPU encoding selection UI, whisper transcription (P2 audio)
- Arbitrary ffmpeg filter graphs from CLI
- Windows installer for ffmpeg

## P0 acceptance criteria

| ID | Criterion |
|---|---|
| AC-v03-01 | Given ffmpeg/ffprobe on PATH, when `pifang doctor --video`, then exit 0 and JSON lists both with paths |
| AC-v03-02 | Given valid MP4, when `pifang video info clip.mp4 --json`, then exit 0 and JSON includes duration, width, height, codec |
| AC-v03-03 | Given valid MP4, when `pifang video transcode clip.mp4 -o out.webm --json`, then exit 0 and output plays |
| AC-v03-04 | Given valid MP4, when `pifang video trim clip.mp4 -o trim.mp4 --start 5 --duration 10 --json`, then output duration ≈ 10s |
| AC-v03-05 | Given valid MP4, when `pifang video extract-audio clip.mp4 -o audio.mp3 --json`, then audio-only mp3 exists |
| AC-v03-06 | Given two MP4s, when `pifang video concat a.mp4 b.mp4 -o merged.mp4 --json`, then merged duration ≈ sum |
| AC-v03-07 | Given valid MP4 + SRT, when `pifang video captions clip.mp4 --srt subs.srt -o out.mp4 --burn-in --json`, then output has burned subs |
| AC-v03-08 | Given valid MP4, when `pifang recipe run video social-clip clip.mp4 -o out.mp4 --json`, then vertical mp4 output |
| AC-v03-09 | Given missing ffmpeg, when `pifang doctor --video`, then exit 2 with install hint |
| AC-v03-10 | Given `--dry-run` on any mutating video command, then no output file written |

## Implementation priority

Wave 3 (single wave): ffmpeg runner → video ops → recipes → CLI → doctor → tests → README.
