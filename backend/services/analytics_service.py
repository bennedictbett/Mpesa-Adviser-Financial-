"""
Computes financial analytics from categorised, date-normalised
transactions.

Deliberately does NO parsing, categorisation, or LLM calls — takes
transaction_service.categorise_transactions() output as its only
input. Every function here returns real numbers computed from real
data, so Jarvis (Phase 2) can call these as tools and simply explain
the result, rather than doing arithmetic itself.

Input schema expected on each transaction dict:
    amount        float
    trans_type    str   sent|received|withdraw|payment|airtime|charges|deposit|other
    category      str   Food|Transport|Utilities|Airtime|... (from transaction_service)
    parsed_date   datetime | None (from transaction_service)

Files that import from here:
  - backend/agents/tools.py   (wraps these as Jarvis-callable tools)
  - backend/api/routes/analytics.py
"""

import logging
from collections import defaultdict
from datetime import datetime

logger = logging.getLogger(__name__)


# Which trans_types count as money leaving the account ("spending")
# vs money coming in. Used by get_spending_summary().
OUTFLOW_TYPES = {"sent", "payment", "withdraw", "airtime", "charges"}
INFLOW_TYPES = {"received", "deposit"}


def _filter_by_month(transactions: list[dict], month: str) -> list[dict]:
    """
    Args:
        month: "YYYY-MM", e.g. "2026-08"

    Skips transactions with parsed_date=None — they can't be placed
    in a month, so they're excluded rather than guessed at.
    """
    try:
        target_year, target_month = (int(p) for p in month.split("-"))
    except (ValueError, AttributeError):
        raise ValueError(f"month must be 'YYYY-MM', got: {month!r}")

    return [
        t for t in transactions
        if t.get("parsed_date")
        and t["parsed_date"].year == target_year
        and t["parsed_date"].month == target_month
    ]


def get_transactions(
    transactions: list[dict],
    month: str | None = None,
    category: str | None = None,
) -> list[dict]:
    """
    Raw filtered transaction rows. Foundation for everything else —
    other analytics functions should call this rather than
    re-filtering independently.
    """
    result = transactions

    if month:
        result = _filter_by_month(result, month)

    if category:
        result = [t for t in result if t.get("category") == category]

    return result


def get_spending_summary(transactions: list[dict], month: str) -> dict:
    """
    Total spent, total received, and net for a given month.

    "Spent" = sum of OUTFLOW_TYPES transactions (sent, payment,
    withdraw, airtime, charges). "Received" = INFLOW_TYPES.
    """
    month_txns = _filter_by_month(transactions, month)

    total_spent = sum(t["amount"] for t in month_txns if t["trans_type"] in OUTFLOW_TYPES)
    total_received = sum(t["amount"] for t in month_txns if t["trans_type"] in INFLOW_TYPES)

    return {
        "month": month,
        "total_spent": round(total_spent, 2),
        "total_received": round(total_received, 2),
        "net": round(total_received - total_spent, 2),
        "transaction_count": len(month_txns),
    }


def get_spending_by_category(transactions: list[dict], category: str, month: str) -> float:
    """
    The exact function Jarvis calls for "how much did I spend on X".
    Returns a real computed float — never text for an LLM to sum.

    Only counts OUTFLOW_TYPES within the category — e.g. if someone
    is refunded and it lands in "Food" as a received transaction,
    it won't inflate the spend figure.
    """
    month_txns = _filter_by_month(transactions, month)

    total = sum(
        t["amount"] for t in month_txns
        if t.get("category") == category and t["trans_type"] in OUTFLOW_TYPES
    )

    return round(total, 2)


def get_category_breakdown(transactions: list[dict], month: str) -> dict[str, float]:
    """
    category -> amount spent, for the dashboard chart and for Jarvis
    answering "what do I spend most on". Only counts outflows.
    """
    month_txns = _filter_by_month(transactions, month)

    breakdown: dict[str, float] = defaultdict(float)
    for t in month_txns:
        if t["trans_type"] in OUTFLOW_TYPES:
            breakdown[t.get("category", "Other")] += t["amount"]

    return {cat: round(amt, 2) for cat, amt in sorted(breakdown.items(), key=lambda kv: -kv[1])}


def get_monthly_comparison(transactions: list[dict], month_a: str, month_b: str) -> dict:
    """
    Per-category spending delta between two months (month_b vs month_a).
    Positive delta = spent more in month_b.
    """
    breakdown_a = get_category_breakdown(transactions, month_a)
    breakdown_b = get_category_breakdown(transactions, month_b)

    all_categories = set(breakdown_a) | set(breakdown_b)

    deltas = {
        cat: round(breakdown_b.get(cat, 0.0) - breakdown_a.get(cat, 0.0), 2)
        for cat in all_categories
    }

    return {
        "month_a": month_a,
        "month_b": month_b,
        "breakdown_a": breakdown_a,
        "breakdown_b": breakdown_b,
        "deltas": dict(sorted(deltas.items(), key=lambda kv: -abs(kv[1]))),
    }