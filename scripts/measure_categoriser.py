"""
One-off diagnostic: measures the real 'Other' percentage of the
hybrid categoriser against a realistic messy M-Pesa statement, and
lists exactly which transactions fell through — so the keyword list
in transaction_service.py can be expanded based on real gaps, not
guesses.

Run with: python scripts/measure_categoriser.py
"""

from src.rag.statement_parser import parse_statement_text
from backend.services.transaction_service import categorise_transactions

# A deliberately messy statement mixing:
#  - known chains (should categorise cleanly)
#  - Paybill/Till numbers with no business name (the real weak point)
#  - phone-number-only recipients (person-to-person, no way to guess category)
#  - small/local vendors unlikely to be in any keyword list
#  - standard M-Pesa mechanism lines (airtime, withdraw, charges)
MESSY_STATEMENT = """
RJK81ABCD1 01/08/2026 08:15 Customer Transfer to NAIVAS SUPERMARKET -850.00 45000.00
RJK81ABCD2 01/08/2026 09:02 Pay Bill to 522533 - KPLC PREPAID -1200.00 43800.00
RJK81ABCD3 02/08/2026 07:45 Customer Transfer to 0722334455 -500.00 43300.00
RJK81ABCD4 02/08/2026 12:30 Pay Bill to 888880 - Mama Njeri Groceries -350.00 42950.00
RJK81ABCD5 03/08/2026 18:00 Buy Goods to UBER TRIP -420.00 42530.00
RJK81ABCD6 04/08/2026 06:10 Withdraw Cash at AGENT 55201 -2000.00 40530.00
RJK81ABCD7 04/08/2026 14:22 Airtime Purchase -100.00 40430.00
RJK81ABCD8 05/08/2026 19:05 Pay Bill to 247247 - DSTV KENYA -3000.00 37430.00
RJK81ABCD9 06/08/2026 09:00 Customer Transfer to JOHN KAMAU 0733221100 -1500.00 35930.00
RJK81ABDA0 07/08/2026 13:15 Buy Goods to KIOSK CHEZA 220011 -150.00 35780.00
RJK81ABDA1 08/08/2026 10:40 Pay Bill to 400200 - EQUITY BANK LOAN -5000.00 30780.00
RJK81ABDA2 09/08/2026 16:20 Customer Transfer to MARY WANJIRU -800.00 29980.00
RJK81ABDA3 10/08/2026 11:11 Buy Goods to CARWASH JUNCTION -300.00 29680.00
RJK81ABDA4 11/08/2026 08:30 Pay Bill to 700100 - NAIROBI WATER -600.00 29080.00
RJK81ABDA5 12/08/2026 20:00 M-PESA Charge -22.00 29058.00
RJK81ABDA6 13/08/2026 15:45 Customer Transfer to 0711998877 -2500.00 26558.00
RJK81ABDA7 14/08/2026 07:00 Buy Goods to JAVA HOUSE -680.00 25878.00
RJK81ABDA8 15/08/2026 12:00 Pay Bill to 999111 - CHURCH OFFERING -1000.00 24878.00
RJK81ABDA9 16/08/2026 09:30 Buy Goods to KINYOZI STYLE CUTS -200.00 24678.00
RJK81ABEA0 17/08/2026 18:45 Customer Transfer to PETER OTIENO -1200.00 23478.00
""".strip()


def main():
    transactions = parse_statement_text(MESSY_STATEMENT)
    print(f"Parsed {len(transactions)} transactions from {MESSY_STATEMENT.count(chr(10)) + 1} lines\n")

    categorised = categorise_transactions(transactions, use_llm_fallback=False)

    other = [t for t in categorised if t["category"] == "Other"]
    other_pct = 100 * len(other) / len(categorised) if categorised else 0

    print(f"Total: {len(categorised)} | Other: {len(other)} ({other_pct:.1f}%)\n")
    print("Transactions that fell through to 'Other':")
    print("-" * 70)
    for t in other:
        print(f"  recipient={t['recipient']!r:35} trans_type={t['trans_type']:10} details={t['details'][:60]}")


if __name__ == "__main__":
    main()