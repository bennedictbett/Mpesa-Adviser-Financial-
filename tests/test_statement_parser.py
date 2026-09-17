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

def test_parses_bracket_semicolon_notation_format():
    """
    Regression guard for the SMS/USSD (*334#) mini-statement export
    format, found via real frontend testing — no receipt number, no
    balance, bracket/semicolon-delimited fields.
    """
    text = """UIH0560T3J
[20260917; ;Customer Send Money; 07****kha;Ksh40.00]Completed
[20260916; ;Customer Payment to Pochi; 01****uma;Ksh195.00]Completed
[20260916; ;Customer Send Money; 25****IMO;Ksh200.00]Completed
[20260916; ;Customer Send Money; 25****NGO;Ksh100.00]Completed
[20260916; ;Airtime Purchase; 999999999 - Safaricom Limited;Ksh10.00]Completed
Transaction cost, Ksh0.00."""

    result = parse_statement_text(text)

    # 5 real transactions — the trailing "Transaction cost" summary
    # line is correctly excluded, not counted as a 6th transaction.
    assert len(result) == 5

    assert result[0]["date"] == "17/09/2026"
    assert result[0]["amount"] == 40.0
    assert result[0]["trans_type"] == "sent"

    assert result[1]["amount"] == 195.0
    assert result[1]["trans_type"] == "payment"

    assert result[4]["amount"] == 10.0
    assert result[4]["trans_type"] == "airtime"

    # No receipt number or balance in this format — must stay None,
    # not crash or get defaulted to something misleading.
    assert result[0]["receipt_no"] is None
    assert result[0]["balance"] is None