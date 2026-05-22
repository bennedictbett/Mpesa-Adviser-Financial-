"""
src/rag/vectorstore.py
----------------------
Manages the ChromaDB vector store — stores chunks with their embeddings
and loads the store back for similarity search.

Responsibilities:
  - Receive chunks from splitter.py
  - Embed each chunk using embeddings.py
  - Store chunks + embeddings in ChromaDB (persisted to data/chroma_db/)
  - Load the existing ChromaDB store for retriever.py to search
  - Handle duplicate chunks gracefully (upsert not insert)

What happens here in plain English:
  1. You have 200 chunks from your M-Pesa PDFs
  2. Each chunk's text gets converted to 1,536 numbers (embedding)
  3. Those numbers + the original text + the source filename
     are stored together in ChromaDB on disk
  4. Later, retriever.py opens the same ChromaDB, converts a user's
     question to numbers, and finds the chunks whose numbers are
     closest — those are the most relevant chunks

Files that import from here:
  - retriever.py  (loads the store for search)
  - pipeline.py   (calls build_vectorstore during ingestion)
  - app/routes.py (calls add_chunks after a user uploads a PDF)
"""

import logging
from pathlib import Path
from functools import lru_cache

from langchain_chroma import Chroma
from langchain_core.documents import Document

from src.rag import settings
from src.rag.embeddings import get_embeddings

logger = logging.getLogger(__name__)


# ── Build: embed chunks and store in ChromaDB ─────────────────

def build_vectorstore(chunks: list[dict]) -> Chroma:
    """
    Embed all chunks and store them in ChromaDB.

    Takes the list of chunks from splitter.py, converts each chunk's
    text to an embedding vector, and persists everything to disk at
    data/chroma_db/.

    Uses upsert (not insert) — if you run ingestion twice with the
    same chunk_ids, ChromaDB updates rather than duplicates.

    Args:
        chunks: List of chunk dicts from splitter.py, each with:
                - "text"     (str) chunk text
                - "source"   (str) original filename
                - "chunk_id" (str) unique identifier

    Returns:
        Chroma: The loaded vectorstore instance ready for similarity search

    Raises:
        ValueError: if chunks list is empty
    """
    if not chunks:
        raise ValueError(
            "No chunks provided to build_vectorstore(). "
            "Make sure split_documents() returned results before calling this."
        )

    persist_dir = str(settings.paths.chroma_db)

    logger.info(
        f"Building vectorstore | "
        f"{len(chunks)} chunks | "
        f"collection: '{settings.vectorstore.collection_name}' | "
        f"persisting to: '{persist_dir}'"
    )

    # ── Convert chunk dicts → LangChain Document objects ─────
    # LangChain's Chroma wrapper expects Document objects, not plain dicts
    # Document has two fields: page_content (the text) and metadata (dict)
    documents = [
        Document(
            page_content=chunk["text"],
            metadata={
                "source":   chunk["source"],
                "chunk_id": chunk["chunk_id"],
            }
        )
        for chunk in chunks
    ]

    ids = [chunk["chunk_id"] for chunk in chunks]

    # ── Build and persist ChromaDB ────────────────────────────
    vectorstore = Chroma.from_documents(
        documents=documents,
        embedding=get_embeddings(),
        collection_name=settings.vectorstore.collection_name,
        persist_directory=persist_dir,
        ids=ids,
    )

    logger.info(
        f"Vectorstore built successfully — "
        f"{len(chunks)} chunks stored in '{persist_dir}'"
    )

    return vectorstore


# ── Load: open existing ChromaDB for search ───────────────────

@lru_cache(maxsize=1)
def load_vectorstore() -> Chroma:
    """
    Load the existing ChromaDB vectorstore from disk.

    Opens the persisted ChromaDB at data/chroma_db/ and returns
    it ready for similarity search in retriever.py.

    Uses @lru_cache so the store is opened once and reused on every
    request — not reopened on every user question.

    Returns:
        Chroma: The loaded vectorstore ready for similarity search

    Raises:
        RuntimeError: if ChromaDB has not been built yet (run ingestion first)
    """
    persist_dir = Path(settings.paths.chroma_db)

    if not persist_dir.exists() or not any(persist_dir.iterdir()):
        raise RuntimeError(
            f"ChromaDB not found at '{persist_dir}'. "
            f"Run the ingestion pipeline first: python -m src.rag.pipeline"
        )

    logger.info(
        f"Loading vectorstore from '{persist_dir}' | "
        f"collection: '{settings.vectorstore.collection_name}'"
    )

    vectorstore = Chroma(
        collection_name=settings.vectorstore.collection_name,
        embedding_function=get_embeddings(),
        persist_directory=str(persist_dir),
    )

    logger.info("Vectorstore loaded successfully")
    return vectorstore


# ── Add: insert new chunks from uploaded PDF ──────────────────

def add_chunks(chunks: list[dict]) -> int:
    """
    Add new chunks to the existing ChromaDB vectorstore.

    Called by app/routes.py after a user uploads a new PDF at runtime.
    Adds the new chunks to the existing store without rebuilding
    everything from scratch.

    Args:
        chunks: List of chunk dicts from splitter.split_single_document()

    Returns:
        int: Number of chunks successfully added

    Raises:
        RuntimeError: if the vectorstore has not been built yet
    """
    if not chunks:
        logger.warning("add_chunks() called with empty chunks list — nothing added")
        return 0

    vectorstore = load_vectorstore()

    documents = [
        Document(
            page_content=chunk["text"],
            metadata={
                "source":   chunk["source"],
                "chunk_id": chunk["chunk_id"],
            }
        )
        for chunk in chunks
    ]

    ids = [chunk["chunk_id"] for chunk in chunks]

    vectorstore.add_documents(documents=documents, ids=ids)

    # clear the lru_cache so the next load_vectorstore() call
    # returns a fresh instance with the new chunks included
    load_vectorstore.cache_clear()

    logger.info(
        f"Added {len(chunks)} new chunks to vectorstore | "
        f"source: '{chunks[0]['source']}'"
    )

    return len(chunks)