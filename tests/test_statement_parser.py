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