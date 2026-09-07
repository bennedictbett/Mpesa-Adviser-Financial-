"""
Analytics query endpoints. Reads transactions previously ingested
via transactions.py (by session_id) and runs analytics_service.py
functions against them.
"""

from fastapi import APIRouter

from backend.models.schemas import (
    SpendingSummaryResponse,
    CategoryBreakdownResponse,
    MonthlyComparisonResponse,
)
from backend.api.routes.transactions import get_session_transactions
from backend.services.analytics_service import (
    get_spending_summary,
    get_category_breakdown,
    get_monthly_comparison,
)

router = APIRouter(prefix="/api/v1", tags=["analytics"])


@router.get("/{session_id}/summary", response_model=SpendingSummaryResponse)
def spending_summary(session_id: str, month: str):
    txns = get_session_transactions(session_id)
    return get_spending_summary(txns, month=month)


@router.get("/{session_id}/breakdown", response_model=CategoryBreakdownResponse)
def category_breakdown(session_id: str, month: str):
    txns = get_session_transactions(session_id)
    breakdown = get_category_breakdown(txns, month=month)
    return {"month": month, "breakdown": breakdown}


@router.get("/{session_id}/compare", response_model=MonthlyComparisonResponse)
def monthly_comparison(session_id: str, month_a: str, month_b: str):
    txns = get_session_transactions(session_id)
    return get_monthly_comparison(txns, month_a=month_a, month_b=month_b)