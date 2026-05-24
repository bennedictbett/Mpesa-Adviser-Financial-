"""
Initialises and returns the embeddings client used by vectorstore.py.

Currently configured to use HuggingFace sentence-transformers —
completely free, no API key required, runs locally on your machine.

To switch back to OpenAI embeddings later:
  1. Change config.yaml:  embeddings.provider: "openai"
  2. Change config.yaml:  embeddings.model: "text-embedding-3-small"
  3. Add OPENAI_API_KEY to .env
  Nothing else changes.

What are embeddings?
  Text embeddings convert a piece of text into a list of numbers (a vector)
  that captures its meaning. Similar texts produce similar vectors.
  ChromaDB uses these vectors to find the most relevant document chunks
  when a user asks a question.

Only one file imports from here: vectorstore.py
"""

import logging
from functools import lru_cache

from langchain_huggingface import HuggingFaceEmbeddings

from src.rag import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_embeddings() -> HuggingFaceEmbeddings:
    """
    Initialise and return the HuggingFace embeddings client.

    Uses @lru_cache so the model is loaded only once and reused
    on every subsequent call — loading sentence-transformers takes
    a few seconds the first time, you don't want it per request.

    Model: all-MiniLM-L6-v2
      - Completely free, no API key needed
      - Runs locally on your CPU
      - 384-dimensional vectors
      - Fast and accurate for semantic search
      - Downloaded automatically on first run (~90MB)

    Returns:
        HuggingFaceEmbeddings: LangChain-wrapped embeddings client
                               ready for vectorstore.py

    Raises:
        Exception: if the model fails to download or initialise
    """
    logger.info(
        "Initialising embeddings | provider: %s | model: %s",
        settings.embeddings.provider,
        settings.embeddings.model,
    )
    logger.info(
        "First run will download the model (~90MB) — "
        "subsequent runs load from cache instantly"
    )

    embeddings = HuggingFaceEmbeddings(
        model_name=settings.embeddings.model,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

    logger.info("Embeddings client initialised successfully")
    return embeddings