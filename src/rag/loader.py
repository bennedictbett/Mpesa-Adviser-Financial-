"""
Finds all supported PDF files in data/raw/ and returns their
extracted text using pdf_parser.py.

Responsibilities:
  - Scan the data/raw/ folder for supported files
  - Pass each file to pdf_parser.py for text extraction
  - Return a list of documents (text + metadata) ready for splitter.py
  - Handle a single uploaded file (for the /upload API endpoint)

What is a document here?
  A document is a dict with two keys:
    {
        "text":   str,        # raw extracted text from the PDF
        "source": str,        # filename e.g. "mpesa_tariff_2024.pdf"
    }
  splitter.py receives this list and chunks each document's text.

Files that import from here:
  - splitter.py  (during ingestion pipeline)
  - app/routes.py (for single file upload via /upload endpoint)
"""

import logging
from pathlib import Path

from src.rag import settings
from src.rag.pdf_parser import extract_text_from_pdf, is_supported_file

logger = logging.getLogger(__name__)


def load_documents(data_dir: str | Path | None = None) -> list[dict]:
    """
    Scan data/raw/ and load all supported PDF files.

    Iterates over every file in the raw data directory, checks if it
    is a supported file type, extracts its text via pdf_parser.py,
    and returns a list of document dicts ready for splitter.py.

    Args:
        data_dir: Path to folder containing PDFs.
                  Defaults to settings.paths.raw_data from config.yaml.

    Returns:
        list[dict]: List of documents, each with keys:
                    - "text"   (str) raw extracted text
                    - "source" (str) filename only e.g. "mpesa_tariff.pdf"

    Raises:
        FileNotFoundError: if data_dir does not exist
        RuntimeError: if no supported files are found in data_dir
    """
    raw_dir = Path(data_dir or settings.paths.raw_data)

    # Guard: folder must exist 
    if not raw_dir.exists():
        raise FileNotFoundError(
            f"Data directory not found: {raw_dir}. "
            f"Create the folder and place your PDFs inside it."
        )

    # Discover all supported files 
    all_files = list(raw_dir.iterdir())
    supported_files = [f for f in all_files if is_supported_file(f)]

    logger.info(
        f"Scanning '{raw_dir}' — "
        f"found {len(all_files)} files, "
        f"{len(supported_files)} supported"
    )

    # Guard: at least one file must exist
    if not supported_files:
        raise RuntimeError(
            f"No supported files found in '{raw_dir}'. "
            f"Supported types: {settings.pdf.supported_extensions}. "
            f"Place your M-Pesa PDF documents in the '{raw_dir}' folder and try again."
        )

    # Extract text from each file 
    documents = []

    for file_path in supported_files:
        logger.info(f"Loading: {file_path.name}")

        text = extract_text_from_pdf(file_path)

        # skip files that produced no text (scanned/image PDFs)
        if not text.strip():
            logger.warning(
                f"Skipping {file_path.name} — no extractable text. "
                f"File may be a scanned image PDF."
            )
            continue

        documents.append({
            "text":   text,
            "source": file_path.name,
        })

        logger.info(
            f"Loaded '{file_path.name}' — "
            f"{len(text):,} characters extracted"
        )

    logger.info(
        f"Loading complete — "
        f"{len(documents)}/{len(supported_files)} files loaded successfully"
    )

    return documents


def load_single_document(file_path: str | Path) -> dict:
    """
    Load and extract text from a single PDF file.

    Used by app/routes.py when a user uploads a PDF via the
    /upload endpoint — we don't re-scan the whole data/raw/ folder,
    we just process the one uploaded file.

    Args:
        file_path: Full path to the uploaded PDF file

    Returns:
        dict: Single document with keys:
              - "text"   (str) raw extracted text
              - "source" (str) filename only

    Raises:
        ValueError: if the file type is not supported
        FileNotFoundError: if the file does not exist
    """
    file_path = Path(file_path)

    # must be a supported file type 
    if not is_supported_file(file_path):
        raise ValueError(
            f"Unsupported file type: '{file_path.suffix}'. "
            f"Supported types: {settings.pdf.supported_extensions}."
        )

    logger.info(f"Loading single document: {file_path.name}")

    text = extract_text_from_pdf(file_path)

    if not text.strip():
        raise ValueError(
            f"No text could be extracted from '{file_path.name}'. "
            f"The file may be a scanned image PDF."
        )

    logger.info(
        f"Single document loaded — "
        f"'{file_path.name}' | {len(text):,} characters"
    )

    return {
        "text":   text,
        "source": file_path.name,
    }