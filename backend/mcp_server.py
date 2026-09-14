"""
MCP server exposing the same read-only financial-analytics tools
that Jarvis uses internally (backend/agents/tools.py), but via the
standard Model Context Protocol instead of Groq's proprietary
function-calling format — so any MCP-compatible client (Claude
Desktop, another agent, etc.) can query the same data.

Uses the mcp 2.x SDK (MCPServer, formerly FastMCP in 1.x — see
https://py.sdk.modelcontextprotocol.io/v2/migration/).

Tool return types are explicit Pydantic models / typed dicts rather
than bare `dict`, since the SDK only auto-populates a tool result's
structured_content for return types it can generate a JSON schema
from — a bare `dict` return type falls back to an unstructured
TextContent block instead (found via scripts/test_mcp_client.py).

This does NOT replace Jarvis's existing tool-calling — that stays
as-is. This is a second, standard interface onto the same
analytics_service.py / budget_service.py functions, following the
same read-only guarantee documented in SECURITY.md.
"""

from pydantic import BaseModel
from mcp.server.mcpserver import MCPServer

from backend.database.connection import SessionLocal
from backend.api.routes.transactions import get_session_transactions
from backend.api.routes.budget import get_session_overrides
from backend.services.analytics_service import (
    get_spending_summary,
    get_spending_by_category,
    get_category_breakdown,
    get_monthly_comparison,
)
from backend.services.budget_service import get_budget_status as _get_budget_status

mcp = MCPServer("mpesa-financial-advisor")


# --- Response models: give the SDK a real schema to structure output with ---

class SpendingSummary(BaseModel):
    month: str
    total_spent: float
    total_received: float
    net: float
    transaction_count: int


class MonthlyComparison(BaseModel):
    month_a: str
    month_b: str
    breakdown_a: dict[str, float]
    breakdown_b: dict[str, float]
    deltas: dict[str, float]


class BudgetStatus(BaseModel):
    category: str
    month: str
    actual_spent: float
    budget: float | None
    budget_source: str | None
    percent_used: float | None = None
    status: str | None = None
    message: str | None = None


def _load_session(session_id: str):
    db = SessionLocal()
    try:
        transactions = get_session_transactions(session_id, db)
        overrides = get_session_overrides(session_id, db)
        return transactions, overrides
    finally:
        db.close()


@mcp.tool()
def spending_summary(session_id: str, month: str) -> SpendingSummary:
    """Total spent, total received, and net for a given month (YYYY-MM)."""
    transactions, _ = _load_session(session_id)
    return SpendingSummary(**get_spending_summary(transactions, month=month))


@mcp.tool()
def spending_by_category(session_id: str, category: str, month: str) -> float:
    """Total amount spent in one category (e.g. Food, Transport) for a given month (YYYY-MM)."""
    transactions, _ = _load_session(session_id)
    return get_spending_by_category(transactions, category=category, month=month)


@mcp.tool()
def category_breakdown(session_id: str, month: str) -> dict[str, float]:
    """Spending broken down by all categories for a given month (YYYY-MM), sorted highest first."""
    transactions, _ = _load_session(session_id)
    return get_category_breakdown(transactions, month=month)


@mcp.tool()
def monthly_comparison(session_id: str, month_a: str, month_b: str) -> MonthlyComparison:
    """Per-category spending change between two months (YYYY-MM each)."""
    transactions, _ = _load_session(session_id)
    return MonthlyComparison(**get_monthly_comparison(transactions, month_a=month_a, month_b=month_b))


@mcp.tool()
def budget_status(session_id: str, category: str, month: str) -> BudgetStatus:
    """
    Whether spending in a category is under, near, or over budget for
    a given month (YYYY-MM). Uses the user's manual override if set,
    otherwise a suggested budget based on the average of prior months.
    """
    transactions, overrides = _load_session(session_id)
    result = _get_budget_status(
        transactions,
        category=category,
        month=month,
        override_amount=overrides.get(category),
    )
    return BudgetStatus(**result)