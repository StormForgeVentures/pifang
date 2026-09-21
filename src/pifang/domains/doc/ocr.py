"""OCR scanned PDFs via Tesseract."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from pifang.errors import MissingDependencyError, ProcessingError, ValidationError

# Per-page OCR can be slow on large scans; default is generous.
DEFAULT_OCR_TIMEOUT = 3600


def ocr_pdf(
    input_path: Path,
    output_path: Path,
    *,
    lang: str = "eng",
    dpi: int = 300,
    timeout: float | None = DEFAULT_OCR_TIMEOUT,
) -> dict:
    """Render PDF pages and run Tesseract; write plain-text or .md output."""
    tesseract = shutil.which("tesseract")
    if not tesseract:
        raise MissingDependencyError("tesseract not found on PATH", {"hint": "Install tesseract-ocr system package"})

    try:
        import fitz
    except ImportError as exc:
        raise MissingDependencyError("pymupdf not installed", {"hint": "pip install pifang[doc]"}) from exc

    if not input_path.exists():
        raise ValidationError(f"File not found: {input_path}", "FILE_NOT_FOUND")

    doc = fitz.open(input_path)
    parts: list[str] = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=dpi)
        img_bytes = pix.tobytes("png")
        try:
            proc = subprocess.run(
                [tesseract, "stdin", "stdout", "-l", lang],
                input=img_bytes,
                capture_output=True,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            doc.close()
            raise ProcessingError(
                f"tesseract timed out after {timeout}s on page {i + 1}",
                "SUBPROCESS_TIMEOUT",
                {"hint": "Increase timeout or lower --dpi"},
            ) from exc
        if proc.returncode != 0:
            doc.close()
            raise ProcessingError(proc.stderr.decode() or "Tesseract failed", "OCR_FAILED")
        text = proc.stdout.decode("utf-8", errors="replace").strip()
        parts.append(f"## Page {i + 1}\n\n{text}\n")
    doc.close()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(parts)
    output_path.write_text(body, encoding="utf-8")
    return {
        "input": str(input_path.resolve()),
        "output": str(output_path.resolve()),
        "pages": len(parts),
        "lang": lang,
    }
