"""
tests/test_retriever.py
-----------------------
Tests for src/rag/retriever.py

Tests similarity search, threshold filtering, and context formatting.
Uses mocks to avoid real ChromaDB or embedding API calls.
"""

import pytest
from unittest.mock import patch, MagicMock
from langchain_core.documents import Document


# ── retrieve() tests ──────────────────────────────────────────

def test_retrieve_raises_on_empty_query():
    """retrieve() raises ValueError for empty or whitespace-only queries."""
    from src.rag.retriever import retrieve

    with pytest.raises(ValueError, match="Query cannot be empty"):
        retrieve("")

    with pytest.raises(ValueError, match="Query cannot be empty"):
        retrieve("   ")


def test_retrieve_returns_empty_list_when_no_chunks_pass_threshold():
    """retrieve() returns empty list when all distances exceed threshold."""
    from src.rag.retriever import retrieve

    # All distances above threshold of 2.1
    mock_results = [
        (Document(page_content="some chunk", metadata={"source": "test.pdf"}), 3.5),
        (Document(page_content="other chunk", metadata={"source": "test.pdf"}), 4.0),
    ]

    mock_vs = MagicMock()
    mock_vs.similarity_search_with_score.return_value = mock_results

    with patch("src.rag.retriever.load_vectorstore", return_value=mock_vs):
        results = retrieve("What is M-Pesa?")

    assert results == []


def test_retrieve_returns_chunks_below_threshold():
    """retrieve() returns chunks whose distance is below the threshold."""
    from src.rag.retriever import retrieve

    mock_results = [
        (Document(page_content="Sending KES 500 costs KES 6",
                  metadata={"source": "tariff.pdf"}), 1.5),
        (Document(page_content="Withdraw fee is KES 28",
                  metadata={"source": "tariff.pdf"}), 1.8),
        (Document(page_content="Irrelevant content",
                  metadata={"source": "other.pdf"}), 3.5),  # above threshold
    ]

    mock_vs = MagicMock()
    mock_vs.similarity_search_with_score.return_value = mock_results

    with patch("src.rag.retriever.load_vectorstore", return_value=mock_vs):
        results = retrieve("How much to send KES 500?")

    # Only 2 chunks should pass (distance <= 2.1)
    assert len(results) == 2
    assert results[0]["source"] == "tariff.pdf"
    assert "text" in results[0]
    assert "relevance" in results[0]


def test_retrieve_result_has_correct_keys():
    """retrieve() result dicts have text, source, and relevance keys."""
    from src.rag.retriever import retrieve

    mock_results = [
        (Document(page_content="M-Pesa tariff info",
                  metadata={"source": "tariff.pdf"}), 1.7),
    ]

    mock_vs = MagicMock()
    mock_vs.similarity_search_with_score.return_value = mock_results

    with patch("src.rag.retriever.load_vectorstore", return_value=mock_vs):
        results = retrieve("M-Pesa fees")

    assert len(results) == 1
    assert set(results[0].keys()) == {"text", "source", "relevance"}


def test_retrieve_results_sorted_by_relevance_descending():
    """retrieve() returns results sorted highest relevance first."""
    from src.rag.retriever import retrieve

    mock_results = [
        (Document(page_content="Less relevant", metadata={"source": "a.pdf"}), 2.0),
        (Document(page_content="Most relevant",  metadata={"source": "b.pdf"}), 1.5),
        (Document(page_content="Mid relevant",   metadata={"source": "c.pdf"}), 1.8),
    ]

    mock_vs = MagicMock()
    mock_vs.similarity_search_with_score.return_value = mock_results

    with patch("src.rag.retriever.load_vectorstore", return_value=mock_vs):
        results = retrieve("test query")

    # Best match (lowest distance = highest relevance) should be first
    assert results[0]["relevance"] >= results[1]["relevance"]
    assert results[1]["relevance"] >= results[2]["relevance"]


# ── format_context() tests ────────────────────────────────────

def test_format_context_returns_empty_string_for_empty_results():
    """format_context() returns empty string when given empty list."""
    from src.rag.retriever import format_context

    result = format_context([])
    assert result == ""


def test_format_context_includes_source_and_text():
    """format_context() includes source name and chunk text in output."""
    from src.rag.retriever import format_context

    results = [
        {"text": "Sending KES 500 costs KES 6", "source": "tariff.pdf", "relevance": 0.85},
    ]

    context = format_context(results)

    assert "tariff.pdf" in context
    assert "Sending KES 500 costs KES 6" in context
    assert "0.85" in context


def test_format_context_separates_multiple_chunks():
    """format_context() separates multiple chunks with double newline."""
    from src.rag.retriever import format_context

    results = [
        {"text": "Chunk one text", "source": "doc1.pdf", "relevance": 0.9},
        {"text": "Chunk two text", "source": "doc2.pdf", "relevance": 0.7},
    ]

    context = format_context(results)

    assert "Chunk one text" in context
    assert "Chunk two text" in context
    assert "\n\n" in context