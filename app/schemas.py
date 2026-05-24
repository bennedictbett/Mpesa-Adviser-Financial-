"""
app/schemas.py
--------------
Pydantic request and response models for all FastAPI endpoints.

Responsibilities:
  - Define what data comes IN to each endpoint (request models)
  - Define what data goes OUT of each endpoint (response models)
  - Validate all incoming data automatically
  - Provide clear API documentation via FastAPI's auto-generated docs

Why Pydantic schemas?
  Without schemas, FastAPI accepts anything and returns anything.
  With schemas, FastAPI automatically:
    - Validates every incoming request field (type, length, required)
    - Rejects invalid requests with a clear 422 error before your code runs
    - Generates interactive API docs at /docs showing exact request/response shapes
    - Serialises response dicts into clean JSON automatically

Every endpoint in app/routes.py uses these models.
"""

from pydantic import BaseModel, Field


#  /chat endpoint 

class ChatMessage(BaseModel):
    """
    A single message in the conversation history.
    Used in ChatRequest to pass previous messages for follow-up questions.
    """
    role:    str = Field(..., description="Either 'user' or 'assistant'")
    content: str = Field(..., description="The message text")


class ChatRequest(BaseModel):
    """
    Request body for POST /chat

    The frontend sends this when a user asks a question.
    history is optional — only needed for follow-up questions.
    """
    question: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="The user's question",
        examples=["How much does it cost to send KES 500?"],
    )
    history: list[ChatMessage] = Field(
        default=[],
        description="Previous messages in the conversation for follow-up questions",
    )


class ChatResponse(BaseModel):
    """
    Response body for POST /chat

    Returned after Claude generates a grounded answer.
    """
    answer:      str       = Field(..., description="Claude's grounded answer")
    sources:     list[str] = Field(..., description="Source document filenames cited")
    chunks_used: int       = Field(..., description="Number of chunks retrieved from ChromaDB")
    has_context: bool      = Field(..., description="Whether relevant chunks were found")
    question:    str       = Field(..., description="The original question echoed back")


#  /analyse endpoint

class AnalyseRequest(BaseModel):
    """
    Request body for POST /analyse

    Used when the user asks personal finance questions about
    their uploaded M-Pesa statement.
    """
    question: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Personal finance question about the user's M-Pesa statement",
        examples=["How much did I spend last month?"],
    )
    history: list[ChatMessage] = Field(
        default=[],
        description="Previous messages for follow-up questions",
    )


class AnalyseResponse(BaseModel):
    """
    Response body for POST /analyse

    Same shape as ChatResponse — reused for consistency.
    """
    answer:      str       = Field(..., description="Financial advice based on statement data")
    sources:     list[str] = Field(..., description="Source filenames (user's statement)")
    chunks_used: int       = Field(..., description="Number of statement chunks retrieved")
    has_context: bool      = Field(..., description="Whether statement data was found")
    question:    str       = Field(..., description="The original question echoed back")


#  /upload endpoint 

class UploadResponse(BaseModel):
    """
    Response body for POST /upload

    Returned after a PDF is successfully parsed and ingested into ChromaDB.
    """
    message:      str = Field(..., description="Human-readable confirmation message")
    filename:     str = Field(..., description="Name of the uploaded file")
    chunks_added: int = Field(..., description="Number of chunks added to ChromaDB")


# /health endpoint 

class HealthResponse(BaseModel):
    """
    Response body for GET /health

    Used by Docker and deployment platforms to check if the app is running.
    """
    status:  str = Field(..., description="'ok' if the app is running")
    version: str = Field(..., description="App version from config.yaml")