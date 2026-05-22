"""
src/rag/retriever.py
--------------------
Searches ChromaDB for the most relevant document chunks
given a user's question.

Responsibilities:
  - Receive a user question as a string
  - Embed the question using the same embeddings model used during ingestion
  - Search ChromaDB for the top-k most similar chunks
  - Filter out chunks below the score threshold
  - Return a clean list of result dicts ready for chain.py

How similarity search works:
  1. The user's question is converted to a vector (1,536 numbers)
     using the same OpenAI embedding model used during ingestion
  2. ChromaDB compares that vector against all stored chunk vectors
     using cosine similarity
  3. The chunks with the highest similarity scores are returned
  4. Chunks below score_threshold (0.3) are filtered out —
     they are not relevant enough to be useful context for Claude

What is a result here?
  A result is a dict with three keys:
    {
        "text":      str,   # the chunk text Claude will read
        "source":    str,   # filename for citation
        "relevance": float, # similarity score 0.0 → 1.0
    }

Only one file imports from here: chain.py
"""

import logging
from src.rag import settings
from src.rag.vectorstore import load_vectorstore

logger = logging.getLogger(__name__)


def retrieve(query: str, top_k: int | None = None) -> list[dict]:
    """
    Search ChromaDB for the most relevant chunks for a given query.

    Embeds the query, runs similarity search against ChromaDB,
    filters results by score threshold, and returns the top matches
    as clean dicts ready for chain.py to inject into the prompt.

    Args:
        query:  The user's question as a plain string
        top_k:  Number of chunks to retrieve.
                Defaults to settings.retriever.top_k from config.yaml.
                Pass an int to override for specific use cases.

    Returns:
        list[dict]: List of result dicts ordered by relevance (highest first).
                    Each dict has:
                    - "text"      (str)   chunk text
                    - "source"    (str)   original filename
                    - "relevance" (float) similarity score 0.0 → 1.0
                    Returns empty list if no chunks meet the score threshold.

    Raises:
        ValueError: if query is empty or whitespace only
        RuntimeError: if ChromaDB has not been built yet
    """
    # ── Guard: query must not be empty ────────────────────────
    if not query or not query.strip():
        raise ValueError(
            "Query cannot be empty. "
            "Pass a non-empty question string to retrieve()."
        )

    k              = top_k or settings.retriever.top_k
    threshold      = settings.retriever.score_threshold
    clean_query    = query.strip()

    logger.info(
        f"Retrieving chunks | "
        f"top_k: {k} | "
        f"threshold: {threshold} | "
        f"query: '{clean_query[:80]}{'...' if len(clean_query) > 80 else ''}'"
    )

    # ── Load vectorstore and run similarity search ────────────
    vectorstore = load_vectorstore()

    # similarity_search_with_relevance_scores returns:
    # list of (Document, score) tuples ordered by score descending
    results_with_scores = vectorstore.similarity_search_with_relevance_scores(
        query=clean_query,
        k=k,
    )

    # ── Filter by score threshold ─────────────────────────────
    filtered = [
        (doc, score)
        for doc, score in results_with_scores
        if score >= threshold
    ]

    logger.info(
        f"Search complete — "
        f"{len(results_with_scores)} results found, "
        f"{len(filtered)} above threshold ({threshold})"
    )

    # ── No relevant chunks found ──────────────────────────────
    if not filtered:
        logger.warning(
            f"No chunks above threshold {threshold} found for query: "
            f"'{clean_query[:80]}'. "
            f"chain.py will use NO_CONTEXT_PROMPT."
        )
        return []

    # ── Build clean result dicts ──────────────────────────────
    results = []
    for doc, score in filtered:
        results.append({
            "text":      doc.page_content,
            "source":    doc.metadata.get("source", "unknown"),
            "relevance": round(score, 4),
        })
        logger.debug(
            f"  chunk: '{doc.page_content[:60]}...' | "
            f"source: {doc.metadata.get('source')} | "
            f"score: {round(score, 4)}"
        )

    return results


def format_context(results: list[dict]) -> str:
    """
    Format retrieved chunks into a single context string for the prompt.

    Takes the list of result dicts from retrieve() and formats them
    into a clean string that chain.py injects into the {context}
    placeholder in RAG_PROMPT.

    Each chunk is labelled with its source filename so Claude knows
    which document each piece of information came from and can cite it.

    Args:
        results: List of result dicts from retrieve()

    Returns:
        str: Formatted context string ready for prompt injection.
             Returns empty string if results list is empty.

    Example output:
        [Source: mpesa_tariff_2024.pdf | Relevance: 0.87]
        Sending KES 101 to KES 500 costs KES 6...

        [Source: cbk_guidelines.pdf | Relevance: 0.74]
        The maximum single transaction limit for mobile money...
    """
    if not results:
        return ""

    context_parts = []
    for result in results:
        part = (
            f"[Source: {result['source']} | Relevance: {result['relevance']}]\n"
            f"{result['text']}"
        )
        context_parts.append(part)

    return "\n\n".join(context_parts)