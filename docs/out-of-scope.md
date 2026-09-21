# Out of scope

Settled “no”s so contributors and agents do not re-litigate them. Append new entries; do not delete.

| Item | Why declined | What would reopen |
|---|---|---|
| MCP server in v0.1–v0.4 | CLI is the agent interface for now | v1.0 design pass if agents need tool discovery without shell |
| Scene / generative video (Revideo, Manim, Remotion) | Different product; not ffmpeg edit ops | Separate AI track or sibling tool |
| Bundling Java / ffmpeg in the wheel | Keep install light; system tools via `pifang setup` | Strong demand + maintainable bundling story |
| GUI / web UI | CLI-only package | Explicit product pivot |
| Arbitrary `pifang run script.py` | Unsafe eval harness; deferred to plugins | P2 plugin system with pinned API |

See also [project-brief.md](project-brief.md) Non-goals.
