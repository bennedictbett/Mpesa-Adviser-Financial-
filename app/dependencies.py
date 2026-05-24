"""
Shared FastAPI dependencies injected into route handlers.

Responsibilities:
  - Initialise shared resources once at app startup (not per request)
  - Expose them via FastAPI's dependency injection system
  - Validate the app is ready to serve requests before any endpoint runs

What is FastAPI dependency injection?
  Instead of initialising the vectorstore or LLM inside every route
  function, you define them here and FastAPI injects them automatically.
  This means:
    - Resources are created once, reused on every request
    - Routes stay clean — no setup code inside route handlers
    - Easy to swap implementations for testing

Dependencies defined here:
  - get_rag_chain   → verifies vectorstore is loaded, ready for chain.py
  - get_settings    → exposes the settings object to routes that need it
  - verify_api_keys → checks API keys are set before serving any request

All route handlers in app/routes.py use these via FastAPI's Depends().
"""

import logging
from functools import lru_cache

from fastapi import Depends, HTTPException, status

from src.rag import settings
from src.rag.vectorstore import load_vectorstore

logger = logging.getLogger(__name__)


# Settings dependency 

@lru_cache(maxsize=1)
def get_settings():
    """
    Return the global settings object.

    Cached so it is only read once regardless of how many
    requests come in simultaneously.

    Usage in a route:
        @router.get("/info")
        def info(cfg = Depends(get_settings)):
            return {"version": cfg.app.version}
    """
    return settings


# API key validation 

def verify_api_keys():
    """
    Verify both API keys are set before serving any request.

    Called as a dependency on every route — if either key is
    missing the app returns a 503 immediately with a clear message
    rather than failing silently mid-request when Claude is called.

    Raises:
        HTTPException 503: if OPENAI_API_KEY or ANTHROPIC_API_KEY
                           are missing or still set to placeholder values
    """
    openai_key    = settings.secrets.OPENAI_API_KEY
    anthropic_key = settings.secrets.ANTHROPIC_API_KEY

    if not openai_key or openai_key == "your-openai-api-key-here":
        logger.error("OPENAI_API_KEY is not set")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "OPENAI_API_KEY is not configured. "
                "Add it to your .env file and restart the app."
            ),
        )

    if not anthropic_key or anthropic_key == "your-anthropic-api-key-here":
        logger.error("ANTHROPIC_API_KEY is not set")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "ANTHROPIC_API_KEY is not configured. "
                "Add it to your .env file and restart the app."
            ),
        )


# Vectorstore dependency 

def get_vectorstore():
    """
    Load and return the ChromaDB vectorstore.

    Verifies ChromaDB has been built before serving any
    chat or analyse request. If the ingestion pipeline has
    not been run yet, returns a clear 503 error instead of
    a confusing internal error deep inside retriever.py.

    Raises:
        HTTPException 503: if ChromaDB has not been built yet
                           (run: python -m src.rag.pipeline)

    Usage in a route:
        @router.post("/chat")
        def chat(request: ChatRequest, vs = Depends(get_vectorstore)):
            ...
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


# Combined readiness check 

def check_app_ready(
    _keys = Depends(verify_api_keys),
    _vs   = Depends(get_vectorstore),
):
    """
    Combined dependency that checks the app is fully ready.

    Runs both verify_api_keys() and get_vectorstore() together.
    Use this on any route that needs both — /chat and /analyse.

    If either check fails the request is rejected before your
    route handler runs.

    Usage in a route:
        @router.post("/chat")
        def chat(
            request: ChatRequest,
            _: None = Depends(check_app_ready),
        ):
            ...
    """
    pass