"""
src/rag/pipeline.py
-------------------
Ingestion pipeline — runs once at setup to load all PDFs from
data/raw/, chunk them, embed them, and store them in ChromaDB.

Responsibilities:
  - Orchestrate the full ingestion flow end to end
  - Wire loader → splitter → vectorstore in sequence
  - Log progress at every step so you know exactly what is happening
  - Expose run_ingestion() for programmatic use
  - Run as a standalone script via: python -m src.rag.pipeline

When to run this:
  - Once before launching the app for the first time
  - Again whenever you add new PDFs to data/raw/
  - Again whenever you update existing PDFs

You do NOT need to run this when a user uploads a PDF at runtime —
that is handled separately by vectorstore.add_chunks() via app/routes.py

Flow:
  data/raw/ PDFs
    → loader.load_documents()        load + extract text from all PDFs
    → splitter.split_documents()     chunk text with overlap
    → vectorstore.build_vectorstore() embed chunks + persist to ChromaDB
    → done — app is ready to answer questions
"""

import logging
import time
from pathlib import Path

from src.rag import settings
from src.rag.loader import load_documents
from src.rag.splitter import split_documents
from src.rag.vectorstore import build_vectorstore

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


def run_ingestion(data_dir: str | Path | None = None) -> dict:
    """
    Run the full ingestion pipeline end to end.

    Loads all PDFs from data/raw/, splits them into chunks,
    embeds each chunk, and persists everything to ChromaDB at
    data/chroma_db/. After this runs successfully, the app is
    ready to answer questions.

    Args:
        data_dir: Path to folder containing PDFs.
                  Defaults to settings.paths.raw_data from config.yaml.

    Returns:
        dict: Ingestion summary with keys:
              - "documents_loaded"  (int)   number of PDFs successfully loaded
              - "chunks_created"    (int)   total chunks stored in ChromaDB
              - "duration_seconds"  (float) total time taken
              - "sources"           (list)  list of ingested filenames

    Raises:
        FileNotFoundError: if data/raw/ does not exist
        RuntimeError: if no supported PDFs are found in data/raw/
    """
    start_time = time.time()

    logger.info("=" * 60)
    logger.info("M-PESA ADVISOR — INGESTION PIPELINE STARTING")
    logger.info("=" * 60)

    #  Step 1: Load PDFs 
    logger.info("STEP 1/3 — Loading PDFs from '%s'", settings.paths.raw_data)

    documents = load_documents(data_dir)
    sources   = [doc["source"] for doc in documents]

    logger.info(
        "STEP 1/3 COMPLETE — %d document(s) loaded: %s",
        len(documents),
        sources,
    )

    # Step 2: Split into chunks
    logger.info(
        "STEP 2/3 — Splitting documents into chunks "
        "(chunk_size: %d | overlap: %d)",
        settings.splitter.chunk_size,
        settings.splitter.chunk_overlap,
    )

    chunks = split_documents(documents)

    logger.info(
        "STEP 2/3 COMPLETE — %d total chunks created from %d document(s)",
        len(chunks),
        len(documents),
    )

    # Step 3: Embed and store in ChromaDB 
    logger.info(
        "STEP 3/3 — Embedding chunks and storing in ChromaDB "
        "(model: %s | collection: '%s')",
        settings.embeddings.model,
        settings.vectorstore.collection_name,
    )
    logger.info(
        "This step calls the OpenAI API — "
        "embedding %d chunks. Please wait...",
        len(chunks),
    )

    build_vectorstore(chunks)

    logger.info(
        "STEP 3/3 COMPLETE — %d chunks embedded and persisted to '%s'",
        len(chunks),
        settings.paths.chroma_db,
    )

    # Summary 
    duration = round(time.time() - start_time, 2)

    logger.info("=" * 60)
    logger.info("INGESTION PIPELINE COMPLETE")
    logger.info("  Documents loaded : %d", len(documents))
    logger.info("  Chunks stored    : %d", len(chunks))
    logger.info("  Duration         : %ss", duration)
    logger.info("  ChromaDB path    : %s", settings.paths.chroma_db)
    logger.info("=" * 60)
    logger.info("The app is ready. Run:")
    logger.info("  uvicorn app.main:app --reload        (API)")
    logger.info("  streamlit run frontend/app.py        (UI)")
    logger.info("=" * 60)

    return {
        "documents_loaded": len(documents),
        "chunks_created":   len(chunks),
        "duration_seconds": duration,
        "sources":          sources,
    }


#  Run as standalone script 
# python -m src.rag.pipeline

if __name__ == "__main__":
    try:
        summary = run_ingestion()
        print("\nSummary:")
        for key, value in summary.items():
            print(f"  {key}: {value}")
    except FileNotFoundError as e:
        logger.error("Data directory error: %s", e)
        raise SystemExit(1)
    except RuntimeError as e:
        logger.error("Ingestion error: %s", e)
        raise SystemExit(1)
    except Exception as e:
        logger.error("Unexpected error during ingestion: %s", e)
        raise SystemExit(1)