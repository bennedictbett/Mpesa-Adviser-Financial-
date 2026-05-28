"""
tests/test_loader.py
--------------------
Tests for src/rag/loader.py

Tests PDF discovery, loading, and the single document loader.
Uses a real PDF from data/raw/ if available, otherwise creates
a minimal test PDF in a temp directory.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.rag.loader import load_documents, load_single_document


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def mock_pdf_text():
    """Sample text that pdf_parser would return from a PDF."""
    return (
        "Benedict Bett\n"
        "Eldoret, Kenya\n"
        "Application for Industrial Attachment\n"
        "I am writing to apply for an industrial attachment opportunity.\n"
    )


# ── load_documents() tests ────────────────────────────────────

def test_load_documents_raises_if_dir_not_found():
    """load_documents() raises FileNotFoundError for non-existent directory."""
    with pytest.raises(FileNotFoundError):
        load_documents("data/nonexistent_folder")


def test_load_documents_raises_if_no_pdfs(temp_dir):
    """load_documents() raises RuntimeError when folder has no PDFs."""
    # Create a non-PDF file to ensure folder is not empty
    (temp_dir / "notes.txt").write_text("some text")

    with pytest.raises(RuntimeError, match="No supported files found"):
        load_documents(temp_dir)


def test_load_documents_returns_list_of_dicts(temp_dir, mock_pdf_text):
    """load_documents() returns list of dicts with text and source keys."""
    fake_pdf = temp_dir / "test.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 fake pdf content")

    with patch("src.rag.loader.extract_text_from_pdf", return_value=mock_pdf_text):
        docs = load_documents(temp_dir)

    assert isinstance(docs, list)
    assert len(docs) == 1
    assert "text" in docs[0]
    assert "source" in docs[0]
    assert docs[0]["source"] == "test.pdf"
    assert docs[0]["text"] == mock_pdf_text


def test_load_documents_skips_empty_pdfs(temp_dir):
    """load_documents() skips PDFs with no extractable text and logs a warning."""
    fake_pdf = temp_dir / "scanned.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 scanned image")

    with patch("src.rag.loader.extract_text_from_pdf", return_value=""):
        # All PDFs skipped → empty documents list returned
        # loader raises RuntimeError because no supported files loaded
        with pytest.raises(RuntimeError):
            load_documents(temp_dir)


def test_load_documents_source_is_filename_not_path(temp_dir, mock_pdf_text):
    """source field should be filename only, not full path."""
    fake_pdf = temp_dir / "mpesa_tariff.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 content")

    with patch("src.rag.loader.extract_text_from_pdf", return_value=mock_pdf_text):
        docs = load_documents(temp_dir)

    # source should be just the filename, not the full path
    assert docs[0]["source"] == "mpesa_tariff.pdf"
    assert str(temp_dir) not in docs[0]["source"]


# ── load_single_document() tests ─────────────────────────────

def test_load_single_document_raises_for_unsupported_type(temp_dir):
    """load_single_document() raises ValueError for non-PDF files."""
    txt_file = temp_dir / "document.txt"
    txt_file.write_text("some text")

    with pytest.raises(ValueError, match="Unsupported file type"):
        load_single_document(txt_file)


def test_load_single_document_raises_if_file_not_found():
    """load_single_document() raises FileNotFoundError for missing file."""
    with pytest.raises(FileNotFoundError):
        load_single_document("data/raw/nonexistent.pdf")


def test_load_single_document_returns_dict(temp_dir, mock_pdf_text):
    """load_single_document() returns a dict with text and source."""
    fake_pdf = temp_dir / "statement.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 content")

    with patch("src.rag.loader.extract_text_from_pdf", return_value=mock_pdf_text):
        doc = load_single_document(fake_pdf)

    assert isinstance(doc, dict)
    assert "text" in doc
    assert "source" in doc
    assert doc["source"] == "statement.pdf"
    assert doc["text"] == mock_pdf_text


def test_load_single_document_raises_if_no_text(temp_dir):
    """load_single_document() raises ValueError when PDF has no extractable text."""
    fake_pdf = temp_dir / "blank.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 blank")

    with patch("src.rag.loader.extract_text_from_pdf", return_value=""):
        with pytest.raises(ValueError, match="No text could be extracted"):
            load_single_document(fake_pdf)