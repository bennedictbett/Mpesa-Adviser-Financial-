import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import app
from backend.database.connection import Base, get_db
from backend.database.models import TransactionRecord, BudgetOverride  # import BOTH models so their tables register

# --- Test DB setup: in-memory SQLite, overrides the real get_db dependency ---
#
# StaticPool is required here: without it, SQLAlchemy opens a NEW
# connection per request, and ":memory:" SQLite databases are
# per-connection — each new connection would see an empty database
# with no tables, even though create_all() succeeded on an earlier
# connection. StaticPool forces every session to share one connection.

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

TEST_SESSION_ID = "test-session-validation"


@pytest.fixture(autouse=True)
def seed_session():
    """
    Every test in this file needs a session_id that actually exists
    (get_session_transactions 404s on unknown IDs otherwise). Seeds
    one Food transaction, cleans up after each test so tests don't
    leak state into each other.
    """
    db = TestingSessionLocal()
    db.add(TransactionRecord(
        session_id=TEST_SESSION_ID,
        receipt_no="TEST123",
        date="01/08/2026",
        time="12:00",
        details="test transaction",
        recipient="Test",
        amount=500.0,
        trans_type="payment",
        balance=1000.0,
        category="Food",
        parsed_date=datetime(2026, 8, 1, 12, 0),
    ))
    db.commit()
    db.close()

    yield

    db = TestingSessionLocal()
    db.query(TransactionRecord).filter(TransactionRecord.session_id == TEST_SESSION_ID).delete()
    db.commit()
    db.close()


class TestBudgetAmountBounds:
    def test_negative_amount_rejected(self):
        response = client.post(
            f"/api/v1/{TEST_SESSION_ID}/budget",
            json={"category": "Food", "amount": -500},
        )
        assert response.status_code == 422

    def test_zero_amount_rejected(self):
        """gt=0 means zero itself must also be rejected, not just negatives."""
        response = client.post(
            f"/api/v1/{TEST_SESSION_ID}/budget",
            json={"category": "Food", "amount": 0},
        )
        assert response.status_code == 422

    def test_absurdly_large_amount_rejected(self):
        response = client.post(
            f"/api/v1/{TEST_SESSION_ID}/budget",
            json={"category": "Food", "amount": 999_999_999},
        )
        assert response.status_code == 422

    def test_valid_amount_accepted(self):
        response = client.post(
            f"/api/v1/{TEST_SESSION_ID}/budget",
            json={"category": "Food", "amount": 5000},
        )
        assert response.status_code == 200
        assert response.json()["amount"] == 5000.0

    def test_boundary_just_above_zero_accepted(self):
        """gt=0 should accept a tiny positive value — proves the bound
        is exclusive-zero, not accidentally excluding small valid amounts."""
        response = client.post(
            f"/api/v1/{TEST_SESSION_ID}/budget",
            json={"category": "Food", "amount": 0.01},
        )
        assert response.status_code == 200

    def test_boundary_at_max_accepted(self):
        """le=10_000_000 should accept exactly the upper bound, not reject it."""
        response = client.post(
            f"/api/v1/{TEST_SESSION_ID}/budget",
            json={"category": "Food", "amount": 10_000_000},
        )
        assert response.status_code == 200

    def test_empty_category_rejected(self):
        response = client.post(
            f"/api/v1/{TEST_SESSION_ID}/budget",
            json={"category": "", "amount": 500},
        )
        assert response.status_code == 422


class TestAnalyticsMonthValidation:
    def test_invalid_month_format_returns_422_not_500(self):
        """
        The core regression this test guards: before the fix, a bad
        month string caused an uncaught ValueError -> raw 500 error
        that leaked internals to the client instead of a clean 422.
        """
        response = client.get(f"/api/v1/{TEST_SESSION_ID}/breakdown?month=not-a-month")
        assert response.status_code == 422
        assert "detail" in response.json()

    def test_valid_month_format_succeeds(self):
        response = client.get(f"/api/v1/{TEST_SESSION_ID}/breakdown?month=2026-08")
        assert response.status_code == 200
        assert response.json()["breakdown"] == {"Food": 500.0}

    def test_invalid_month_on_summary_endpoint_returns_422(self):
        response = client.get(f"/api/v1/{TEST_SESSION_ID}/summary?month=hello")
        assert response.status_code == 422

    def test_invalid_month_on_compare_endpoint_returns_422(self):
        response = client.get(
            f"/api/v1/{TEST_SESSION_ID}/compare?month_a=bad&month_b=2026-08"
        )
        assert response.status_code == 422

    def test_unknown_session_id_returns_404_not_422(self):
        """
        A missing session should still 404 (existing behavior from
        get_session_transactions) — confirms the new try/except for
        ValueError doesn't accidentally swallow or reclassify this
        different error case.
        """
        response = client.get("/api/v1/nonexistent-session/breakdown?month=2026-08")
        assert response.status_code == 404