"""Chat endpoint for Jarvis — the LLM adviser layer."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.api.routes.transactions import get_session_transactions
from backend.agents.jarvis import ask_jarvis

router = APIRouter(prefix="/api/v1", tags=["agent"])


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str


@router.post("/{session_id}/ask", response_model=AskResponse)
def ask(session_id: str, payload: AskRequest, db: Session = Depends(get_db)):
    transactions = get_session_transactions(session_id, db)
    answer = ask_jarvis(payload.question, transactions)
    return {"answer": answer}