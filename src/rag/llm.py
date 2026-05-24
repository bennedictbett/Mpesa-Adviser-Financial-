"""
Initialises and returns the LLM client used by chain.py.

Currently configured to use Groq — completely free, no credit card
required. Sign up at console.groq.com with just an email address.

To switch back to Claude (Anthropic) later:
  1. Change config.yaml: llm.provider: "anthropic"
  2. Change config.yaml: llm.model: "claude-sonnet-4-20250514"
  3. Add ANTHROPIC_API_KEY to .env
  Nothing else changes.

Only one file imports from here: chain.py
"""

import logging
from functools import lru_cache

from langchain_groq import ChatGroq

from src.rag import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_llm() -> ChatGroq:
    """
    Initialise and return the Groq LLM client.

    Uses @lru_cache so the client is created only once
    and reused on every subsequent call — not rebuilt on every request.

    Why Groq?
      - Completely free tier — no credit card needed
      - Sign up at console.groq.com with just an email
      - Runs Llama 3.1 70B — high quality, fast responses
      - LangChain wrapper means zero code changes when switching to Claude

    Returns:
        ChatGroq: LangChain-wrapped Groq client ready for chain.py

    Raises:
        ValueError: if GROQ_API_KEY is missing or not set in .env
        Exception:  if the LangChain/Groq client fails to initialise
    """
    api_key = settings.secrets.GROQ_API_KEY

    if not api_key or api_key == "your-groq-api-key-here":
        raise ValueError(
            "GROQ_API_KEY is missing or not set in your .env file. "
            "Get your free key at https://console.groq.com — email only, no card needed."
        )

    logger.info(
        "Initialising LLM | provider: %s | model: %s",
        settings.llm.provider,
        settings.llm.model,
    )

    llm = ChatGroq(
        api_key=api_key,
        model=settings.llm.model,
        max_tokens=settings.llm.max_tokens,
        temperature=settings.llm.temperature,
    )

    logger.info("LLM client initialised successfully")
    return llm