"""
Combines a user's budget override (if set) with a historical-average
suggestion (if not) to produce a budget status for a category/month.

This is the function get_budget_status wraps for Jarvis — see
backend/agents/tools.py.
"""

from backend.services.analytics_service import (
    get_spending_by_category,
    get_historical_average_spending,
)


def get_budget_status(
    transactions: list[dict],
    category: str,
    month: str,
    override_amount: float | None = None,
    lookback_months: int = 3,
) -> dict:
    actual_spent = get_spending_by_category(transactions, category, month)

    if override_amount is not None:
        budget = override_amount
        budget_source = "user_set"
    else:
        budget = get_historical_average_spending(transactions, category, month, lookback_months)
        budget_source = "suggested_average" if budget is not None else None

    if budget is None:
        return {
            "category": category,
            "month": month,
            "actual_spent": actual_spent,
            "budget": None,
            "budget_source": None,
            "message": (
                f"No budget is set for {category} and there isn't enough "
                f"prior-month data yet to suggest one."
            ),
        }

    percent_used = round(100 * actual_spent / budget, 1) if budget > 0 else None

    if percent_used is None:
        status = "no_budget"
    elif percent_used < 80:
        status = "under"
    elif percent_used <= 100:
        status = "near"
    else:
        status = "over"

    return {
        "category": category,
        "month": month,
        "actual_spent": actual_spent,
        "budget": budget,
        "budget_source": budget_source,
        "percent_used": percent_used,
        "status": status,
    }