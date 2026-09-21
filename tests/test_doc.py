"""Extended document, text, and meta tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pifang.domains.doc.ingest import convert_batch, ingest_batch, ingest_one
from pifang.domains.doc.info import pdf_info
from pifang.domains.doc.pdf_ops import extract_images, merge_pdfs, split_pdf
from pifang.domains.meta.index import build_index, validate_ingest_manifest
from pifang.domains.text.chunk import chunk_markdown, chunk_markdown_file
from pifang.domains.text.frontmatter import add_frontmatter


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    import fitz

    path = tmp_path / "sample.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello from Pifang doc ingest test.")
    doc.save(path)
    doc.close()
    return path


@pytest.fixture
def two_page_pdf(tmp_path: Path) -> Path:
    import fitz

    path = tmp_path / "two-page.pdf"
    doc = fitz.open()
    for text in ("Page one", "Page two"):
        page = doc.new_page()
        page.insert_text((72, 72), text)
    doc.save(path)
    doc.close()
    return path


def test_pdf_info(sample_pdf: Path) -> None:
    info = pdf_info(sample_pdf)
    assert info["pages"] == 1
    assert info["encrypted"] is False


def test_ingest_fast_engine(sample_pdf: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = ingest_one(sample_pdf, out, engine_name="fast")
    assert result.ok
    assert result.markdown_path and result.markdown_path.exists()
    text = result.markdown_path.read_text(encoding="utf-8")
    assert "Hello" in text or "Pifang" in text


def test_ingest_batch(sample_pdf: Path, tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "a.pdf").write_bytes(sample_pdf.read_bytes())
    out = tmp_path / "ingested"
    batch = ingest_batch(corpus, out, engine_name="fast")
    assert batch.ok
    assert (out / "ingest.jsonl").exists()
    assert (out / "a.md").exists()


def test_convert_no_manifest_or_engine_json(sample_pdf: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    batch = convert_batch(sample_pdf, out, engine_name="fast")
    assert batch.ok
    assert batch.command == "doc.convert"
    assert batch.manifest_path is None
    assert (out / "sample.md").exists()
    assert not (out / "ingest.jsonl").exists()
    assert not (out / "sample.json").exists()


def test_doc_convert_cli(sample_pdf: Path, tmp_path: Path) -> None:
    import subprocess
    import sys

    out = tmp_path / "cli-out"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pifang.cli.main",
            "--json",
            "doc",
            "convert",
            str(sample_pdf),
            "-o",
            str(out),
            "--engine",
            "fast",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    assert data["command"] == "doc.convert"
    assert data["manifest"] is None
    assert (out / "sample.md").exists()
    assert not (out / "ingest.jsonl").exists()


def test_ingest_space_named_pdf(sample_pdf: Path, tmp_path: Path) -> None:
    pytest.importorskip("pymupdf4llm")
    spaced = tmp_path / "HMDAZW Print Ready.pdf"
    spaced.write_bytes(sample_pdf.read_bytes())
    out = tmp_path / "out"
    result = ingest_one(spaced, out, engine_name="fast")
    assert result.ok, result.error
    assert result.markdown_path == out / "HMDAZW_Print_Ready.md"
    assert result.markdown_path.exists()
    if result.images_dir is not None:
        assert result.images_dir.name == "HMDAZW_Print_Ready_images"
        assert result.images_dir.exists()


def test_ingest_manifest_merges_across_runs(sample_pdf: Path, tmp_path: Path) -> None:
    out = tmp_path / "ingested"
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    first.write_bytes(sample_pdf.read_bytes())
    second.write_bytes(sample_pdf.read_bytes())

    batch1 = ingest_batch(first, out, engine_name="fast")
    assert batch1.ok
    batch2 = ingest_batch(second, out, engine_name="fast")
    assert batch2.ok

    lines = (out / "ingest.jsonl").read_text(encoding="utf-8").strip().splitlines()
    rows = [json.loads(line) for line in lines]
    inputs = {row["input"] for row in rows}
    assert str(first.resolve()) in inputs
    assert str(second.resolve()) in inputs
    assert len(rows) == 2

    # Re-ingest first: replace entry, do not duplicate
    batch3 = ingest_batch(first, out, engine_name="fast")
    assert batch3.ok
    lines_again = (out / "ingest.jsonl").read_text(encoding="utf-8").strip().splitlines()
    rows_again = [json.loads(line) for line in lines_again]
    assert len(rows_again) == 2
    assert {row["input"] for row in rows_again} == inputs


def test_doc_ingest_cli(sample_pdf: Path, tmp_path: Path) -> None:
    import subprocess
    import sys

    out = tmp_path / "cli-out"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pifang.cli.main",
            "--json",
            "doc",
            "ingest",
            str(sample_pdf),
            "-o",
            str(out),
            "--engine",
            "fast",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    assert (out / "sample.md").exists()


def test_split_pdf(two_page_pdf: Path, tmp_path: Path) -> None:
    out = tmp_path / "split"
    data = split_pdf(two_page_pdf, out)
    assert data["pages_written"] == 2
    assert len(data["outputs"]) == 2


def test_merge_pdfs(two_page_pdf: Path, sample_pdf: Path, tmp_path: Path) -> None:
    merged = tmp_path / "merged.pdf"
    data = merge_pdfs([sample_pdf, two_page_pdf], merged)
    assert merged.exists()
    assert data["pages"] == 3


def test_extract_images(sample_pdf: Path, tmp_path: Path) -> None:
    out = tmp_path / "imgs"
    data = extract_images(sample_pdf, out)
    assert data["image_count"] >= 0


def test_chunk_by_heading() -> None:
    md = "# One\n\nA\n\n## Two\n\nB"
    chunks = chunk_markdown(md, mode="heading")
    assert len(chunks) == 2
    assert chunks[0]["title"] == "One"


def test_chunk_file(tmp_path: Path) -> None:
    src = tmp_path / "doc.md"
    src.write_text("# Title\n\nBody paragraph.\n\n## Section\n\nMore text.", encoding="utf-8")
    out = tmp_path / "chunks"
    data = chunk_markdown_file(src, out, mode="heading")
    assert data["chunk_count"] >= 1
    assert Path(data["manifest"]).exists()


def test_frontmatter(tmp_path: Path) -> None:
    src = tmp_path / "note.md"
    src.write_text("# Hello\n", encoding="utf-8")
    add_frontmatter(src, {"title": "Hello", "source": "test"})
    text = src.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "title: Hello" in text


def test_meta_index_and_validate(sample_pdf: Path, tmp_path: Path) -> None:
    out = tmp_path / "ingested"
    ingest_batch(sample_pdf, out, engine_name="fast")
    idx = build_index(out)
    assert idx["count"] >= 1
    manifest = out / "ingest.jsonl"
    report = validate_ingest_manifest(manifest)
    assert report["valid"] is True


def test_doc_split_cli(two_page_pdf: Path, tmp_path: Path) -> None:
    import subprocess
    import sys

    out = tmp_path / "split"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pifang.cli.main",
            "--json",
            "doc",
            "split",
            str(two_page_pdf),
            "-o",
            str(out),
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert len(list(out.glob("*.pdf"))) == 2


def test_ingest_resume_warns_on_corrupt_jsonl(sample_pdf: Path, tmp_path: Path, capsys) -> None:
    out = tmp_path / "ingested"
    out.mkdir()
    manifest = out / "ingest.jsonl"
    # Valid prior entry + corrupt line + blank + another valid-looking junk
    good_input = str((tmp_path / "prior.pdf").resolve())
    manifest.write_text(
        "\n".join(
            [
                json.dumps({"ok": True, "input": good_input, "markdown": None}),
                "{not valid json",
                "",
                '{"ok": true, "input": ',  # truncated
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    pdf = tmp_path / "fresh.pdf"
    pdf.write_bytes(sample_pdf.read_bytes())
    batch = ingest_batch(pdf, out, engine_name="fast")
    assert batch.ok
    assert len(batch.warnings) >= 2
    assert any("line 2" in w for w in batch.warnings)
    assert any("line 4" in w for w in batch.warnings)
    captured = capsys.readouterr()
    assert "line 2" in captured.err
    payload = batch.to_dict()
    assert "warnings" in payload
    assert any("line 2" in w for w in payload["warnings"])
    # Prior good entry preserved + new pdf
    lines = manifest.read_text(encoding="utf-8").strip().splitlines()
    rows = [json.loads(line) for line in lines]
    inputs = {row["input"] for row in rows}
    assert good_input in inputs
    assert str(pdf.resolve()) in inputs
