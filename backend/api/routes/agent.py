"""Chat endpoint for Jarvis — the LLM adviser layer."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.api.routes.transactions import get_session_transactions
from backend.api.routes.budget import get_session_overrides
from backend.agents.jarvis import ask_jarvis
from backend.rate_limit import limiter


router = APIRouter(prefix="/api/v1", tags=["agent"])


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str


@router.post("/{session_id}/ask", response_model=AskResponse)
@limiter.limit("10/minute")
def ask(request: Request, session_id: str, payload: AskRequest, db: Session = Depends(get_db)):
    """
    Rate-limited to 10 requests/minute per client IP. Each request can
    trigger up to MAX_TOOL_ROUNDS (4) real Groq API calls, so this caps
    worst-case cost exposure from a single client rather than leaving
    it open-ended.
    """
    transactions = get_session_transactions(session_id, db)
    overrides = get_session_overrides(session_id, db)
    answer = ask_jarvis(payload.question, transactions, budget_overrides=overrides)
    return {"answer": answer}