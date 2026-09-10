"""
Unit tests for backend/services/budget_service.py — the
override-vs-suggestion branching and status thresholds.
"""

from datetime import datetime

import pytest

from backend.services.budget_service import get_budget_status


def _txn(amount, trans_type, category, date_str):
    day, mon, year = date_str.split("/")
    return {
        "amount": amount,
        "trans_type": trans_type,
        "category": category,
        "parsed_date": datetime(int(year), int(mon), int(day), 12, 0),
    }


@pytest.fixture
def transactions_with_history():
    return [
        _txn(400.0, "payment", "Food", "01/06/2026"),
        _txn(600.0, "payment", "Food", "01/07/2026"),
        _txn(500.0, "payment", "Food", "01/08/2026"),  # target month: 500 spent
    ]


class TestGetBudgetStatus:
    def test_uses_override_when_provided(self, transactions_with_history):
        result = get_budget_status(
            transactions_with_history, "Food", month="2026-08", override_amount=1000.0
        )
        assert result["budget"] == 1000.0
        assert result["budget_source"] == "user_set"

    def test_uses_historical_average_when_no_override(self, transactions_with_history):
        result = get_budget_status(transactions_with_history, "Food", month="2026-08")
        # avg of June (400) + July (600) = 500.0
        assert result["budget"] == 500.0
        assert result["budget_source"] == "suggested_average"

    def test_override_takes_priority_over_average_even_when_both_available(self, transactions_with_history):
        """The user's explicit choice must always win over the computed suggestion."""
        result = get_budget_status(
            transactions_with_history, "Food", month="2026-08", override_amount=2000.0
        )
        assert result["budget"] == 2000.0
        assert result["budget_source"] == "user_set"

    def test_no_budget_and_no_history_returns_none_budget_with_message(self):
        txns = [_txn(500.0, "payment", "Food", "01/08/2026")]  # no prior months
        result = get_budget_status(txns, "Food", month="2026-08")

        assert result["budget"] is None
        assert result["budget_source"] is None
        assert "message" in result

    def test_status_is_under_when_below_80_percent(self, transactions_with_history):
        # 500 actual / 1000 override = 50% -> under
        result = get_budget_status(
            transactions_with_history, "Food", month="2026-08", override_amount=1000.0
        )
        assert result["percent_used"] == 50.0
        assert result["status"] == "under"

    def test_status_is_near_between_80_and_100_percent(self, transactions_with_history):
        # 500 actual / 550 override = ~90.9% -> near
        result = get_budget_status(
            transactions_with_history, "Food", month="2026-08", override_amount=550.0
        )
        assert 80 <= result["percent_used"] <= 100
        assert result["status"] == "near"

    def test_status_is_over_when_above_100_percent(self, transactions_with_history):
        # 500 actual / 300 override = ~166.7% -> over
        result = get_budget_status(
            transactions_with_history, "Food", month="2026-08", override_amount=300.0
        )
        assert result["percent_used"] > 100
        assert result["status"] == "over"

    def test_boundary_exactly_80_percent_is_near_not_under(self, transactions_with_history):
        # 500 / 625 = exactly 80.0% -> should be "near" (>= 80), not "under"
        result = get_budget_status(
            transactions_with_history, "Food", month="2026-08", override_amount=625.0
        )
        assert result["percent_used"] == 80.0
        assert result["status"] == "near"

    def test_boundary_exactly_100_percent_is_near_not_over(self, transactions_with_history):
        # 500 / 500 = exactly 100% -> should be "near" (<= 100), not "over"
        result = get_budget_status(
            transactions_with_history, "Food", month="2026-08", override_amount=500.0
        )
        assert result["percent_used"] == 100.0
        assert result["status"] == "near"

    def test_actual_spent_is_always_the_real_computed_value(self, transactions_with_history):
        """actual_spent must come from get_spending_by_category regardless
        of what budget_source is used — the two are independent."""
        result = get_budget_status(
            transactions_with_history, "Food", month="2026-08", override_amount=999999.0
        )
        assert result["actual_spent"] == 500.0