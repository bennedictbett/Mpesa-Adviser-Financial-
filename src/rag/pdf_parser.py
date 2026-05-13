"""
Extracts raw text from PDF files using pdfplumber.

Responsibilities:
  - Open a PDF file from disk
  - Extract text page by page
  - Extract tables and convert them to readable text
  - Skip blank or near-blank pages
  - Return clean raw text ready for splitter.py

Why pdfplumber over pypdf?
  - pdfplumber handles tables reliably — critical for M-Pesa tariff PDFs
    which are full of fee tables (send, withdraw, pay bill amounts)
  - pypdf is faster but loses table structure — you'd get garbled numbers
  - For Kenyan government/telco PDFs, pdfplumber is significantly more accurate

Only one file imports from here: loader.py
"""

import logging
from pathlib import Path

import pdfplumber

from src.rag import settings

logger = logging.getLogger(__name__)


def extract_text_from_pdf(pdf_path: str | Path) -> str:
    """
    Extract all text from a single PDF file.

    Processes the PDF page by page:
      1. Extracts regular text from each page
      2. Extracts any tables and converts them to readable text
      3. Skips pages with less than min_page_chars characters (blank/cover pages)
      4. Joins all page content into one clean string

    Args:
        pdf_path: Path to the PDF file (str or Path object)

    Returns:
        str: Full extracted text from the PDF, ready for splitter.py
             Returns empty string if the PDF has no extractable text.

    Raises:
        FileNotFoundError: if the PDF file does not exist at the given path
        Exception: if pdfplumber fails to open or read the PDF
    """
    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"PDF not found: {pdf_path}. "
            f"Make sure your PDFs are placed in the '{settings.paths.raw_data}' folder."
        )

    logger.info(f"Parsing PDF: {pdf_path.name}")

    pages_text = []
    min_chars  = settings.pdf.min_page_chars

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        logger.info(f"{pdf_path.name} has {total_pages} pages")

        for page_num, page in enumerate(pdf.pages, start=1):

            page_content = []

            # Extract regular text
            text = page.extract_text()
            if text:
                page_content.append(text.strip())

            # Extract tables 
            # pdfplumber returns tables as list of rows (list of lists)
            # We convert each row to a tab-separated string so the
            # content stays readable after chunking
            if settings.pdf.extract_tables:
                tables = page.extract_tables()
                for table in tables:
                    if not table:
                        continue
                    table_lines = []
                    for row in table:
                        # filter None cells, join with tab
                        clean_row = "\t".join(
                            cell.strip() if cell else "" for cell in row
                        )
                        if clean_row.strip():
                            table_lines.append(clean_row)
                    if table_lines:
                        page_content.append("\n".join(table_lines))

            #  Combine page content 
            combined = "\n".join(page_content).strip()

            # Skip near-blank pages 
            if len(combined) < min_chars:
                logger.debug(
                    f"Skipping page {page_num}/{total_pages} "
                    f"— only {len(combined)} chars (min: {min_chars})"
                )
                continue

            pages_text.append(combined)
            logger.debug(
                f"Page {page_num}/{total_pages} — extracted {len(combined)} chars"
            )

    full_text = "\n\n".join(pages_text)

    if not full_text.strip():
        logger.warning(
            f"{pdf_path.name} produced no extractable text. "
            f"It may be a scanned image PDF — pdfplumber cannot read scanned PDFs."
        )
        return ""

    logger.info(
        f"Finished parsing {pdf_path.name} — "
        f"{len(pages_text)} pages extracted, "
        f"{len(full_text)} total characters"
    )

    return full_text


def is_supported_file(file_path: str | Path) -> bool:
    """
    Check if a file is a supported type for ingestion.

    Uses the supported_extensions list from config.yaml.
    Currently supports .pdf only — extend config to add more types later.

    Args:
        file_path: Path to the file to check

    Returns:
        bool: True if the file extension is in supported_extensions
    """
    return Path(file_path).suffix.lower() in settings.pdf.supported_extensions