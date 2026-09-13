from src.rag.statement_parser import parse_statement_text

def test_parses_transaction_with_alphabetic_merchant_name():
    """
    Regression test: merchant names that are 8-12 uppercase letters
    (e.g. SUPERMARKET, QUICKMART) must not be mistaken for a receipt
    number and split the transaction into unparseable fragments.
    """
    text = "RJK81ABCDE 01/08/2026 12:34 Customer Transfer to NAIVAS SUPERMARKET -500.00 12450.00"
    result = parse_statement_text(text)

    assert len(result) == 1
    assert result[0]["amount"] == 500.0
    assert result[0]["balance"] == 12450.0

def test_mpesa_charge_singular_hyphenated_form_is_classified_as_charges():
    """
    Regression guard: 'M-PESA Charge' (singular, hyphenated) must match
    the 'charges' trans_type, not fall through to 'other'. Found via
    real-world messy-statement testing — the original keyword list only
    had the plural 'mpesa charges' form.
    """
    text = "RJK81ABDA5 12/08/2026 20:00 M-PESA Charge -22.00 29058.00"
    result = parse_statement_text(text)

    assert len(result) == 1
    assert result[0]["trans_type"] == "charges"