"""Guided dependency install for Python extras + system-tool instructions."""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from typing import Any

from pifang.errors import ProcessingError

# Pure-Python / pip-installable extras (no system JDK required).
PIP_EXTRAS: dict[str, str] = {
    "doc": "pifang[doc]",
    "transcribe": "pifang[transcribe]",
    "doc-odl": "pifang[doc-odl]",
    "doc-heavy": "pifang[doc-heavy]",
    "fast": "pifang[fast]",
    "video": "pifang[video]",  # marker only — ffmpeg is system
}

DEFAULT_PIP_TIMEOUT = 3600


def system_install_hints() -> list[dict[str, Any]]:
    """OS-specific commands for non-pip tools (never auto-run)."""
    system = platform.system().lower()
    hints: list[dict[str, Any]] = []

    ffmpeg_ok = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
    if system == "linux":
        ffmpeg_cmds = [
            "sudo apt-get update && sudo apt-get install -y ffmpeg",
            "# or: download a static build and put ffmpeg/ffprobe on PATH",
        ]
        java_cmds = [
            "sudo apt-get install -y openjdk-17-jre-headless",
            "# only needed for --engine opendataloader",
        ]
    elif system == "darwin":
        ffmpeg_cmds = ["brew install ffmpeg"]
        java_cmds = ["brew install openjdk@17", "# only needed for --engine opendataloader"]
    else:
        ffmpeg_cmds = [
            "Install ffmpeg from https://ffmpeg.org/download.html and add to PATH",
        ]
        java_cmds = [
            "Install a JDK 11+ from https://adoptium.net (only for --engine opendataloader)",
        ]

    hints.append(
        {
            "name": "ffmpeg",
            "required_for": ["video", "transcribe (video inputs)"],
            "ok": ffmpeg_ok,
            "install": ffmpeg_cmds,
        }
    )
    java = shutil.which("java")
    hints.append(
        {
            "name": "java",
            "required_for": ["doc --engine opendataloader"],
            "ok": java is not None,
            "optional": True,
            "install": java_cmds,
            "note": "Default doc engine is pure-Python `fast` (pymupdf4llm). Java is only for OpenDataLoader.",
        }
    )
    return hints


def install_pip_extras(
    extras: list[str],
    *,
    dry_run: bool = False,
    timeout: float | None = DEFAULT_PIP_TIMEOUT,
) -> dict[str, Any]:
    """Install selected optional extras into the current Python environment."""
    unknown = [e for e in extras if e not in PIP_EXTRAS]
    if unknown:
        return {
            "ok": False,
            "error_code": "UNKNOWN_EXTRA",
            "message": f"Unknown extras: {', '.join(unknown)}",
            "recovery": {"hint": f"Choose from: {', '.join(sorted(PIP_EXTRAS))}"},
        }

    specs = [PIP_EXTRAS[e] for e in extras]
    # Prefer editable root when developing from a checkout.
    cmd = [sys.executable, "-m", "pip", "install", *specs]
    if dry_run:
        return {"ok": True, "dry_run": True, "command": cmd, "extras": extras}

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise ProcessingError(
            f"pip install timed out after {timeout}s",
            "SUBPROCESS_TIMEOUT",
            {"hint": "Increase timeout or install extras manually"},
        ) from exc
    return {
        "ok": proc.returncode == 0,
        "dry_run": False,
        "command": cmd,
        "extras": extras,
        "stdout": (proc.stdout or "")[-4000:],
        "stderr": (proc.stderr or "")[-4000:],
        "exit_code": proc.returncode,
    }


def setup_report(
    *,
    extras: list[str] | None = None,
    install: bool = False,
    dry_run: bool = False,
    show_system: bool = True,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": True,
        "command": "setup",
        "default_doc_engine": "fast",
        "pip_extras": sorted(PIP_EXTRAS),
    }
    if show_system:
        payload["system"] = system_install_hints()

    if extras:
        unknown = [e for e in extras if e not in PIP_EXTRAS]
        if unknown:
            payload["ok"] = False
            payload["error_code"] = "UNKNOWN_EXTRA"
            payload["message"] = f"Unknown extras: {', '.join(unknown)}"
            payload["recovery"] = {"hint": f"Choose from: {', '.join(sorted(PIP_EXTRAS))}"}
            return payload
        if install:
            result = install_pip_extras(extras, dry_run=dry_run)
            payload["install"] = result
            payload["ok"] = bool(result.get("ok"))
        else:
            specs = [PIP_EXTRAS[e] for e in extras]
            payload["install"] = {
                "ok": True,
                "dry_run": True,
                "message": "Pass --install to run pip (or copy the command).",
                "command": [sys.executable, "-m", "pip", "install", *specs],
                "extras": extras,
            }
    else:
        payload["suggested"] = {
            "recommended": "pip install 'pifang[doc,transcribe]'",
            "video_system": "Install ffmpeg on PATH, then: pip install 'pifang[transcribe]'",
            "opendataloader": "Optional: pip install 'pifang[doc-odl]' + JDK 11+, then --engine opendataloader",
        }
    return payload
