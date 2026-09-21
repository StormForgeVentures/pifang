"""PDF metadata."""

from __future__ import annotations

from pathlib import Path

from pifang.errors import MissingDependencyError, ProcessingError, ValidationError


def pdf_info(path: Path) -> dict:
    if path.suffix.lower() != ".pdf":
        raise ValidationError(f"Not a PDF: {path}", "NOT_PDF")
    if not path.exists():
        raise ValidationError(f"File not found: {path}", "FILE_NOT_FOUND")

    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
    except ImportError as exc:
        raise MissingDependencyError("pypdf not installed", {"hint": "pip install pifang[doc]"}) from exc

    try:
        reader = PdfReader(str(path))
        meta = reader.metadata
        return {
            "path": str(path.resolve()),
            "pages": len(reader.pages),
            "encrypted": reader.is_encrypted,
            "title": meta.title if meta else None,
            "author": meta.author if meta else None,
        }
    except PdfReadError as exc:
        raise ProcessingError(
            f"Failed to read PDF: {exc}",
            "PDF_READ_FAILED",
            {"hint": "Ensure the file is a valid, non-truncated PDF"},
        ) from exc
    except Exception as exc:  # noqa: BLE001 — corrupt PDFs raise various pypdf errors
        # PdfStreamError and friends
        name = type(exc).__name__
        if "Pdf" in name or "Stream" in name or "EOF" in name or "read" in str(exc).lower():
            raise ProcessingError(
                f"Failed to read PDF: {exc}",
                "PDF_READ_FAILED",
                {"hint": "Ensure the file is a valid, non-truncated PDF"},
            ) from exc
        raise
