"""
tests/test_vectorstore.py
-------------------------
Tests for src/rag/vectorstore.py

Tests chunk storage, vectorstore building, and loading.
Uses mocks to avoid real API calls or disk writes during testing.
"""

import pytest
from unittest.mock import patch, MagicMock


# ── build_vectorstore() tests ─────────────────────────────────

def test_build_vectorstore_raises_on_empty_chunks():
    """build_vectorstore() raises ValueError when given empty chunks list."""
    from src.rag.vectorstore import build_vectorstore

    with pytest.raises(ValueError, match="No chunks provided"):
        build_vectorstore([])


def test_build_vectorstore_called_with_correct_ids():
    """build_vectorstore() passes chunk_ids as document IDs to ChromaDB."""
    from src.rag.vectorstore import build_vectorstore

    chunks = [
        {"text": "M-Pesa send fee KES 6", "source": "tariff.pdf", "chunk_id": "tariff.pdf_chunk_0"},
        {"text": "Withdraw KES 28",        "source": "tariff.pdf", "chunk_id": "tariff.pdf_chunk_1"},
    ]

    mock_vs = MagicMock()

    with patch("src.rag.vectorstore.Chroma.from_documents", return_value=mock_vs) as mock_build:
        with patch("src.rag.vectorstore.get_embeddings", return_value=MagicMock()):
            result = build_vectorstore(chunks)

    mock_build.assert_called_once()
    call_kwargs = mock_build.call_args.kwargs
    assert call_kwargs["ids"] == ["tariff.pdf_chunk_0", "tariff.pdf_chunk_1"]


def test_build_vectorstore_converts_chunks_to_documents():
    """build_vectorstore() converts chunk dicts to LangChain Document objects."""
    from src.rag.vectorstore import build_vectorstore
    from langchain_core.documents import Document

    chunks = [
        {"text": "Test chunk text", "source": "test.pdf", "chunk_id": "test.pdf_chunk_0"},
    ]

    captured_docs = []

    def capture_docs(**kwargs):
        captured_docs.extend(kwargs.get("documents", []))
        return MagicMock()

    with patch("src.rag.vectorstore.Chroma.from_documents", side_effect=capture_docs):
        with patch("src.rag.vectorstore.get_embeddings", return_value=MagicMock()):
            build_vectorstore(chunks)

    assert len(captured_docs) == 1
    assert isinstance(captured_docs[0], Document)
    assert captured_docs[0].page_content == "Test chunk text"
    assert captured_docs[0].metadata["source"] == "test.pdf"


# ── load_vectorstore() tests ──────────────────────────────────

def test_load_vectorstore_raises_if_chroma_db_missing():
    """load_vectorstore() raises RuntimeError if ChromaDB hasn't been built."""
    from src.rag.vectorstore import load_vectorstore

    # Clear lru_cache before testing
    load_vectorstore.cache_clear()

    with patch("src.rag.vectorstore.Path.exists", return_value=False):
        with pytest.raises(RuntimeError, match="ChromaDB not found"):
            load_vectorstore()

    load_vectorstore.cache_clear()


# ── add_chunks() tests ────────────────────────────────────────

def test_add_chunks_returns_zero_for_empty_list():
    """add_chunks() returns 0 and logs warning when given empty list."""
    from src.rag.vectorstore import add_chunks

    result = add_chunks([])
    assert result == 0


def test_add_chunks_returns_correct_count():
    """add_chunks() returns the number of chunks successfully added."""
    from src.rag.vectorstore import add_chunks, load_vectorstore

    load_vectorstore.cache_clear()

    chunks = [
        {"text": "chunk one", "source": "test.pdf", "chunk_id": "test.pdf_chunk_0"},
        {"text": "chunk two", "source": "test.pdf", "chunk_id": "test.pdf_chunk_1"},
    ]

    mock_vs = MagicMock()

    with patch("src.rag.vectorstore.load_vectorstore", return_value=mock_vs):
        result = add_chunks(chunks)

    assert result == 2
    mock_vs.add_documents.assert_called_once()