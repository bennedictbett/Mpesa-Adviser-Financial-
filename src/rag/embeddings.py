"""
Initialises and returns the OpenAI embeddings client used by vectorstore.py.

Responsibilities:
  - Read embedding settings from config via settings object
  - Initialise the OpenAIEmbeddings client (LangChain wrapper)
  - Expose a single get_embeddings() function that vectorstore.py calls

What are embeddings?
  Text embeddings convert a piece of text into a list of numbers (a vector)
  that captures its meaning. Similar texts produce similar vectors.
  ChromaDB uses these vectors to find the most relevant document chunks
  when a user asks a question.

Only one file imports from here: vectorstore.py
"""

import logging
from functools import lru_cache

from langchain_openai import OpenAIEmbeddings

from src.rag import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_embeddings() -> OpenAIEmbeddings:
    """
    Initialise and return the OpenAI embeddings client.

    Uses @lru_cache so the client is created only once
    and reused on every subsequent call — not rebuilt on every request.

    Why OpenAI for embeddings and Anthropic for generation?
      - Claude (Anthropic) does not provide an embeddings API.
      - OpenAI's text-embedding-3-small is fast, cheap (~$0.02 per million
        tokens), and high quality — industry standard for RAG pipelines.
      - Embedding your entire document collection costs under KES 10 total.

    Returns:
        OpenAIEmbeddings: LangChain-wrapped embeddings client ready
                          for vectorstore.py

    Raises:
        ValueError: if OPENAI_API_KEY is missing or not set in .env
        Exception:  if the LangChain/OpenAI client fails to initialise
    """
    api_key = settings.secrets.OPENAI_API_KEY

    if not api_key or api_key == "":
        raise ValueError(
            "OPENAI_API_KEY is missing or not set in your .env file. "
            "Get your key at https://platform.openai.com/api-keys"
        )

    logger.info(
        f"Initialising embeddings | provider: {settings.embeddings.provider} "
        f"| model: {settings.embeddings.model} "
        f"| dimensions: {settings.embeddings.dimensions}"
    )

    embeddings = OpenAIEmbeddings(
        api_key=api_key,
        model=settings.embeddings.model,
        dimensions=settings.embeddings.dimensions,
    )

    logger.info("Embeddings client initialised successfully")
    return embeddings