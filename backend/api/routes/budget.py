"""Set or update a user's budget override for a category."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.database.models import BudgetOverride

router = APIRouter(prefix="/api/v1", tags=["budget"])


class SetBudgetRequest(BaseModel):
    category: str
    amount: float


class SetBudgetResponse(BaseModel):
    category: str
    amount: float


@router.post("/{session_id}/budget", response_model=SetBudgetResponse)
def set_budget(session_id: str, payload: SetBudgetRequest, db: Session = Depends(get_db)):
    existing = (
        db.query(BudgetOverride)
        .filter(BudgetOverride.session_id == session_id, BudgetOverride.category == payload.category)
        .first()
    )

    if existing:
        existing.amount = payload.amount
    else:
        db.add(BudgetOverride(session_id=session_id, category=payload.category, amount=payload.amount))

    db.commit()

    return {"category": payload.category, "amount": payload.amount}


def get_session_overrides(session_id: str, db: Session) -> dict[str, float]:
    """Used by agent.py to build the tool dispatcher's overrides."""
    records = db.query(BudgetOverride).filter(BudgetOverride.session_id == session_id).all()
    return {r.category: r.amount for r in records}