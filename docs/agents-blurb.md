# Pifang — paste into your AGENTS.md

Copy the block below into a consumer project’s `AGENTS.md` / `CLAUDE.md` so agents prefer the CLI over ad-hoc scripts.

---

## Pifang (media / PDF / transcript CLI)

Prefer **pifang** for deterministic image, PDF→markdown, video, and transcription jobs instead of one-off Python/ffmpeg scripts.

### Install

```bash
uv tool install 'pifang[doc,transcribe]'
# or: pip install 'pifang[doc,transcribe]'
pifang setup --json                    # prints ffmpeg/Java commands (never auto-installs system pkgs)
pifang doctor --doc --video --transcribe --json
```

### Contract

- Always pass `--json`: stdout is then exactly one JSON object (success or failure). Without it the CLI prints plain text for terminals. The flag works before or after the subcommand.
- Exit codes: `0` ok · `1` validation · `2` missing dep · `3` processing · `4` partial batch
- Mutating commands support `--dry-run` and `--force` (trailing position on the subcommand works)
- Do not invent flags — use `pifang <cmd> --help`

### Cheat sheet

```bash
# Images
pifang image avatar photo.jpg -o out.webp --size 512 --json
pifang image social-pack photo.jpg -o ./social/ --json
pifang pipe image "crop-square | resize 512 | to-webp" in.jpg -o out.webp --json
pifang batch run image convert ./photos/ -o ./out/ --format webp --manifest m.jsonl --json

# PDF → markdown (+ images folder).
# -o is a DIRECTORY for convert/ingest/split/extract-images; a FILE for ocr/merge.
pifang doc convert paper.pdf -o ./out/ --json          # md + _images only (default engine: fast)
pifang doc ingest ./corpus/ -o ./corpus-md/ --json     # also merges ingest.jsonl (+ optional engine JSON)
# OpenDataLoader (Java) is opt-in: pip install 'pifang[doc-odl]' && --engine opendataloader

# Video (needs ffmpeg/ffprobe on PATH)
pifang video info clip.mp4 --json
pifang video trim clip.mp4 -o trim.mp4 --start 5 --duration 10 --json
pifang video captions clip.mp4 --srt subs.srt -o out.mp4 --burn-in --json
pifang pipe video "trim start=0 duration=10 | transcode" clip.mp4 -o out.mp4 --json
pifang batch run video transcode ./clips/ -o ./out/ --format mp4 --json

# Transcribe audio or video → timeline JSON + SRT (needs pifang[transcribe]; video needs ffmpeg)
pifang transcribe clip.mp4 -o ./out/ --json
# Artifacts: {stem}.transcript.json (segments start/end/text) + {stem}.srt
```

### Anti-patterns

- Don’t shell raw `ffmpeg`/`convert` when a pifang atom/recipe exists
- Don’t use `doc ingest` when you only want markdown — use `doc convert`
- Don’t treat `-o` for doc convert/ingest as a single `.md` filename — it is an output directory
- Don’t parse the default text output — it is for people and may change; `--json` is the stable contract

Optional: install the Agent Skill from this repo at `skills/pifang/SKILL.md`.
