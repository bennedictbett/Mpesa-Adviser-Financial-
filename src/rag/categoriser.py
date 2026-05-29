"""
Categorises M-Pesa transactions into spending categories.

This is the file that transforms the project from a document Q&A bot
into a genuine personal financial advisor.

The problem:
  M-Pesa statements contain raw transaction names like:
    "JOHN KAMAU", "0712345678", "NAIVAS LTD", "KENYA POWER"
  These names don't clearly indicate spending categories.
  A user cannot easily know how much they spend on food vs transport
  without reading every line manually.

The solution — three layers:
  Layer 1: Keyword matching (fast, free, catches ~60% of transactions)
    Known business names and patterns mapped to categories.

  Layer 2: LLM inference (catches ~25% more)
    For unrecognised names, ask Groq/Llama to infer the category
    from the name, amount, and time of day.

  Layer 3: "Other" fallback
    Anything the LLM cannot confidently categorise is labelled
    "Other" — never guessed wrongly.

Categories:
  Food          - restaurants, supermarkets, food vendors
  Transport     - matatu, ride-hailing, fuel, parking
  Utilities     - electricity, water, internet, TV
  Airtime       - airtime and data purchases
  Shopping      - clothing, electronics, general retail
  Family        - transfers to family and friends
  Banking       - bank transfers, loan repayments, savings
  Business      - business-related payments
  Other         - unrecognised transactions

Files that import from here:
  - src/rag/chain.py  (analyse_statement() enriches context with categories)
"""

import json
import logging
import re
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage

from src.rag.llm import get_llm

logger = logging.getLogger(__name__)


# Category definitions

CATEGORIES = {
    "Food": [
        "naivas", "quickmart", "carrefour", "java", "kfc", "artcaffe",
        "subway", "pizza", "restaurant", "hotel", "mama", "nyama", "ugali",
        "chicken", "burger", "cafe", "bakery", "grocery", "supermarket",
        "market", "food", "canteen", "cafeteria", "eating", "chips",
        "shawarma", "pilau", "nyuchini", "kibandaski", "kiosk",
    ],
    "Transport": [
        "uber", "bolt", "little", "matatu", "safiri", "parking",
        "fuel", "petrol", "shell", "total", "kenol", "kobil", "oilibya",
        "taxi", "boda", "bodaboda", "tuk", "bus", "sacco", "transport",
        "fare", "ride", "travel", "station", "terminus",
    ],
    "Utilities": [
        "kenya power", "kplc", "nairobi water", "zuku", "safaricom home",
        "faiba", "startimes", "dstv", "gotv", "water", "electricity",
        "power", "internet", "wifi", "broadband", "cable", "utilities",
        "rent", "landlord", "caretaker",
    ],
    "Airtime": [
        "airtime", "safaricom", "airtel", "telkom", "equitel",
        "data", "bundle", "credit",
    ],
    "Shopping": [
        "jumia", "kilimall", "masoko", "clothing", "shoes", "fashion",
        "boutique", "hardware", "electronics", "phone", "laptop",
        "mall", "plaza", "centre", "store", "shop", "retail",
    ],
    "Banking": [
        "equity", "kcb", "cooperative", "ncba", "absa", "stanbic",
        "family bank", "dtb", "i&m", "bank", "loan", "repayment",
        "mortgage", "insurance", "britam", "jubilee", "aar", "sacco",
        "savings", "investment", "mpesa charges", "withdraw", "fuliza",
        "mshwari", "kcb mpesa",
    ],
    "Business": [
        "paybill", "till", "buygoods", "supplier", "invoice",
        "payment", "services", "consulting", "agency", "enterprise",
        "company", "ltd", "limited", "kenya", "solutions",
    ],
    "Family": [
        # Family transfers are usually phone numbers or personal names
        # handled by LLM inference layer
    ],
}


# Transaction data class 

class Transaction:
    """
    Represents a single M-Pesa transaction extracted from a statement.
    """
    def __init__(
        self,
        recipient:    str,
        amount:       float,
        date:         Optional[str] = None,
        time:         Optional[str] = None,
        trans_type:   Optional[str] = None,
    ):
        self.recipient  = recipient.strip()
        self.amount     = amount
        self.date       = date
        self.time       = time
        self.trans_type = trans_type
        self.category   = "Other"
        self.confidence = 0.0

    def to_dict(self) -> dict:
        return {
            "recipient":  self.recipient,
            "amount":     self.amount,
            "date":       self.date,
            "time":       self.time,
            "trans_type": self.trans_type,
            "category":   self.category,
            "confidence": self.confidence,
        }


# Layer 1: Keyword matching

def categorise_by_keyword(transaction: Transaction) -> Optional[str]:
    """
    Match transaction recipient against known keyword patterns.

    Case-insensitive substring matching — if any keyword from a
    category appears in the recipient name, assign that category.

    Args:
        transaction: Transaction object to categorise

    Returns:
        str: Category name if matched, None if no match found
    """
    name_lower = transaction.recipient.lower()

    for category, keywords in CATEGORIES.items():
        for keyword in keywords:
            if keyword.lower() in name_lower:
                logger.debug(
                    "Keyword match: '%s' → %s (keyword: '%s')",
                    transaction.recipient, category, keyword
                )
                return category

    # Phone number pattern — likely a personal transfer (Family)
    if re.match(r"^0[17]\d{8}$", transaction.recipient.strip()):
        return "Family"

    return None


# Layer 2: LLM inference 

def categorise_by_llm(transactions: list[Transaction]) -> list[Transaction]:
    """
    Use Groq/Llama to infer categories for unrecognised transactions.

    Batches all unrecognised transactions into a single LLM call
    to avoid multiple API calls — efficient and cost-effective.

    Args:
        transactions: List of Transaction objects with category == "Other"

    Returns:
        list[Transaction]: Same transactions with categories updated
                           where LLM was confident enough to categorise
    """
    if not transactions:
        return transactions

    logger.info(
        "LLM inference for %d unrecognised transactions", len(transactions)
    )

    # Build the batch prompt
    transaction_lines = "\n".join([
        f"{i+1}. Recipient: {t.recipient} | Amount: KES {t.amount}"
        + (f" | Time: {t.time}" if t.time else "")
        for i, t in enumerate(transactions)
    ])

    prompt = f"""You are categorising M-Pesa transactions for a Kenyan user.

For each transaction below, assign ONE category from this list:
Food, Transport, Utilities, Airtime, Shopping, Banking, Business, Family, Other

Rules:
- Phone numbers (07xx or 01xx) are usually Family transfers
- Generic business names ending in "Ltd" or "Limited" are Business
- If you cannot confidently categorise, use "Other"
- Respond ONLY with a JSON array, no explanation

Transactions:
{transaction_lines}

Respond with a JSON array of objects, one per transaction:
[
  {{"index": 1, "category": "Food",   "confidence": 0.9}},
  {{"index": 2, "category": "Family", "confidence": 0.8}},
  ...
]

JSON array only, no other text:"""

    try:
        llm = get_llm()
        response = llm.invoke([HumanMessage(content=prompt)])
        raw = response.content.strip()

        # Clean JSON fences if present
        raw = re.sub(r"```json|```", "", raw).strip()

        results = json.loads(raw)

        for item in results:
            idx        = item.get("index", 0) - 1
            category   = item.get("category", "Other")
            confidence = float(item.get("confidence", 0.0))

            if 0 <= idx < len(transactions) and confidence >= 0.7:
                transactions[idx].category   = category
                transactions[idx].confidence = confidence
                logger.debug(
                    "LLM categorised: '%s' → %s (confidence: %.2f)",
                    transactions[idx].recipient, category, confidence
                )

    except (json.JSONDecodeError, Exception) as e:
        logger.warning("LLM categorisation failed: %s — keeping 'Other'", e)

    return transactions


# Main categorisation function 

def categorise_transactions(
    transactions: list[dict],
) -> list[dict]:
    """
    Categorise a list of M-Pesa transactions using keyword + LLM layers.

    Main entry point called by chain.py when analysing an M-Pesa statement.

    Args:
        transactions: List of transaction dicts, each with at minimum:
                      - "recipient" (str)
                      - "amount"    (float)
                      Optional: "date", "time", "trans_type"

    Returns:
        list[dict]: Same transactions with "category" and "confidence" added
    """
    if not transactions:
        return []

    logger.info("Categorising %d transactions", len(transactions))

    # Convert to Transaction objects
    trans_objects = [
        Transaction(
            recipient=t.get("recipient", "Unknown"),
            amount=float(t.get("amount", 0)),
            date=t.get("date"),
            time=t.get("time"),
            trans_type=t.get("trans_type"),
        )
        for t in transactions
    ]

    # Layer 1 — keyword matching
    unmatched = []
    for trans in trans_objects:
        category = categorise_by_keyword(trans)
        if category:
            trans.category   = category
            trans.confidence = 1.0
        else:
            unmatched.append(trans)

    logger.info(
        "Keyword matching: %d/%d categorised, %d sent to LLM",
        len(trans_objects) - len(unmatched),
        len(trans_objects),
        len(unmatched),
    )

    # Layer 2 — LLM inference for unmatched
    if unmatched:
        categorise_by_llm(unmatched)

    # Build summary
    results = [t.to_dict() for t in trans_objects]

    categorised = sum(1 for r in results if r["category"] != "Other")
    logger.info(
        "Categorisation complete: %d/%d categorised (%d Other)",
        categorised,
        len(results),
        len(results) - categorised,
    )

    return results


def summarise_by_category(transactions: list[dict]) -> dict:
    """
    Summarise total spending by category.

    Takes categorised transactions and returns total KES spent
    per category, sorted highest to lowest.

    Args:
        transactions: Categorised transaction dicts from categorise_transactions()

    Returns:
        dict: Category → total KES spent, sorted descending
              e.g. {"Food": 8500.0, "Transport": 3200.0, "Other": 1500.0}
    """
    totals: dict[str, float] = {}

    for trans in transactions:
        category = trans.get("category", "Other")
        amount   = float(trans.get("amount", 0))
        totals[category] = totals.get(category, 0) + amount

    # Sort by amount descending
    return dict(sorted(totals.items(), key=lambda x: x[1], reverse=True))