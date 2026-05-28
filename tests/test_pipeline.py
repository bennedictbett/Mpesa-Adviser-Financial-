"""
tests/test_pipeline.py
----------------------
Tests for src/rag/pipeline.py

Tests the full ingestion pipeline end to end.
Uses mocks so no real PDFs, embeddings, or ChromaDB are needed.
"""

import pytest
from unittest.mock import patch, MagicMock


# ── run_ingestion() tests ─────────────────────────────────────

def test_run_ingestion_raises_if_data_dir_missing():
    """run_ingestion() raises FileNotFoundError for non-existent directory."""
    from src.rag.pipeline import run_ingestion

    with pytest.raises(FileNotFoundError):
        run_ingestion("data/nonexistent_folder")


def test_run_ingestion_returns_summary_dict():
    """run_ingestion() returns a dict with the correct summary keys."""
    from src.rag.pipeline import run_ingestion

    mock_documents = [
        {"text": "M-Pesa tariff content", "source": "tariff.pdf"},
    ]
    mock_chunks = [
        {"text": "chunk 1", "source": "tariff.pdf", "chunk_id": "tariff.pdf_chunk_0"},
        {"text": "chunk 2", "source": "tariff.pdf", "chunk_id": "tariff.pdf_chunk_1"},
        {"text": "chunk 3", "source": "tariff.pdf", "chunk_id": "tariff.pdf_chunk_2"},
    ]

    with patch("src.rag.pipeline.load_documents",    return_value=mock_documents):
        with patch("src.rag.pipeline.split_documents",   return_value=mock_chunks):
            with patch("src.rag.pipeline.build_vectorstore", return_value=MagicMock()):
                summary = run_ingestion("data/raw")

    assert isinstance(summary, dict)
    assert "documents_loaded" in summary
    assert "chunks_created"   in summary
    assert "duration_seconds" in summary
    assert "sources"          in summary


def test_run_ingestion_summary_has_correct_counts():
    """run_ingestion() summary reflects actual document and chunk counts."""
    from src.rag.pipeline import run_ingestion

    mock_documents = [
        {"text": "doc one content", "source": "doc1.pdf"},
        {"text": "doc two content", "source": "doc2.pdf"},
    ]
    mock_chunks = [{"text": f"chunk {i}", "source": "doc1.pdf",
                    "chunk_id": f"doc1.pdf_chunk_{i}"} for i in range(10)]

    with patch("src.rag.pipeline.load_documents",    return_value=mock_documents):
        with patch("src.rag.pipeline.split_documents",   return_value=mock_chunks):
            with patch("src.rag.pipeline.build_vectorstore", return_value=MagicMock()):
                summary = run_ingestion("data/raw")

    assert summary["documents_loaded"] == 2
    assert summary["chunks_created"]   == 10
    assert set(summary["sources"])     == {"doc1.pdf", "doc2.pdf"}


def test_run_ingestion_calls_pipeline_steps_in_order():
    """run_ingestion() calls load → split → build in the correct order."""
    from src.rag.pipeline import run_ingestion

    call_order = []

    def mock_load(path):
        call_order.append("load")
        return [{"text": "content", "source": "test.pdf"}]

    def mock_split(docs):
        call_order.append("split")
        return [{"text": "chunk", "source": "test.pdf", "chunk_id": "test.pdf_chunk_0"}]

    def mock_build(chunks):
        call_order.append("build")
        return MagicMock()

    with patch("src.rag.pipeline.load_documents",    side_effect=mock_load):
        with patch("src.rag.pipeline.split_documents",   side_effect=mock_split):
            with patch("src.rag.pipeline.build_vectorstore", side_effect=mock_build):
                run_ingestion("data/raw")

    assert call_order == ["load", "split", "build"]


def test_run_ingestion_duration_is_positive():
    """run_ingestion() summary duration_seconds is always a positive number."""
    from src.rag.pipeline import run_ingestion

    with patch("src.rag.pipeline.load_documents",
               return_value=[{"text": "content", "source": "test.pdf"}]):
        with patch("src.rag.pipeline.split_documents",
                   return_value=[{"text": "chunk", "source": "test.pdf",
                                  "chunk_id": "test.pdf_chunk_0"}]):
            with patch("src.rag.pipeline.build_vectorstore",
                       return_value=MagicMock()):
                summary = run_ingestion("data/raw")

    assert summary["duration_seconds"] >= 0