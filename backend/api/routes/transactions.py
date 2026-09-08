"""
Ingestion endpoints: statement PDF or pasted text goes in,
parsed + categorised transactions come out and are persisted to
the database, grouped by session_id.
"""

import logging
import uuid

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from sqlalchemy.orm import Session

from backend.models.schemas import ParseTextRequest, UploadResponse
from src.rag.statement_parser import parse_from_text, parse_from_pdf
from backend.services.transaction_service import categorise_transactions
from backend.database.connection import get_db
from backend.database.models import TransactionRecord

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["transactions"])


def _ingest(raw_transactions: list[dict], db: Session) -> UploadResponse:
    if not raw_transactions:
        raise HTTPException(status_code=422, detail="No transactions could be parsed from the input.")

    categorised = categorise_transactions(raw_transactions, use_llm_fallback=False)

    session_id = str(uuid.uuid4())

    for txn in categorised:
        record = TransactionRecord(session_id=session_id, **{
            k: v for k, v in txn.items()
            if k in TransactionRecord.__table__.columns.keys()
        })
        db.add(record)

    db.commit()

    uncategorised = sum(1 for t in categorised if t["category"] == "Other")

    return UploadResponse(
        session_id=session_id,
        transaction_count=len(categorised),
        uncategorised_count=uncategorised,
    )


@router.post("/parse-text", response_model=UploadResponse)
def parse_text(payload: ParseTextRequest, db: Session = Depends(get_db)):
    try:
        raw_transactions = parse_from_text(payload.statement_text)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return _ingest(raw_transactions, db)


@router.post("/upload", response_model=UploadResponse)
def upload_statement(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Only PDF files are supported.")

    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(file.file.read())
        tmp_path = Path(tmp.name)

    try:
        raw_transactions = parse_from_pdf(tmp_path)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=422, detail=str(e))
    finally:
        tmp_path.unlink(missing_ok=True)

    return _ingest(raw_transactions, db)


def get_session_transactions(session_id: str, db: Session) -> list[dict]:
    """Used by analytics.py to look up a session's transactions."""
    records = db.query(TransactionRecord).filter(TransactionRecord.session_id == session_id).all()
    if not records:
        raise HTTPException(status_code=404, detail=f"Unknown session_id: {session_id}")
    return [r.to_dict() for r in records]