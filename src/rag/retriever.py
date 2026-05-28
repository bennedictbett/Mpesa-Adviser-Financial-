"""
src/rag/retriever.py
--------------------
Searches ChromaDB for the most relevant document chunks
given a user's question.

Fix note:
  Previously used similarity_search_with_relevance_scores which returns
  inconsistent negative scores with HuggingFace embeddings + ChromaDB.
  Now uses similarity_search_with_score which returns raw L2 distance
  scores (always positive, lower = more similar = better match).

  Distance score interpretation:
    0.0 → 0.5  = highly relevant
    0.5 → 1.0  = moderately relevant
    1.0+        = not relevant, filtered out

  config.yaml score_threshold should now be set to 1.0
  (filter out anything with distance > 1.0)
"""

import logging
from src.rag import settings
from src.rag.vectorstore import load_vectorstore

logger = logging.getLogger(__name__)


def retrieve(query: str, top_k: int | None = None) -> list[dict]:
    """
    Search ChromaDB for the most relevant chunks for a given query.

    Uses L2 distance scoring — lower distance = more relevant.
    Filters out chunks with distance above score_threshold.

    Args:
        query:  The user's question as a plain string
        top_k:  Number of chunks to retrieve.
                Defaults to settings.retriever.top_k from config.yaml.

    Returns:
        list[dict]: List of result dicts ordered by relevance (closest first).
                    Each dict has:
                    - "text"      (str)   chunk text
                    - "source"    (str)   original filename
                    - "relevance" (float) relevance score 0.0 → 1.0
                      (converted from distance for readability)
                    Returns empty list if no chunks meet the threshold.

    Raises:
        ValueError: if query is empty or whitespace only
        RuntimeError: if ChromaDB has not been built yet
    """
    if not query or not query.strip():
        raise ValueError(
            "Query cannot be empty. "
            "Pass a non-empty question string to retrieve()."
        )

    k           = top_k or settings.retriever.top_k
    threshold   = settings.retriever.score_threshold
    clean_query = query.strip()

    logger.info(
        "Retrieving chunks | top_k: %d | threshold: %s | query: '%s%s'",
        k,
        threshold,
        clean_query[:80],
        "..." if len(clean_query) > 80 else "",
    )

    # ── Load vectorstore and run similarity search ────────────
    vectorstore = load_vectorstore()

    # similarity_search_with_score returns (Document, distance) tuples
    # distance is L2 — lower is better, always >= 0
    results_with_scores = vectorstore.similarity_search_with_score(
        query=clean_query,
        k=k,
    )

    logger.info(
        "Raw scores: %s",
        [(round(s, 4), doc.metadata.get("source")) 
         for doc, s in results_with_scores]
    )

    # ── Filter by distance threshold ──────────────────────────
    # Keep chunks where distance is BELOW threshold
    # (lower distance = more similar = better)
    filtered = [
        (doc, score)
        for doc, score in results_with_scores
        if score <= threshold
    ]

    logger.info(
        "Search complete — %d results found, %d below threshold (%.1f)",
        len(results_with_scores),
        len(filtered),
        threshold,
    )

    # ── No relevant chunks found ──────────────────────────────
    if not filtered:
        logger.warning(
            "No chunks below distance threshold %.1f for query: '%s'. "
            "chain.py will use NO_CONTEXT_PROMPT.",
            threshold,
            clean_query[:80],
        )
        return []

    #  Build clean result dicts 
    # Convert distance → relevance score (1.0 - normalised distance)
    # so higher relevance = better match (more intuitive for chain.py)
    results = []
    for doc, distance in filtered:
        relevance = round(max(0.0, 1.0 - distance), 4)
        results.append({
            "text":      doc.page_content,
            "source":    doc.metadata.get("source", "unknown"),
            "relevance": relevance,
        })
        logger.debug(
            "  chunk: '%s...' | source: %s | distance: %.4f | relevance: %.4f",
            doc.page_content[:60],
            doc.metadata.get("source"),
            distance,
            relevance,
        )

    # Sort by relevance descending (best match first)
    results.sort(key=lambda x: x["relevance"], reverse=True)

    return results


def format_context(results: list[dict]) -> str:
    """
    Format retrieved chunks into a single context string for the prompt.

    Takes the list of result dicts from retrieve() and formats them
    into a clean string that chain.py injects into the {context}
    placeholder in RAG_PROMPT.

    Args:
        results: List of result dicts from retrieve()

    Returns:
        str: Formatted context string ready for prompt injection.
             Returns empty string if results list is empty.
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