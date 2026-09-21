"""ffmpeg / ffprobe subprocess helpers."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from pifang.errors import MissingDependencyError, ProcessingError

# Short probes (ffprobe) vs long jobs (transcode, etc.)
DEFAULT_PROBE_TIMEOUT = 30
DEFAULT_FFMPEG_TIMEOUT = 3600


def ffmpeg_path() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise MissingDependencyError(
            "ffmpeg not found on PATH",
            {"hint": "Install ffmpeg (apt install ffmpeg / brew install ffmpeg)"},
        )
    return path


def ffprobe_path() -> str:
    path = shutil.which("ffprobe")
    if not path:
        raise MissingDependencyError(
            "ffprobe not found on PATH",
            {"hint": "Install ffmpeg (includes ffprobe)"},
        )
    return path


def _timeout_error(tool: str, timeout: float | None, exc: BaseException) -> ProcessingError:
    secs = timeout if timeout is not None else "unlimited"
    return ProcessingError(
        f"{tool} timed out after {secs}s",
        "SUBPROCESS_TIMEOUT",
        {"hint": f"Increase timeout or inspect hung {tool} process"},
    )


def run_ffmpeg(
    args: list[str],
    *,
    dry_run: bool = False,
    timeout: float | None = DEFAULT_FFMPEG_TIMEOUT,
) -> list[str]:
    """Run ffmpeg with -y -hide_banner -loglevel error. Returns full command for dry-run."""
    cmd = [ffmpeg_path(), "-y", "-hide_banner", "-loglevel", "error", *args]
    if dry_run:
        return cmd
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise _timeout_error("ffmpeg", timeout, exc) from exc
    if proc.returncode != 0:
        raise ProcessingError(proc.stderr.strip() or "ffmpeg failed", "FFMPEG_FAILED")
    return cmd


def run_ffprobe(
    args: list[str],
    *,
    timeout: float | None = DEFAULT_PROBE_TIMEOUT,
) -> subprocess.CompletedProcess[str]:
    cmd = [ffprobe_path(), *args]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise _timeout_error("ffprobe", timeout, exc) from exc
    if proc.returncode != 0:
        raise ProcessingError(proc.stderr.strip() or "ffprobe failed", "FFPROBE_FAILED")
    return proc


def escape_concat_path(path: Path | str) -> str:
    """Escape a path for ffmpeg concat demuxer `file '...'` lines.

    Single quotes in the path become `'\''` (end quote, escaped quote, reopen).
    """
    text = str(Path(path).resolve())
    return text.replace("'", r"'\''")


def escape_filter_path(path: Path | str) -> str:
    """Escape a filesystem path for use inside an ffmpeg ``-vf`` filter argument.

    Paths are normalized to forward slashes first (Windows-friendly).

    ffmpeg applies *two* layers of backslash escaping (option value + filtergraph).
    A literal ``'`` therefore needs three backslashes (``\\\\\\'`` in a Python
    string / ``\\\'`` raw) so the subtitles filter opens the real path. Colons
    (drive letters) use a double-backslash escape.
    """
    text = str(Path(path).resolve()).replace("\\", "/")
    out: list[str] = []
    for ch in text:
        if ch == "'":
            out.append("\\" * 3 + "'")
        elif ch == ":":
            out.append("\\" * 2 + ":")
        elif ch == "\\":
            out.append("\\" * 4)
        elif ch in ("[", "]", ",", ";"):
            out.append("\\" + ch)
        else:
            out.append(ch)
    return "".join(out)


def parse_time(value: str | float | int) -> float:
    """Parse seconds, MM:SS, or HH:MM:SS to float seconds."""
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        raise ValueError("empty time")
    if ":" not in text:
        return float(text)
    parts = text.split(":")
    if len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    raise ValueError(f"invalid time: {value}")


def ensure_input(path: Path) -> None:
    from pifang.errors import ValidationError

    if not path.exists():
        raise ValidationError(f"Input file not found: {path}", "FILE_NOT_FOUND")


def resolve_output(input_path: Path, output: Path, default_ext: str) -> Path:
    if output.is_dir() or str(output).endswith("/"):
        output.mkdir(parents=True, exist_ok=True)
        return output / f"{input_path.stem}.{default_ext.lstrip('.')}"
    output.parent.mkdir(parents=True, exist_ok=True)
    return output


def should_skip(input_path: Path, output_path: Path, force: bool) -> bool:
    if force or not output_path.exists():
        return False
    return output_path.stat().st_mtime >= input_path.stat().st_mtime
