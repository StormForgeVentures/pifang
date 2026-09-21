"""Basic PDF operations — split, merge, extract images."""

from __future__ import annotations

from pathlib import Path

from pifang.errors import MissingDependencyError, ProcessingError, ValidationError


def _pdf_read_error(exc: BaseException) -> ProcessingError:
    return ProcessingError(
        f"Failed to read PDF: {exc}",
        "PDF_READ_FAILED",
        {"hint": "Ensure the file is a valid, non-truncated PDF"},
    )


def _is_pdf_error(exc: BaseException) -> bool:
    name = type(exc).__name__
    return (
        "Pdf" in name
        or "Stream" in name
        or "EOF" in name
        or "read" in str(exc).lower()
        or "parse" in str(exc).lower()
    )


def split_pdf(input_path: Path, output_dir: Path, *, pages: str | None = None) -> dict:
    """Split PDF into per-page files or a page range."""
    try:
        from pypdf import PdfReader, PdfWriter
        from pypdf.errors import PdfReadError
    except ImportError as exc:
        raise MissingDependencyError("pypdf not installed", {"hint": "pip install pifang[doc]"}) from exc

    if not input_path.exists():
        raise ValidationError(f"File not found: {input_path}", "FILE_NOT_FOUND")
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        reader = PdfReader(str(input_path))
        total = len(reader.pages)

        indices = list(range(total))
        if pages:
            indices = _parse_page_range(pages, total)

        outputs: list[str] = []
        for i in indices:
            writer = PdfWriter()
            writer.add_page(reader.pages[i])
            out = output_dir / f"{input_path.stem}-page-{i + 1:03d}.pdf"
            with out.open("wb") as fh:
                writer.write(fh)
            outputs.append(str(out.resolve()))

        return {"input": str(input_path.resolve()), "pages_written": len(outputs), "outputs": outputs}
    except PdfReadError as exc:
        raise _pdf_read_error(exc) from exc
    except Exception as exc:  # noqa: BLE001
        if _is_pdf_error(exc):
            raise _pdf_read_error(exc) from exc
        raise


def merge_pdfs(inputs: list[Path], output_path: Path) -> dict:
    try:
        from pypdf import PdfReader, PdfWriter
        from pypdf.errors import PdfReadError
    except ImportError as exc:
        raise MissingDependencyError("pypdf not installed", {"hint": "pip install pifang[doc]"}) from exc

    if len(inputs) < 2:
        raise ValidationError("Merge requires at least two PDF inputs", "MERGE_INPUTS")
    try:
        writer = PdfWriter()
        for path in inputs:
            if not path.exists():
                raise ValidationError(f"File not found: {path}", "FILE_NOT_FOUND")
            reader = PdfReader(str(path))
            for page in reader.pages:
                writer.add_page(page)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("wb") as fh:
            writer.write(fh)
        return {
            "output": str(output_path.resolve()),
            "inputs": [str(p.resolve()) for p in inputs],
            "pages": len(writer.pages),
        }
    except ValidationError:
        raise
    except PdfReadError as exc:
        raise _pdf_read_error(exc) from exc
    except Exception as exc:  # noqa: BLE001
        if _is_pdf_error(exc):
            raise _pdf_read_error(exc) from exc
        raise


def extract_images(input_path: Path, output_dir: Path) -> dict:
    try:
        import fitz
    except ImportError as exc:
        raise MissingDependencyError("pymupdf not installed", {"hint": "pip install pifang[doc]"}) from exc

    if not input_path.exists():
        raise ValidationError(f"File not found: {input_path}", "FILE_NOT_FOUND")
    output_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(input_path)
    outputs: list[str] = []
    seen = 0
    for page_index in range(len(doc)):
        for img_index, img in enumerate(doc.get_page_images(page_index)):
            xref = img[0]
            base = doc.extract_image(xref)
            seen += 1
            ext = base.get("ext", "png")
            out = output_dir / f"{input_path.stem}-p{page_index + 1:03d}-img{img_index + 1}.{ext}"
            out.write_bytes(base["image"])
            outputs.append(str(out.resolve()))
    doc.close()
    return {
        "input": str(input_path.resolve()),
        "output_dir": str(output_dir.resolve()),
        "image_count": len(outputs),
        "outputs": outputs,
    }


def _parse_page_range(spec: str, total: int) -> list[int]:
    """Parse '1,3-5' (1-based inclusive) to 0-based indices."""
    indices: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            start = int(a) - 1
            end = int(b) - 1
            indices.extend(range(max(0, start), min(total, end + 1)))
        else:
            idx = int(part) - 1
            if 0 <= idx < total:
                indices.append(idx)
    return sorted(set(indices))
