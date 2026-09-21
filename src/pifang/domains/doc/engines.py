"""PDF → markdown engine backends."""

from __future__ import annotations

import re
import shutil
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path

from pifang.errors import MissingDependencyError, ProcessingError, ValidationError

# Short probes (java -version) vs long jobs (marker PDF conversion)
DEFAULT_PROBE_TIMEOUT = 30
DEFAULT_MARKER_TIMEOUT = 3600


class DocEngine(ABC):
    name: str

    @abstractmethod
    def ingest(
        self,
        pdf_path: Path,
        output_dir: Path,
        stem: str,
        *,
        write_json: bool = True,
    ) -> tuple[Path, Path | None, Path | None, int]:
        """Return (markdown_path, images_dir|None, json_path|None, image_count)."""


class PyMuPDF4LLMEngine(DocEngine):
    name = "fast"

    def ingest(
        self,
        pdf_path: Path,
        output_dir: Path,
        stem: str,
        *,
        write_json: bool = True,
    ) -> tuple[Path, Path | None, Path | None, int]:
        try:
            import pymupdf4llm
        except ImportError as exc:
            raise MissingDependencyError(
                "pymupdf4llm not installed",
                {"hint": "pip install pifang[doc]"},
            ) from exc

        md_path = output_dir / f"{stem}.md"
        images_dir = output_dir / f"{stem}_images"
        images_dir.mkdir(parents=True, exist_ok=True)

        md_text = pymupdf4llm.to_markdown(
            str(pdf_path),
            write_images=True,
            image_path=str(images_dir),
            image_format="png",
        )
        md_path.write_text(md_text, encoding="utf-8")
        image_count = len(list(images_dir.glob("*"))) if images_dir.exists() else 0
        return md_path, images_dir if image_count else None, None, image_count


class OpenDataLoaderEngine(DocEngine):
    name = "opendataloader"

    def ingest(
        self,
        pdf_path: Path,
        output_dir: Path,
        stem: str,
        *,
        write_json: bool = True,
    ) -> tuple[Path, Path | None, Path | None, int]:
        try:
            import opendataloader_pdf
        except ImportError as exc:
            raise MissingDependencyError(
                "opendataloader-pdf not installed",
                {
                    "hint": (
                        "Optional engine. pip install 'pifang[doc-odl]' and JDK 11+, "
                        "or use default --engine fast (pip install 'pifang[doc]'). "
                        "See: pifang setup --extras doc-odl"
                    )
                },
            ) from exc

        _check_java()

        work = output_dir / f".pifang-odl-{stem}"
        if work.exists():
            shutil.rmtree(work)
        work.mkdir(parents=True)

        fmt = "markdown,json" if write_json else "markdown"
        opendataloader_pdf.convert(
            input_path=[str(pdf_path)],
            output_dir=str(work),
            format=fmt,
        )

        md_path = output_dir / f"{stem}.md"
        images_dir = output_dir / f"{stem}_images"
        json_path: Path | None = output_dir / f"{stem}.json" if write_json else None
        images_dir.mkdir(parents=True, exist_ok=True)

        md_candidates = list(work.rglob("*.md"))
        if not md_candidates:
            raise ProcessingError("OpenDataLoader produced no markdown", "INGEST_NO_MARKDOWN")
        shutil.copy2(md_candidates[0], md_path)

        if write_json:
            json_candidates = list(work.rglob("*.json"))
            if json_candidates:
                assert json_path is not None
                shutil.copy2(json_candidates[0], json_path)
            else:
                json_path = None

        image_count = 0
        for img in work.rglob("*"):
            if img.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".gif") and img.is_file():
                dest = images_dir / img.name
                if not dest.exists():
                    shutil.copy2(img, dest)
                image_count += 1

        shutil.rmtree(work, ignore_errors=True)
        _rewrite_image_refs(md_path, images_dir, stem)
        return md_path, images_dir if image_count else None, json_path, image_count


class MarkerEngine(DocEngine):
    name = "marker"

    def ingest(
        self,
        pdf_path: Path,
        output_dir: Path,
        stem: str,
        *,
        write_json: bool = True,
        timeout: float | None = DEFAULT_MARKER_TIMEOUT,
    ) -> tuple[Path, Path | None, Path | None, int]:
        marker = shutil.which("marker_single")
        if not marker:
            raise MissingDependencyError(
                "marker_single not found",
                {"hint": "pip install pifang[doc-heavy] or marker-pdf"},
            )

        work = output_dir / f".pifang-marker-{stem}"
        if work.exists():
            shutil.rmtree(work)
        work.mkdir(parents=True)

        try:
            proc = subprocess.run(
                [marker, str(pdf_path), "--output_dir", str(work), "--output_format", "markdown"],
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            shutil.rmtree(work, ignore_errors=True)
            raise ProcessingError(
                f"marker_single timed out after {timeout}s",
                "SUBPROCESS_TIMEOUT",
                {"hint": "Increase timeout or use a lighter --engine (fast)"},
            ) from exc
        if proc.returncode != 0:
            shutil.rmtree(work, ignore_errors=True)
            raise ProcessingError(
                proc.stderr or proc.stdout or "Marker failed",
                "INGEST_MARKER_FAILED",
            )

        md_path = output_dir / f"{stem}.md"
        images_dir = output_dir / f"{stem}_images"
        images_dir.mkdir(parents=True, exist_ok=True)

        md_candidates = list(work.rglob("*.md"))
        if not md_candidates:
            shutil.rmtree(work, ignore_errors=True)
            raise ProcessingError("Marker produced no markdown", "INGEST_NO_MARKDOWN")
        shutil.copy2(md_candidates[0], md_path)

        image_count = 0
        for img in work.rglob("*"):
            if img.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".gif") and img.is_file():
                dest = images_dir / img.name
                if not dest.exists():
                    shutil.copy2(img, dest)
                image_count += 1

        shutil.rmtree(work, ignore_errors=True)
        _rewrite_image_refs(md_path, images_dir, stem)
        return md_path, images_dir if image_count else None, None, image_count


class DoclingEngine(DocEngine):
    name = "docling"

    def ingest(
        self,
        pdf_path: Path,
        output_dir: Path,
        stem: str,
        *,
        write_json: bool = True,
    ) -> tuple[Path, Path | None, Path | None, int]:
        try:
            from docling.document_converter import DocumentConverter
            from docling_core.types.doc import ImageRefMode
        except ImportError as exc:
            raise MissingDependencyError(
                "docling not installed",
                {"hint": "pip install pifang[doc-heavy] or docling"},
            ) from exc

        md_path = output_dir / f"{stem}.md"
        images_dir = output_dir / f"{stem}_images"
        images_dir.mkdir(parents=True, exist_ok=True)

        result = DocumentConverter().convert(str(pdf_path))
        result.document.save_as_markdown(md_path, image_mode=ImageRefMode.REFERENCED)

        image_count = 0
        for img in output_dir.glob(f"{stem}*"):
            if img.is_file() and img.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".gif") and img != md_path:
                dest = images_dir / img.name
                if not dest.exists():
                    shutil.move(str(img), dest)
                image_count += 1
        for img in md_path.parent.glob("*.png"):
            if img.parent == output_dir and img.stem.startswith(stem):
                dest = images_dir / img.name
                if not dest.exists():
                    shutil.move(str(img), dest)
                image_count += 1

        _rewrite_image_refs(md_path, images_dir, stem)
        return md_path, images_dir if image_count else None, None, image_count


def _check_java() -> None:
    hint = (
        "OpenDataLoader needs JDK 11+. Install a JRE/JDK, or use the default pure-Python engine: "
        "--engine fast (pip install 'pifang[doc]'). Optional: pip install 'pifang[doc-odl]' + "
        "`pifang setup` for install commands."
    )
    try:
        proc = subprocess.run(
            ["java", "-version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=DEFAULT_PROBE_TIMEOUT,
        )
        if proc.returncode != 0:
            raise MissingDependencyError("Java not found", {"hint": hint})
    except FileNotFoundError as exc:
        raise MissingDependencyError("Java not found", {"hint": hint}) from exc
    except subprocess.TimeoutExpired as exc:
        raise ProcessingError(
            f"java -version timed out after {DEFAULT_PROBE_TIMEOUT}s",
            "SUBPROCESS_TIMEOUT",
            {"hint": hint},
        ) from exc


def _rewrite_image_refs(md_path: Path, images_dir: Path, stem: str) -> None:
    """Normalize markdown image paths to {stem}_images/filename."""
    if not md_path.exists():
        return
    text = md_path.read_text(encoding="utf-8")
    rel_prefix = f"{stem}_images/"

    def repl(match: re.Match[str]) -> str:
        alt, path = match.group(1), match.group(2)
        name = Path(path).name
        return f"![{alt}]({rel_prefix}{name})"

    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", repl, text)
    md_path.write_text(text, encoding="utf-8")


ENGINES: dict[str, type[DocEngine]] = {
    "fast": PyMuPDF4LLMEngine,
    "pymupdf4llm": PyMuPDF4LLMEngine,
    "opendataloader": OpenDataLoaderEngine,
    "odl": OpenDataLoaderEngine,
    "marker": MarkerEngine,
    "docling": DoclingEngine,
}


def get_engine(name: str) -> DocEngine:
    key = name.lower().strip()
    cls = ENGINES.get(key)
    if not cls:
        raise ValidationError(
            f"Unknown engine: {name}",
            "UNKNOWN_ENGINE",
            {"hint": "fast (default), opendataloader, marker, docling"},
        )
    return cls()


def default_engine() -> DocEngine:
    """Prefer pure-Python `fast` (pymupdf4llm). OpenDataLoader is opt-in via --engine."""
    return PyMuPDF4LLMEngine()
