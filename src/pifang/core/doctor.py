"""Dependency health checks."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class DoctorReport:
    ok: bool
    checks: list[dict]

    def to_dict(self) -> dict:
        return {"ok": self.ok, "checks": self.checks}


def _java_check() -> dict:
    java = shutil.which("java")
    if not java:
        return {
            "name": "java",
            "ok": False,
            "optional": True,
            "message": "Java not found (only needed for --engine opendataloader)",
            "hint": "pifang setup  # prints JDK install commands; or use --engine fast",
        }
    try:
        proc = subprocess.run(
            [java, "-version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return {
            "name": "java",
            "ok": False,
            "optional": True,
            "message": "java -version timed out after 30s",
            "path": java,
        }
    version = (proc.stderr or proc.stdout or "").strip().split("\n")[0]
    return {"name": "java", "ok": proc.returncode == 0, "optional": True, "version": version, "path": java}


def run_doctor(*, doc: bool = False, video: bool = False, transcribe: bool = False) -> DoctorReport:
    checks: list[dict] = []

    try:
        import PIL

        from PIL import __version__ as pillow_version

        checks.append({"name": "pillow", "ok": True, "version": pillow_version, "path": PIL.__file__})
    except ImportError:
        checks.append(
            {
                "name": "pillow",
                "ok": False,
                "message": "Pillow not installed",
                "hint": "pip install pifang",
            }
        )

    if doc:
        try:
            import pymupdf4llm

            checks.append(
                {
                    "name": "pymupdf4llm",
                    "ok": True,
                    "version": getattr(pymupdf4llm, "__version__", "unknown"),
                    "note": "default doc engine (fast)",
                }
            )
        except ImportError:
            checks.append(
                {
                    "name": "pymupdf4llm",
                    "ok": False,
                    "hint": "pip install 'pifang[doc]'  # or: pifang setup --extras doc --install",
                }
            )

        try:
            import pypdf  # noqa: F401

            checks.append({"name": "pypdf", "ok": True})
        except ImportError:
            checks.append({"name": "pypdf", "ok": False, "hint": "pip install 'pifang[doc]'"})

        try:
            import opendataloader_pdf  # noqa: F401

            checks.append(
                {
                    "name": "opendataloader-pdf",
                    "ok": True,
                    "optional": True,
                    "note": "opt-in via --engine opendataloader",
                }
            )
            checks.append(_java_check())
        except ImportError:
            checks.append(
                {
                    "name": "opendataloader-pdf",
                    "ok": False,
                    "optional": True,
                    "hint": "pip install 'pifang[doc-odl]' + JDK 11+ (optional; default is --engine fast)",
                }
            )

        try:
            import docling  # noqa: F401

            checks.append({"name": "docling", "ok": True, "optional": True})
        except ImportError:
            checks.append({"name": "docling", "ok": False, "optional": True, "hint": "pip install 'pifang[doc-heavy]'"})

        marker = shutil.which("marker_single")
        checks.append(
            {
                "name": "marker",
                "ok": marker is not None,
                "optional": True,
                "path": marker,
                "hint": "pip install 'pifang[doc-heavy]'" if not marker else None,
            }
        )

        tess = shutil.which("tesseract")
        checks.append(
            {
                "name": "tesseract",
                "ok": tess is not None,
                "optional": True,
                "path": tess,
                "hint": "Install tesseract-ocr for doc ocr" if not tess else None,
            }
        )

    if video:
        ffmpeg = shutil.which("ffmpeg")
        ffprobe = shutil.which("ffprobe")
        checks.append(
            {
                "name": "ffmpeg",
                "ok": ffmpeg is not None,
                "path": ffmpeg,
                "hint": "Install system ffmpeg (see: pifang setup)" if not ffmpeg else None,
            }
        )
        checks.append(
            {
                "name": "ffprobe",
                "ok": ffprobe is not None,
                "path": ffprobe,
                "hint": "Install ffmpeg (includes ffprobe); see: pifang setup" if not ffprobe else None,
            }
        )

    if transcribe:
        try:
            import faster_whisper

            checks.append(
                {
                    "name": "faster-whisper",
                    "ok": True,
                    "version": getattr(faster_whisper, "__version__", "unknown"),
                }
            )
        except ImportError:
            checks.append(
                {
                    "name": "faster-whisper",
                    "ok": False,
                    "message": "faster-whisper not installed",
                    "hint": "pip install 'pifang[transcribe]'  # or: pifang setup --extras transcribe --install",
                }
            )

    ok = all(c.get("ok") for c in checks if not c.get("optional"))
    return DoctorReport(ok=ok, checks=checks)
