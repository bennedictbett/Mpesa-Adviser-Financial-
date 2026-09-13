"""
Unit tests for backend/services/transaction_service.py — the hybrid
categoriser (trans_type shortcuts + keyword rules).
"""

from backend.services.transaction_service import categorise_transaction


def _txn(recipient, details, trans_type="payment"):
    return {"recipient": recipient, "details": details, "trans_type": trans_type}


class TestKeywordCategorisation:
    """
    Each case here traces back to a real gap found by running
    scripts/measure_categoriser.py against a realistic messy
    statement — not hypothetical coverage.
    """

    def test_grocery_kiosk_categorised_as_food(self):
        txn = _txn("Unknown", "Pay Bill to 888880 - Mama Njeri Groceries")
        result = categorise_transaction(txn)
        assert result["category"] == "Food"

    def test_small_kiosk_categorised_as_food(self):
        txn = _txn("Unknown", "Buy Goods to KIOSK CHEZA 220011")
        result = categorise_transaction(txn)
        assert result["category"] == "Food"

    def test_carwash_categorised_as_transport(self):
        txn = _txn("Unknown", "Buy Goods to CARWASH JUNCTION")
        result = categorise_transaction(txn)
        assert result["category"] == "Transport"

    def test_barbershop_categorised_as_personal_care(self):
        txn = _txn("Unknown", "Buy Goods to KINYOZI STYLE CUTS")
        result = categorise_transaction(txn)
        assert result["category"] == "Personal Care"

    def test_church_offering_categorised_as_giving(self):
        txn = _txn("Unknown", "Pay Bill to 999111 - CHURCH OFFERING")
        result = categorise_transaction(txn)
        assert result["category"] == "Giving"

    def test_person_to_person_transfer_falls_to_other(self):
        """
        Documents a known, accepted limitation: there's no way to
        categorise a payment to a named individual without a
        contacts/labeling feature that doesn't exist yet. This should
        stay 'Other' — it is NOT a bug to fix.
        """
        txn = _txn("JOHN KAMAU", "Customer Transfer to JOHN KAMAU 0733221100", trans_type="sent")
        result = categorise_transaction(txn)
        assert result["category"] == "Other"