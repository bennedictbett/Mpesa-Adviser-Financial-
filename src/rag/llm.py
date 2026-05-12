"""
Initialises and returns the Claude LLM client used by chain.py.

Responsibilities:
  - Read LLM settings from config via settings object
  - Initialise the ChatAnthropic client (LangChain wrapper around Claude)
  - Expose a single get_llm() function that chain.py calls

Only one file imports from here: chain.py
"""

import logging
from functools import lru_cache

from langchain_anthropic import ChatAnthropic

from src.rag import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_llm() -> ChatAnthropic:
    """
    Initialise and return the Claude LLM client.

    Uses @lru_cache so the client is created only once
    and reused on every subsequent call — not rebuilt on every request.

    Returns:
        ChatAnthropic: LangChain-wrapped Claude client ready for chain.py

    Raises:
        ValueError: if ANTHROPIC_API_KEY is missing from .env
        Exception:  if the LangChain/Anthropic client fails to initialise
    """
    api_key = settings.secrets.ANTHROPIC_API_KEY

    if not api_key or api_key == "":
        raise ValueError(
            "ANTHROPIC_API_KEY is missing or not set in your .env file. "
            "Please add it to use the LLM features."
        )

    logger.info(
        f"Initialising LLM | provider: {settings.llm.provider} "
        f"| model: {settings.llm.model}"
    )

    llm = ChatAnthropic(
        api_key=api_key,
        model=settings.llm.model,
        max_tokens=settings.llm.max_tokens,
        temperature=settings.llm.temperature,
    )

    logger.info("LLM client initialised successfully")
    return llm