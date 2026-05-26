"""
app/dependencies.py
-------------------
Shared FastAPI dependencies injected into route handlers.
"""

import logging
from functools import lru_cache

from fastapi import Depends, HTTPException, status

from src.rag import settings
from src.rag.vectorstore import load_vectorstore

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_settings():
    return settings


def verify_api_keys():
    """
    Verify GROQ_API_KEY is set before serving any request.
    """
    groq_key = settings.secrets.GROQ_API_KEY

    if not groq_key or groq_key == "your-groq-api-key-here":
        logger.error("GROQ_API_KEY is not set")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "GROQ_API_KEY is not configured. "
                "Get your free key at https://console.groq.com "
                "and add it to your .env file."
            ),
        )


def get_vectorstore():
    """
    Load and return the ChromaDB vectorstore.
    """
    try:
        vectorstore = load_vectorstore()
        return vectorstore
    except RuntimeError as e:
        logger.error("Vectorstore not ready: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Knowledge base is not ready. "
                "Run the ingestion pipeline first: "
                "python -m src.rag.pipeline"
            ),
        )


def check_app_ready(
    _keys = Depends(verify_api_keys),
    _vs   = Depends(get_vectorstore),
):
    """
    Combined dependency — checks API key and vectorstore are ready.
    """
    pass