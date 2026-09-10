"""
Unit tests for backend/services/analytics_service.py.

Uses hand-built fake transactions rather than a real statement, so
the expected numbers are known exactly — this is what proves the
aggregation math itself is correct, independent of parsing/categorising.
"""

from datetime import datetime

import pytest

from backend.services.analytics_service import (
    get_transactions,
    get_spending_summary,
    get_spending_by_category,
    get_category_breakdown,
    get_monthly_comparison,
    get_historical_average_spending,  # add this
)


def _txn(amount, trans_type, category, date_str, month="2026-08"):
    """Helper to build a fake transaction dict matching the real schema."""
    day, mon, year = date_str.split("/")
    return {
        "receipt_no": "TEST12345",
        "date": date_str,
        "time": "12:00",
        "details": f"fake {category} transaction",
        "recipient": "Test Recipient",
        "amount": amount,
        "trans_type": trans_type,
        "balance": 1000.0,
        "category": category,
        "parsed_date": datetime(int(year), int(mon), int(day), 12, 0),
    }


@pytest.fixture
def sample_transactions():
    return [
        # August 2026 — spending
        _txn(500.0, "payment", "Food", "01/08/2026"),
        _txn(300.0, "payment", "Food", "15/08/2026"),
        _txn(200.0, "sent", "Transport", "10/08/2026"),
        _txn(1000.0, "withdraw", "Cash Withdrawal", "20/08/2026"),
        _txn(50.0, "airtime", "Airtime", "05/08/2026"),
        # August 2026 — income
        _txn(5000.0, "received", "Other", "01/08/2026"),
        # September 2026 — spending, for comparison test
        _txn(800.0, "payment", "Food", "03/09/2026"),
        _txn(100.0, "sent", "Transport", "12/09/2026"),
        # A transaction with no parseable date — should be excluded
        # from all month-filtered results, never guessed at.
        {
            **_txn(999.0, "payment", "Food", "01/08/2026"),
            "parsed_date": None,
        },
    ]


class TestGetTransactions:
    def test_filters_by_month(self, sample_transactions):
        result = get_transactions(sample_transactions, month="2026-08")
        # 6 August txns with valid dates (the None-date one is excluded)
        assert len(result) == 6

    def test_filters_by_category(self, sample_transactions):
        result = get_transactions(sample_transactions, category="Food")
        # Food appears 4 times total: Aug (500, 300), Sep (800), and
        # the None-date one (999) — category-only filtering doesn't
        # touch date, so all 4 match here.
        assert len(result) == 4

    def test_filters_by_month_and_category(self, sample_transactions):
        result = get_transactions(sample_transactions, month="2026-08", category="Food")
        assert len(result) == 2  # the None-date Food txn is excluded by month filter

    def test_excludes_unparseable_dates_from_month_filter(self, sample_transactions):
        result = get_transactions(sample_transactions, month="2026-08")
        assert all(t["parsed_date"] is not None for t in result)

    def test_invalid_month_format_raises(self, sample_transactions):
        with pytest.raises(ValueError):
            get_transactions(sample_transactions, month="August 2026")


class TestGetSpendingSummary:
    def test_totals_are_correct(self, sample_transactions):
        summary = get_spending_summary(sample_transactions, month="2026-08")

        # spent = 500 + 300 + 200 + 1000 + 50 = 2050.0
        assert summary["total_spent"] == 2050.0
        # received = 5000.0
        assert summary["total_received"] == 5000.0
        assert summary["net"] == 2950.0
        assert summary["transaction_count"] == 6

    def test_empty_month_returns_zeros(self, sample_transactions):
        summary = get_spending_summary(sample_transactions, month="2026-01")
        assert summary["total_spent"] == 0
        assert summary["total_received"] == 0
        assert summary["transaction_count"] == 0


class TestGetSpendingByCategory:
    def test_sums_correct_category_only(self, sample_transactions):
        food_spend = get_spending_by_category(sample_transactions, "Food", month="2026-08")
        assert food_spend == 800.0  # 500 + 300, excludes the None-date 999 txn

    def test_unmatched_category_returns_zero(self, sample_transactions):
        result = get_spending_by_category(sample_transactions, "Utilities", month="2026-08")
        assert result == 0.0

    def test_does_not_count_inflows(self, sample_transactions):
        # "received" transactions should never inflate a spend figure,
        # even if miscategorised into a spending category.
        txns = sample_transactions + [_txn(2000.0, "received", "Food", "02/08/2026")]
        food_spend = get_spending_by_category(txns, "Food", month="2026-08")
        assert food_spend == 800.0  # unchanged — the 2000 received doesn't count


class TestGetCategoryBreakdown:
    def test_breakdown_matches_manual_sums(self, sample_transactions):
        breakdown = get_category_breakdown(sample_transactions, month="2026-08")

        assert breakdown["Food"] == 800.0
        assert breakdown["Transport"] == 200.0
        assert breakdown["Cash Withdrawal"] == 1000.0
        assert breakdown["Airtime"] == 50.0
        assert "Other" not in breakdown  # "received" isn't an outflow type

    def test_sorted_descending_by_amount(self, sample_transactions):
        breakdown = get_category_breakdown(sample_transactions, month="2026-08")
        amounts = list(breakdown.values())
        assert amounts == sorted(amounts, reverse=True)


class TestGetMonthlyComparison:
    def test_deltas_are_correct(self, sample_transactions):
        comparison = get_monthly_comparison(sample_transactions, "2026-08", "2026-09")

        # Food: Sept 800 - Aug 800 = 0
        assert comparison["deltas"]["Food"] == 0.0
        # Transport: Sept 100 - Aug 200 = -100
        assert comparison["deltas"]["Transport"] == -100.0
        # Cash Withdrawal only appears in August: 0 - 1000 = -1000
        assert comparison["deltas"]["Cash Withdrawal"] == -1000.0

    def test_includes_categories_present_in_either_month(self, sample_transactions):
        comparison = get_monthly_comparison(sample_transactions, "2026-08", "2026-09")
        assert set(comparison["deltas"].keys()) == {"Food", "Transport", "Cash Withdrawal", "Airtime"}

class TestGetHistoricalAverageSpending:
    @pytest.fixture
    def multi_month_transactions(self):
        """Three prior months of Food spending, plus the target month."""
        return [
            _txn(400.0, "payment", "Food", "01/05/2026"),   # May
            _txn(600.0, "payment", "Food", "01/06/2026"),   # June
            _txn(800.0, "payment", "Food", "01/07/2026"),   # July
            _txn(999.0, "payment", "Food", "01/08/2026"),   # August (target month — must be excluded)
        ]

    def test_averages_prior_months_only(self, multi_month_transactions):
        result = get_historical_average_spending(
            multi_month_transactions, "Food", before_month="2026-08", lookback_months=3
        )
        # (400 + 600 + 800) / 3 = 600.0 — August's 999 must NOT be included
        assert result == 600.0

    def test_respects_lookback_months_limit(self, multi_month_transactions):
        result = get_historical_average_spending(
            multi_month_transactions, "Food", before_month="2026-08", lookback_months=2
        )
        # Only the 2 most recent prior months: June (600) + July (800) / 2 = 700.0
        assert result == 700.0

    def test_returns_none_with_no_prior_data(self):
        # Only the target month itself has data — no history to average.
        txns = [_txn(500.0, "payment", "Food", "01/08/2026")]
        result = get_historical_average_spending(txns, "Food", before_month="2026-08")
        assert result is None

    def test_zero_history_in_category_returns_zero_not_none(self, multi_month_transactions):
        """
        Distinguishes two different situations: a month with NO statement
        data at all (excluded from the average, tested above) vs. a month
        WITH data where this specific category simply had no spending
        (correctly averages to 0.0 — a real, reportable fact).
        """
        result = get_historical_average_spending(
            multi_month_transactions, "Utilities", before_month="2026-08"
        )
        assert result == 0.0

    def test_month_with_no_transactions_at_all_is_not_treated_as_zero(self):
        """
        Regression guard: a calendar month with NO statement data present
        must be excluded from the average entirely — not silently counted
        as a real $0 month, which would drag the average down incorrectly.
        """
        txns = [
            _txn(1000.0, "payment", "Food", "01/06/2026"),  # June has data
            # July has NO transactions at all — no statement covers it
            _txn(500.0, "payment", "Food", "01/08/2026"),   # target month
        ]
        result = get_historical_average_spending(txns, "Food", before_month="2026-08", lookback_months=3)
        # Only June counts — July isn't a real $0 month, it's just missing data
        assert result == 1000.0

    def test_invalid_before_month_format_raises(self, multi_month_transactions):
        with pytest.raises(ValueError):
            get_historical_average_spending(multi_month_transactions, "Food", before_month="August 2026")