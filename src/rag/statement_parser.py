"""
Extracts structured transaction data from M-Pesa statements.

Accepts two input methods:
  1. PDF file path  → pdfplumber extracts text → parser
  2. Pasted text    → raw text goes directly   → parser

Both methods produce the same output — a list of structured
transaction dicts ready for categoriser.py.

M-Pesa statement formats supported:
  - MySafaricom app statement (PDF download)
  - USSD/SMS forwarded text (pasted directly)
  - M-Pesa portal statement (PDF download)

What a parsed transaction looks like:
  {
      "receipt_no":  "RJK81ABCDE",
      "date":        "01/05/2026",
      "time":        "12:34",
      "details":     "Customer Transfer to JOHN KAMAU 0712345678",
      "recipient":   "JOHN KAMAU",
      "amount":      850.0,
      "trans_type":  "sent",     # sent | received | withdraw | payment | airtime
      "balance":     12450.0,
  }

Files that import from here:
  - app/routes.py  (POST /api/v1/parse-text and /upload endpoints)
  - src/rag/chain.py (analyse_statement() passes parsed data to categoriser)
"""

import logging
import re
from pathlib import Path
from typing import Optional

import pdfplumber

logger = logging.getLogger(__name__)


# Transaction types 

TRANSACTION_TYPES = {
    "sent":     ["customer transfer to", "send money", "transfer to"],
    "received": ["customer transfer from", "receive money", "transfer from"],
    "withdraw": ["withdraw cash", "atm withdrawal", "agent withdrawal"],
    "payment":  ["pay bill", "buy goods", "lipa na mpesa", "paybill"],
    "airtime":  ["airtime purchase", "airtime", "data bundle"],
    "charges":  ["transaction cost", "mpesa charges", "service charge"],
    "deposit":  ["deposit", "received from"],
}


#  PDF input 

def extract_text_from_statement_pdf(pdf_path: str | Path) -> str:
    """
    Extract raw text from an M-Pesa statement PDF.

    Args:
        pdf_path: Path to the M-Pesa statement PDF

    Returns:
        str: Raw extracted text ready for parse_statement_text()

    Raises:
        FileNotFoundError: if PDF does not exist
        ValueError: if PDF produces no extractable text
    """
    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        raise FileNotFoundError(f"Statement PDF not found: {pdf_path}")

    logger.info("Extracting text from statement PDF: %s", pdf_path.name)

    pages_text = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # Try table extraction first — M-Pesa statements are tabular
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    for row in table:
                        if row:
                            clean_row = " | ".join(
                                cell.strip() if cell else ""
                                for cell in row
                            )
                            if clean_row.strip():
                                pages_text.append(clean_row)
            else:
                # Fallback to raw text
                text = page.extract_text()
                if text:
                    pages_text.append(text)

    full_text = "\n".join(pages_text)

    if not full_text.strip():
        raise ValueError(
            f"No text could be extracted from '{pdf_path.name}'. "
            f"The file may be a scanned image PDF."
        )

    logger.info(
        "Extracted %d characters from %s", len(full_text), pdf_path.name
    )
    return full_text


#  Core parser

def parse_statement_text(raw_text: str) -> list[dict]:
    """
    Parse raw M-Pesa statement text into structured transaction dicts.

    Handles both PDF-extracted text and directly pasted statement text.
    Uses regex patterns to identify transaction rows regardless of
    minor formatting differences between M-Pesa statement versions.

    Args:
        raw_text: Raw text from PDF extraction or direct paste

    Returns:
        list[dict]: List of structured transaction dicts, each with:
                    - receipt_no  (str)   M-Pesa receipt number
                    - date        (str)   transaction date DD/MM/YYYY
                    - time        (str)   transaction time HH:MM
                    - details     (str)   full transaction description
                    - recipient   (str)   extracted recipient name
                    - amount      (float) transaction amount in KES
                    - trans_type  (str)   sent|received|withdraw|payment|airtime
                    - balance     (float) account balance after transaction
    """
    if not raw_text or not raw_text.strip():
        logger.warning("Empty text passed to parse_statement_text()")
        return []

    logger.info("Parsing M-Pesa statement text (%d chars)", len(raw_text))

    transactions = []
    lines = raw_text.split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        transaction = _parse_line(line)
        if transaction:
            transactions.append(transaction)

    # If line-by-line didn't work well, try block parsing
    if len(transactions) < 3:
        logger.info(
            "Line parser found %d transactions — trying block parser",
            len(transactions)
        )
        transactions = _parse_blocks(raw_text)

    logger.info(
        "Parsed %d transactions from statement", len(transactions)
    )

    return transactions


def _parse_line(line: str) -> Optional[dict]:
    """
    Try to parse a single line as an M-Pesa transaction.

    M-Pesa statement lines typically follow this pattern:
    RJK81ABCDE | 01/05/2026 | 12:34 | Customer Transfer to JOHN | -850.00 | 12,450.00

    Args:
        line: Single line of text from the statement

    Returns:
        dict: Parsed transaction or None if line is not a transaction row
    """
    # Pattern: receipt number (alphanumeric, 10 chars), date, amount
    receipt_pattern = re.compile(
        r"([A-Z0-9]{8,12})"          # receipt number
        r".*?"
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"  # date
        r".*?"
        r"(-?[\d,]+\.?\d*)"          # amount
    )

    match = receipt_pattern.search(line)
    if not match:
        return None

    receipt_no = match.group(1)
    date       = match.group(2)
    amount_str = match.group(3).replace(",", "")

    try:
        amount = float(amount_str)
    except ValueError:
        return None

    # Skip header rows
    if receipt_no.lower() in ("receipt", "rpt", "ref", "mpesa"):
        return None

    # Extract time if present
    time_match = re.search(r"\b(\d{1,2}:\d{2})\b", line)
    time = time_match.group(1) if time_match else None

    # Determine transaction type and recipient
    trans_type, recipient = _classify_transaction(line)

    # Extract balance (last number in line)
    numbers = re.findall(r"[\d,]+\.?\d*", line)
    balance = 0.0
    if len(numbers) >= 2:
        try:
            balance = float(numbers[-1].replace(",", ""))
        except ValueError:
            pass

    return {
        "receipt_no": receipt_no,
        "date":       date,
        "time":       time,
        "details":    line[:200],
        "recipient":  recipient,
        "amount":     abs(amount),
        "trans_type": trans_type,
        "balance":    balance,
    }


def _parse_blocks(raw_text: str) -> list[dict]:
    """
    Parse statement as multi-line transaction blocks.
    ...
    """
    transactions = []

    # Find receipt-number-like boundaries: 8-12 alnum chars followed
    # by whitespace, but ONLY where the token contains at least one
    # digit — distinguishes real receipt numbers (e.g. "RJK81ABCDE")
    # from all-caps merchant/recipient names (e.g. "SUPERMARKET",
    # "QUICKMART") that would otherwise be misidentified as a new
    # transaction boundary and split mid-transaction.
    candidate_pattern = re.compile(r"(?=([A-Z0-9]{8,12})\s)")
    boundaries = [
        m.start() for m in candidate_pattern.finditer(raw_text)
        if any(c.isdigit() for c in m.group(1))
    ]

    if not boundaries:
        return transactions

    boundaries.append(len(raw_text))  # end of text as final boundary

    for start, end in zip(boundaries, boundaries[1:]):
        block = raw_text[start:end].strip()
        if not block or len(block) < 20:
            continue

        date_match = re.search(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", block)
        if not date_match:
            continue

        date = date_match.group(1)

        time_match = re.search(r"\b(\d{1,2}:\d{2})\b", block)
        time = time_match.group(1) if time_match else None

        amounts = re.findall(r"-?[\d,]+\.\d{2}", block)
        if not amounts:
            continue

        try:
            amount  = abs(float(amounts[0].replace(",", "")))
            balance = float(amounts[-1].replace(",", "")) if len(amounts) > 1 else 0.0
        except ValueError:
            continue

        first_word = block.split()[0] if block.split() else ""
        receipt_no = first_word if re.match(r"[A-Z0-9]{8,12}", first_word) else "UNKNOWN"

        trans_type, recipient = _classify_transaction(block)

        transactions.append({
            "receipt_no": receipt_no,
            "date":       date,
            "time":       time,
            "details":    block[:200],
            "recipient":  recipient,
            "amount":     amount,
            "trans_type": trans_type,
            "balance":    balance,
        })

    return transactions


def _classify_transaction(text: str) -> tuple[str, str]:
    """
    Determine transaction type and extract recipient name from text.

    Args:
        text: Transaction line or block text

    Returns:
        tuple: (transaction_type, recipient_name)
    """
    text_lower = text.lower()

    # Determine transaction type
    trans_type = "other"
    for t_type, keywords in TRANSACTION_TYPES.items():
        if any(kw in text_lower for kw in keywords):
            trans_type = t_type
            break

    # Extract recipient name
    recipient = _extract_recipient(text, trans_type)

    return trans_type, recipient


def _extract_recipient(text: str, trans_type: str) -> str:
    """
    Extract the recipient or sender name from transaction text.

    Tries multiple patterns in order of specificity.

    Args:
        text: Transaction text
        trans_type: Type of transaction

    Returns:
        str: Extracted recipient name or "Unknown"
    """
    # Pattern 1: "to/from NAME" — most common
    to_from = re.search(
        r"(?:to|from)\s+([A-Z][A-Z\s]{2,30}?)(?:\s+\d{10}|\s*$|\s*\|)",
        text,
        re.IGNORECASE,
    )
    if to_from:
        return to_from.group(1).strip()

    # Pattern 2: Phone number
    phone = re.search(r"\b(0[17]\d{8})\b", text)
    if phone:
        return phone.group(1)

    # Pattern 3: Business name (words before "Ltd" or "Limited")
    business = re.search(
        r"([A-Z][A-Z\s]+(?:Ltd|Limited|Co|Company))",
        text,
        re.IGNORECASE,
    )
    if business:
        return business.group(1).strip()

    # Pattern 4: Paybill/Till reference
    paybill = re.search(r"(?:paybill|till|account)\s*(?:no\.?)?\s*(\d+)", text, re.IGNORECASE)
    if paybill:
        return f"Paybill {paybill.group(1)}"

    return "Unknown"


# Public API 

def parse_from_pdf(pdf_path: str | Path) -> list[dict]:
    """
    Parse M-Pesa statement from a PDF file.

    Full pipeline: PDF → text extraction → transaction parsing.

    Args:
        pdf_path: Path to M-Pesa statement PDF

    Returns:
        list[dict]: Structured transaction list
    """
    raw_text = extract_text_from_statement_pdf(pdf_path)
    return parse_statement_text(raw_text)


def parse_from_text(pasted_text: str) -> list[dict]:
    """
    Parse M-Pesa statement from directly pasted text.

    For users who copy-paste from MySafaricom app or SMS.

    Args:
        pasted_text: Raw text copied from M-Pesa statement

    Returns:
        list[dict]: Structured transaction list
    """
    if not pasted_text or not pasted_text.strip():
        raise ValueError(
            "Pasted text is empty. "
            "Please paste your M-Pesa statement text and try again."
        )

    logger.info(
        "Parsing pasted statement text (%d chars)", len(pasted_text)
    )
    return parse_statement_text(pasted_text)


def get_statement_summary(transactions: list[dict]) -> dict:
    """
    Generate a high-level summary of parsed transactions.

    Args:
        transactions: Parsed transaction list from parse_from_pdf()
                      or parse_from_text()

    Returns:
        dict: Summary statistics including totals and date range
    """
    if not transactions:
        return {"error": "No transactions found"}

    amounts = [t["amount"] for t in transactions]
    dates   = [t["date"] for t in transactions if t.get("date")]

    sent     = sum(t["amount"] for t in transactions if t["trans_type"] == "sent")
    received = sum(t["amount"] for t in transactions if t["trans_type"] == "received")
    payments = sum(t["amount"] for t in transactions if t["trans_type"] == "payment")
    withdraw = sum(t["amount"] for t in transactions if t["trans_type"] == "withdraw")

    return {
        "total_transactions": len(transactions),
        "total_sent":         round(sent, 2),
        "total_received":     round(received, 2),
        "total_payments":     round(payments, 2),
        "total_withdrawals":  round(withdraw, 2),
        "total_spent":        round(sent + payments + withdraw, 2),
        "largest_transaction": max(amounts) if amounts else 0,
        "smallest_transaction": min(amounts) if amounts else 0,
        "average_transaction": round(sum(amounts) / len(amounts), 2) if amounts else 0,
        "date_range": {
            "from": dates[0]  if dates else None,
            "to":   dates[-1] if dates else None,
        },
    }