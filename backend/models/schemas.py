"""Pydantic request/response models for the backend API."""

from pydantic import BaseModel


class ParseTextRequest(BaseModel):
    statement_text: str


class UploadResponse(BaseModel):
    session_id: str
    transaction_count: int
    uncategorised_count: int


class SpendingSummaryResponse(BaseModel):
    month: str
    total_spent: float
    total_received: float
    net: float
    transaction_count: int


class CategoryBreakdownResponse(BaseModel):
    month: str
    breakdown: dict[str, float]


class MonthlyComparisonResponse(BaseModel):
    month_a: str
    month_b: str
    breakdown_a: dict[str, float]
    breakdown_b: dict[str, float]
    deltas: dict[str, float]