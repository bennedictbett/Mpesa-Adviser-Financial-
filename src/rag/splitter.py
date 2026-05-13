"""
Splits raw extracted text from loader.py into smaller chunks
ready for embedding and storage in ChromaDB.

Responsibilities:
  - Receive a list of documents from loader.py
  - Split each document's text into overlapping chunks
  - Preserve source metadata on every chunk
  - Return a list of chunks ready for embeddings.py and vectorstore.py

Why do we chunk at all?
  LLMs have a context window limit — you cannot pass an entire 50-page
  PDF into Claude at once. Chunking breaks documents into smaller pieces
  so we only retrieve and pass the most relevant sections per question.

Why overlap between chunks?
  If a sentence about an M-Pesa fee sits at the boundary between two
  chunks, without overlap one chunk would have the first half and the
  next chunk the second half — neither chunk has the full sentence.
  Overlap of 150 characters ensures boundary content appears in both
  neighbouring chunks so nothing is lost.

What is a chunk here?
  A chunk is a dict with three keys:
    {
        "text":     str,  # the chunk text (max chunk_size characters)
        "source":   str,  # original filename e.g. "mpesa_tariff.pdf"
        "chunk_id": str,  # unique ID e.g. "mpesa_tariff.pdf_chunk_3"
    }

Only one file imports from here: vectorstore.py
"""

import logging
from langchain.text_splitter import RecursiveCharacterTextSplitter
from src.rag import settings

logger = logging.getLogger(__name__)


def split_documents(documents: list[dict]) -> list[dict]:
    """
    Split a list of documents into overlapping text chunks.

    Takes the raw documents returned by loader.py and splits each
    document's text using LangChain's RecursiveCharacterTextSplitter.

    The splitter tries to split on paragraph breaks first (\n\n),
    then line breaks (\n), then sentences (.), then spaces — so it
    always tries to cut at the most natural boundary before cutting
    mid-sentence.

    All split settings (chunk_size, chunk_overlap, separators) come
    from config/config.yaml via the settings object — never hardcoded.

    Args:
        documents: List of document dicts from loader.py, each with:
                   - "text"   (str) raw extracted text
                   - "source" (str) filename

    Returns:
        list[dict]: List of chunk dicts, each with:
                    - "text"     (str) chunk text
                    - "source"   (str) original filename
                    - "chunk_id" (str) unique identifier

    Raises:
        ValueError: if documents list is empty
    """
    if not documents:
        raise ValueError(
            "No documents provided to split. "
            "Make sure load_documents() returned results before calling split_documents()."
        )

    #  Initialise splitter from config 
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.splitter.chunk_size,
        chunk_overlap=settings.splitter.chunk_overlap,
        separators=settings.splitter.separators,
        length_function=len,
    )

    logger.info(
        f"Splitting {len(documents)} document(s) | "
        f"chunk_size: {settings.splitter.chunk_size} | "
        f"chunk_overlap: {settings.splitter.chunk_overlap}"
    )

    all_chunks = []

    for document in documents:
        source = document["source"]
        text   = document["text"]

        #  Split this document's text
        splits = splitter.split_text(text)

        # Build chunk dicts with metadata 
        for i, chunk_text in enumerate(splits):
            chunk = {
                "text":     chunk_text,
                "source":   source,
                "chunk_id": f"{source}_chunk_{i}",
            }
            all_chunks.append(chunk)

        logger.info(
            f"'{source}' → {len(splits)} chunks "
            f"(avg {sum(len(s) for s in splits) // max(len(splits), 1)} chars/chunk)"
        )

    logger.info(
        f"Splitting complete — "
        f"{len(documents)} document(s) → {len(all_chunks)} total chunks"
    )

    return all_chunks


def split_single_document(document: dict) -> list[dict]:
    """
    Split a single document into chunks.

    Used by app/routes.py after a user uploads a PDF via the
    /upload endpoint — mirrors load_single_document() in loader.py.

    Args:
        document: Single document dict from loader.load_single_document()
                  with keys "text" and "source"

    Returns:
        list[dict]: List of chunk dicts with "text", "source", "chunk_id"
    """
    logger.info(f"Splitting single document: {document['source']}")
    return split_documents([document])