"""
Assigns a spending category (Food, Transport, Airtime, ...) to each
parsed transaction from statement_parser.py.

Strategy — hybrid, cheapest-first:
  1. trans_type shortcut  — some M-Pesa mechanisms map to a category
                             unambiguously (airtime, withdrawal, charges).
                             No text matching needed, always correct.
  2. Keyword rules         — match recipient/details against known
                             merchant/service keywords. Free, instant,
                             deterministic.
  3. LLM fallback          — only for what's left unmatched. Result is
                             cached by recipient text so the same
                             merchant is never re-classified twice.

Input:  list[dict] as produced by statement_parser.parse_statement_text()
Output: same dicts, each with a new "category" key added.

Files that import from here:
  - backend/agents/tools.py     (get_category_breakdown, etc.)
  - backend/services/analytics_service.py
"""

import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


# trans_type → category shortcuts
# These M-Pesa mechanisms are unambiguous — no need to inspect text.
TRANS_TYPE_CATEGORY_MAP = {
    "airtime":  "Airtime",
    "withdraw": "Cash Withdrawal",
    "charges":  "M-Pesa Charges",
}

# Keyword rules — checked against recipient + details (lowercased).
# Extend this list as you see more "Other" transactions in real statements.
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "Food": [
        "naivas", "quickmart", "carrefour", "java", "kfc",
        "chicken inn", "restaurant", "hotel", "eatery", "chandarana",
        "cleanshelf", "supermarket", "butchery", "bakery",
    ],
    "Transport": [
        "uber", "bolt", "little cab", "matatu", "sacco",
        "shell", "total energies", "rubis", "petrol", "fuel",
    ],
    "Utilities": [
        "kenya power", "kplc", "zuku", "safaricom home", "dstv",
        "gotv", "startimes", "nairobi water", "faiba",
    ],
    "Banking": [
        "equity", "kcb", "co-operative bank", "ncba", "absa",
        "fuliza", "mshwari", "kcb-mpesa", "loan repayment",
    ],
    "Business": [
        "ltd", "limited", "enterprises", "traders", "supplies",
    ],
}

# In-memory cache for LLM-fallback results, keyed by normalised
# recipient/details text. Avoids re-classifying the same merchant
# twice within a run.
# TODO (Phase 1 / database/): persist this to the transactions DB
# once it exists, so it survives across runs — not just per-process.
_llm_category_cache: dict[str, str] = {}

from datetime import datetime


def normalise_transaction_date(txn: dict) -> dict:
    """
    Parses the raw "DD/MM/YYYY" date string (and optional "HH:MM" time)
    from statement_parser.py into a real datetime object, stored under
    a new "parsed_date" key. Leaves the original "date"/"time" strings
    untouched, since routes/UI may still want to display them as-is.

    Falls back to None on unparseable dates rather than raising —
    a single malformed row shouldn't break analytics for the whole
    statement. Callers filtering by date should skip None values.
    """
    date_str = txn.get("date")
    time_str = txn.get("time") or "00:00"

    if not date_str:
        txn["parsed_date"] = None
        return txn

    for fmt in ("%d/%m/%Y %H:%M", "%d-%m-%Y %H:%M", "%d/%m/%y %H:%M"):
        try:
            txn["parsed_date"] = datetime.strptime(f"{date_str} {time_str}", fmt)
            return txn
        except ValueError:
            continue

    logger.warning("Could not parse date '%s' for transaction %s", date_str, txn.get("receipt_no"))
    txn["parsed_date"] = None
    return txn


def normalise_transaction_dates(transactions: list[dict]) -> list[dict]:
    """Applies normalise_transaction_date() to a full list in place."""
    for txn in transactions:
        normalise_transaction_date(txn)

    unparsed = sum(1 for t in transactions if t["parsed_date"] is None)
    if unparsed:
        logger.warning("%d/%d transactions had unparseable dates", unparsed, len(transactions))

    return transactions


def categorise_by_trans_type(txn: dict) -> Optional[str]:
    """Unambiguous category from trans_type alone. No text matching."""
    return TRANS_TYPE_CATEGORY_MAP.get(txn.get("trans_type"))


def categorise_by_keyword(txn: dict) -> Optional[str]:
    """Match recipient/details text against known keyword lists."""
    text = f"{txn.get('recipient', '')} {txn.get('details', '')}".lower()

    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return category

    return None


def categorise_by_llm(txn: dict) -> str:
    """
    Fallback for transactions that keyword rules can't place.
    Caches by recipient text so a merchant is only ever sent to the
    LLM once, not once per transaction.

    NOTE: not wired to Groq yet — wire this to backend/agents/jarvis.py's
    LLM client (or src/rag/llm.py) once Phase 1's plain-Python pipeline
    is verified working end-to-end without any LLM in the loop.
    """
    cache_key = (txn.get("recipient") or txn.get("details", ""))[:100].lower().strip()

    if cache_key in _llm_category_cache:
        return _llm_category_cache[cache_key]

    # Placeholder until wired up — deliberately NOT calling the LLM yet,
    # per Phase 1: stabilize the deterministic pipeline first.
    logger.info("No keyword match for '%s' — would fall back to LLM here", cache_key)
    category = "Other"

    _llm_category_cache[cache_key] = category
    return category


def categorise_transaction(txn: dict, use_llm_fallback: bool = False) -> dict:
    """
    Assign a category to a single transaction dict.

    Args:
        txn: A transaction dict from statement_parser.py
        use_llm_fallback: If False (default), unmatched transactions
                           get "Other" instead of hitting the LLM path.
                           Keep this False until Phase 1 is stable and
                           the LLM client is actually wired in.

    Returns:
        The same dict, with a "category" key added.
    """
    category = (
        categorise_by_trans_type(txn)
        or categorise_by_keyword(txn)
    )

    if category is None:
        category = categorise_by_llm(txn) if use_llm_fallback else "Other"

    txn["category"] = category
    return txn


def categorise_transactions(transactions: list[dict], use_llm_fallback: bool = False) -> list[dict]:
    """Categorise and date-normalise a full list of parsed transactions in place."""
    normalise_transaction_dates(transactions)

    for txn in transactions:
        categorise_transaction(txn, use_llm_fallback=use_llm_fallback)

    uncategorised = sum(1 for t in transactions if t["category"] == "Other")
    logger.info(
        "Categorised %d transactions — %d landed in 'Other' (%.1f%%)",
        len(transactions), uncategorised,
        100 * uncategorised / len(transactions) if transactions else 0,
    )

    return transactions