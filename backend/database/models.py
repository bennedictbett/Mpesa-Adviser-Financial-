"""
SQLAlchemy models.

Transaction rows are grouped by session_id, matching the current
API design (backend/api/routes/transactions.py) where a statement
upload creates one session. There's no user/auth system yet — once
one exists, add a user_id column and scope queries by it instead of
(or alongside) session_id.
"""

from sqlalchemy import Column, Integer, String, Float, DateTime
from backend.database.connection import Base


class TransactionRecord(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True, nullable=False)

    receipt_no = Column(String)
    date = Column(String)          # original "DD/MM/YYYY" string, kept as-is
    time = Column(String)
    details = Column(String)
    recipient = Column(String)
    amount = Column(Float, nullable=False)
    trans_type = Column(String, nullable=False)
    balance = Column(Float)
    category = Column(String, nullable=False)
    parsed_date = Column(DateTime, nullable=True)  # None if unparseable

    def to_dict(self) -> dict:
        """Converts back to the plain-dict schema analytics_service.py expects."""
        return {
            "receipt_no": self.receipt_no,
            "date": self.date,
            "time": self.time,
            "details": self.details,
            "recipient": self.recipient,
            "amount": self.amount,
            "trans_type": self.trans_type,
            "balance": self.balance,
            "category": self.category,
            "parsed_date": self.parsed_date,
        }