---
type: prd
id: prd-003
slug: pifang-v04-transcribe
owner: pkg-developer
verifier: pm-triage-2026-09-21
created: 2026-09-21
priority: 
submitter: 
blocked_ask:
---

> **Superseded (2026-09-21):** the output-mode decision in this PRD was replaced — plain text is the default and `--json` (root or any subcommand) is the agent contract; `--human` is removed. See `docs/api-design.md`.

# PRD — Pifang v0.4 (Transcribe)

**Status:** Approved for build (plan gate: implement instruction 2026-07-16)  
**Source:** `docs/project-brief.md` P1 Transcribe, transcript wave plan

## Overview & goals

Ship a shared **transcription** surface so agents get a stable **timeline JSON** (plus SRT) from video or audio files. Engine: Faster-Whisper (wrapper). Video extracts audio via existing ffmpeg path first. Success: an agent can run one command and receive machine-editable segments for LLM video editing workflows.

## Personas

Agent (primary), operator.

## P0 — v0.4 functional requirements

### Global contract (unchanged)

- JSON stdout default; exit codes 0–4
- `--dry-run`, `--force`, `--verbose` on mutating commands
- `pifang doctor --transcribe` checks Faster-Whisper import; video path also needs ffmpeg

### Commands

| Command | Purpose |
|---|---|
| `pifang transcribe PATH -o OUT_DIR` | Shared entry: video or audio → timeline + SRT |
| `pifang video transcribe …` | Alias → same core |
| `pifang audio transcribe …` | Alias → same core (audio-only inputs) |

### Flags

- `--model` (default `base`) — Faster-Whisper model size
- `--language` optional (auto-detect when omitted)
- `--format` / outputs: always write `{stem}.transcript.json`; write `{stem}.srt` by default; `--vtt` also writes `{stem}.vtt`
- `-o` output **directory** (artifacts named from sanitized stem)

### Artifacts

**Timeline JSON** (`{stem}.transcript.json`):

```json
{
  "ok": true,
  "input": "/abs/path/in.mp4",
  "engine": "faster-whisper",
  "model": "base",
  "language": "en",
  "duration_sec": 12.3,
  "segments": [
    {"id": 0, "start": 0.0, "end": 2.4, "text": "Hello world"}
  ]
}
```

**SRT** — standard cue file for `video captions` interop.

### Dependencies

- PyPI: `pifang[transcribe]` → `faster-whisper`
- System: ffmpeg/ffprobe required when input is video

## Non-goals (v0.4)

- Speaker diarization, live streaming, GPU installer bundling
- Cut-from-transcript / timeline-driven edit (follow-on)
- Scene engines, generative image→video

## P0 acceptance criteria

| ID | Criterion |
|---|---|
| AC-v04-01 | Given Faster-Whisper installed, when `pifang doctor --transcribe`, then exit 0 and JSON lists faster-whisper ok |
| AC-v04-02 | Given missing Faster-Whisper, when `pifang doctor --transcribe` or `transcribe`, then exit 2 with install hint `pip install pifang[transcribe]` |
| AC-v04-03 | Given audio WAV/MP3, when `pifang transcribe audio.wav -o out/ --json`, then `{stem}.transcript.json` + `{stem}.srt` exist and segments non-empty for spoken audio |
| AC-v04-04 | Given MP4 with audio + ffmpeg, when `pifang video transcribe clip.mp4 -o out/ --json`, then same artifacts; stdout JSON ok=true |
| AC-v04-05 | Given `--dry-run`, when any transcribe command, then no output files written |
| AC-v04-06 | Given `--vtt`, when transcribe succeeds, then `{stem}.vtt` is written |
| AC-v04-07 | Given `audio transcribe` on a video file, then validation error (audio alias rejects non-audio) |

## Implementation priority

Wave 4 (serial): core engine → formats → CLI aliases → doctor → tests → README.
