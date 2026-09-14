"""
Unit tests for backend/mcp_server.py — verifies the MCP tools return
correct, correctly-structured data.

Connects to the MCPServer instance in-process (no HTTP, no running
uvicorn needed) via mcp.Client(mcp_server_instance), and patches
SessionLocal so the tools read from an isolated in-memory SQLite
database rather than the real mpesa_advisor.db file.
"""

from datetime import datetime
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from mcp import Client

from backend.mcp_server import mcp
from backend.database.connection import Base
from backend.database.models import TransactionRecord, BudgetOverride

TEST_SESSION_ID = "test-mcp-session"


@pytest.fixture
def test_db():
    """
    Isolated in-memory SQLite DB, seeded with one Food transaction.
    StaticPool is required — see tests/test_api_validation.py for why
    a plain ':memory:' engine loses its tables across connections.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestSessionLocal()
    db.add(TransactionRecord(
        session_id=TEST_SESSION_ID,
        receipt_no="TEST123",
        date="01/08/2026",
        time="12:00",
        details="test transaction",
        recipient="Test",
        amount=850.0,
        trans_type="payment",
        balance=1000.0,
        category="Food",
        parsed_date=datetime(2026, 8, 1, 12, 0),
    ))
    db.commit()
    db.close()

    with patch("backend.mcp_server.SessionLocal", TestSessionLocal):
        yield TestSessionLocal


class TestMCPTools:
    @pytest.mark.asyncio
    async def test_lists_all_five_tools(self, test_db):
        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools.tools}
            assert names == {
                "spending_summary",
                "spending_by_category",
                "category_breakdown",
                "monthly_comparison",
                "budget_status",
            }

    @pytest.mark.asyncio
    async def test_spending_summary_returns_correct_structured_data(self, test_db):
        async with Client(mcp) as client:
            result = await client.call_tool(
                "spending_summary", {"session_id": TEST_SESSION_ID, "month": "2026-08"}
            )
            assert result.structured_content == {
                "month": "2026-08",
                "total_spent": 850.0,
                "total_received": 0.0,
                "net": -850.0,
                "transaction_count": 1,
            }

    @pytest.mark.asyncio
    async def test_spending_by_category_returns_real_computed_value(self, test_db):
        async with Client(mcp) as client:
            result = await client.call_tool(
                "spending_by_category",
                {"session_id": TEST_SESSION_ID, "category": "Food", "month": "2026-08"},
            )
            # Scalar float returns come back under the "result" key
            assert result.structured_content == {"result": 850.0}

    @pytest.mark.asyncio
    async def test_category_breakdown_returns_structured_dict_not_none(self, test_db):
        """
        Regression guard for the exact bug found via manual testing:
        category_breakdown's return used to come back as None because
        a bare `dict` return type annotation didn't get a JSON schema,
        so structured_content stayed empty. Must return real data now.
        """
        async with Client(mcp) as client:
            result = await client.call_tool(
                "category_breakdown", {"session_id": TEST_SESSION_ID, "month": "2026-08"}
            )
            assert result.structured_content is not None
            assert result.structured_content == {"Food": 850.0}

    @pytest.mark.asyncio
    async def test_budget_status_no_history_returns_message(self, test_db):
        async with Client(mcp) as client:
            result = await client.call_tool(
                "budget_status",
                {"session_id": TEST_SESSION_ID, "category": "Food", "month": "2026-08"},
            )
            data = result.structured_content
            assert data["actual_spent"] == 850.0
            assert data["budget"] is None
            assert "message" in data

    @pytest.mark.asyncio
    async def test_monthly_comparison_returns_structured_data(self, test_db):
        async with Client(mcp) as client:
            result = await client.call_tool(
                "monthly_comparison",
                {"session_id": TEST_SESSION_ID, "month_a": "2026-07", "month_b": "2026-08"},
            )
            data = result.structured_content
            assert data["month_a"] == "2026-07"
            assert data["month_b"] == "2026-08"
            assert data["breakdown_b"] == {"Food": 850.0}

    @pytest.mark.asyncio
    async def test_unknown_session_id_raises_tool_error(self, test_db):
        """
        Mirrors the REST API's 404 behavior (get_session_transactions
        raises HTTPException for an unknown session) — confirms the MCP
        layer doesn't silently swallow this into an empty/wrong result.
        """
        async with Client(mcp) as client:
            result = await client.call_tool(
                "spending_by_category",
                {"session_id": "nonexistent-session", "category": "Food", "month": "2026-08"},
            )
            assert result.is_error is True