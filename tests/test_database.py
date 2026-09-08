"""
Unit tests for backend/database/ — verifies the model and session
scoping work correctly, independent of the API layer.

Uses an in-memory SQLite database (separate from the dev file
mpesa_advisor.db) so tests never touch or depend on real data,
and each test run starts from a clean slate.
"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.connection import Base
from backend.database.models import TransactionRecord


@pytest.fixture
def db_session():
    """Fresh in-memory SQLite DB per test — created and torn down each time."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def _make_record(session_id: str, amount: float, category: str = "Food", **overrides) -> TransactionRecord:
    defaults = {
        "session_id": session_id,
        "receipt_no": "RJK81ABCDE",
        "date": "01/08/2026",
        "time": "12:00",
        "details": "fake transaction",
        "recipient": "Test Recipient",
        "amount": amount,
        "trans_type": "payment",
        "balance": 1000.0,
        "category": category,
        "parsed_date": datetime(2026, 8, 1, 12, 0),
    }
    defaults.update(overrides)
    return TransactionRecord(**defaults)


class TestTransactionRecord:
    def test_saves_and_retrieves_a_record(self, db_session):
        record = _make_record("session-a", amount=500.0)
        db_session.add(record)
        db_session.commit()

        fetched = db_session.query(TransactionRecord).first()
        assert fetched.amount == 500.0
        assert fetched.category == "Food"
        assert fetched.session_id == "session-a"

    def test_to_dict_matches_analytics_service_schema(self, db_session):
        """
        analytics_service.py expects specific keys on each transaction
        dict. If to_dict() drifts from that schema, analytics silently
        breaks — this test is the tripwire for that.
        """
        record = _make_record("session-a", amount=500.0)
        db_session.add(record)
        db_session.commit()

        fetched = db_session.query(TransactionRecord).first()
        result = fetched.to_dict()

        expected_keys = {
            "receipt_no", "date", "time", "details", "recipient",
            "amount", "trans_type", "balance", "category", "parsed_date",
        }
        assert set(result.keys()) == expected_keys
        assert result["amount"] == 500.0
        assert result["parsed_date"] == datetime(2026, 8, 1, 12, 0)

    def test_null_parsed_date_is_preserved(self, db_session):
        """A transaction with an unparseable date (parsed_date=None from
        transaction_service.py) must survive a round-trip through the DB
        as None, not get coerced into some default date."""
        record = _make_record("session-a", amount=999.0, parsed_date=None)
        db_session.add(record)
        db_session.commit()

        fetched = db_session.query(TransactionRecord).first()
        assert fetched.parsed_date is None


class TestSessionScoping:
    def test_only_returns_records_for_the_requested_session(self, db_session):
        db_session.add(_make_record("session-a", amount=500.0))
        db_session.add(_make_record("session-a", amount=300.0))
        db_session.add(_make_record("session-b", amount=9999.0))  # different session
        db_session.commit()

        session_a_records = (
            db_session.query(TransactionRecord)
            .filter(TransactionRecord.session_id == "session-a")
            .all()
        )

        assert len(session_a_records) == 2
        assert all(r.session_id == "session-a" for r in session_a_records)
        assert sum(r.amount for r in session_a_records) == 800.0

    def test_unknown_session_returns_empty(self, db_session):
        db_session.add(_make_record("session-a", amount=500.0))
        db_session.commit()

        result = (
            db_session.query(TransactionRecord)
            .filter(TransactionRecord.session_id == "nonexistent")
            .all()
        )

        assert result == []

    def test_records_persist_across_separate_queries(self, db_session):
        """
        Sanity check that this is real persistence, not an artifact of
        querying the same object still in memory — insert, then query
        fresh, twice.
        """
        db_session.add(_make_record("session-a", amount=500.0))
        db_session.commit()

        first_query = db_session.query(TransactionRecord).filter(
            TransactionRecord.session_id == "session-a"
        ).count()
        second_query = db_session.query(TransactionRecord).filter(
            TransactionRecord.session_id == "session-a"
        ).count()

        assert first_query == second_query == 1