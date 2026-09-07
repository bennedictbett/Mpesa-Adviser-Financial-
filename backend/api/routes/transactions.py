"""
Ingestion endpoints: statement PDF or pasted text goes in,
parsed + categorised transactions come out and are held in-memory
for the analytics endpoints to query.

STOPGAP: uses an in-memory dict keyed by session_id instead of a
real database. Fine for local single-user testing only — replace
with backend/database/ once Phase 1's DB layer exists. Data is lost
on server restart and is NOT isolated between concurrent users.
"""

import logging
import uuid

from fastapi import APIRouter, HTTPException, UploadFile, File

from backend.models.schemas import ParseTextRequest, UploadResponse
from src.rag.statement_parser import parse_from_text, parse_from_pdf
from backend.services.transaction_service import categorise_transactions

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["transactions"])

# session_id -> list[transaction dict]
# TODO: replace with backend/database/ once it exists.
_SESSION_STORE: dict[str, list[dict]] = {}


def _ingest(raw_transactions: list[dict]) -> UploadResponse:
    if not raw_transactions:
        raise HTTPException(status_code=422, detail="No transactions could be parsed from the input.")

    categorised = categorise_transactions(raw_transactions, use_llm_fallback=False)

    session_id = str(uuid.uuid4())
    _SESSION_STORE[session_id] = categorised

    uncategorised = sum(1 for t in categorised if t["category"] == "Other")

    return UploadResponse(
        session_id=session_id,
        transaction_count=len(categorised),
        uncategorised_count=uncategorised,
    )


@router.post("/parse-text", response_model=UploadResponse)
def parse_text(payload: ParseTextRequest):
    try:
        raw_transactions = parse_from_text(payload.statement_text)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return _ingest(raw_transactions)


@router.post("/upload", response_model=UploadResponse)
def upload_statement(file: UploadFile = File(...)):
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

    return _ingest(raw_transactions)


def get_session_transactions(session_id: str) -> list[dict]:
    """Used by analytics.py to look up a session's transactions."""
    if session_id not in _SESSION_STORE:
        raise HTTPException(status_code=404, detail=f"Unknown session_id: {session_id}")
    return _SESSION_STORE[session_id]