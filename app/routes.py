"""
FastAPI route handlers for all API endpoints.

Endpoints:
  POST /chat      → general M-Pesa and CBK regulation questions
  POST /analyse   → personal finance analysis from uploaded M-Pesa statement
  POST /upload    → upload a PDF and ingest it into ChromaDB
  GET  /health    → app health check for Docker and deployment platforms

Responsibilities:
  - Receive validated requests (schemas.py handles validation)
  - Call the appropriate function from src/rag/
  - Return structured responses (schemas.py handles serialisation)
  - Handle errors gracefully with meaningful HTTP status codes

Routes stay thin — no business logic lives here.
All RAG logic lives in src/rag/chain.py and src/rag/pipeline.py.
"""

import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.dependencies import check_app_ready, verify_api_keys
from app.schemas import (
    AnalyseRequest,
    AnalyseResponse,
    ChatRequest,
    ChatResponse,
    HealthResponse,
    UploadResponse,
)
from src.rag import settings
from src.rag.chain import analyse_statement, ask
from src.rag.loader import load_single_document
from src.rag.splitter import split_single_document
from src.rag.vectorstore import add_chunks
from src.rag.prompts import UPLOAD_CONFIRMATION

logger = logging.getLogger(__name__)

router = APIRouter()


# POST /chat

@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Ask a question about M-Pesa or CBK regulations",
    description=(
        "Send a question and get a grounded answer cited from official "
        "Safaricom and CBK documents. Pass conversation history for follow-up questions."
    ),
)
async def chat(
    request: ChatRequest,
    _: None = Depends(check_app_ready),
):
    """
    Answer a general M-Pesa or CBK regulation question.

    Retrieves relevant chunks from ChromaDB and passes them to Claude
    to generate a cited, grounded answer. If no relevant chunks are
    found the response explains this clearly rather than guessing.
    """
    logger.info("POST /chat — question: '%s'", request.question[:80])

    try:
        # Convert ChatMessage objects to plain dicts for chain.py
        history = [
            {"role": msg.role, "content": msg.content}
            for msg in request.history
        ]

        result = ask(question=request.question, history=history)
        return ChatResponse(**result)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error("Error in /chat: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing your question. Please try again.",
        )


# POST /analyse 

@router.post(
    "/analyse",
    response_model=AnalyseResponse,
    summary="Analyse your M-Pesa statement and get financial advice",
    description=(
        "Ask personal finance questions about your uploaded M-Pesa statement. "
        "Get spending analysis, budgeting advice, and financial insights "
        "grounded in your actual transaction data."
    ),
)
async def analyse(
    request: AnalyseRequest,
    _: None = Depends(check_app_ready),
):
    """
    Analyse an uploaded M-Pesa statement and give financial advice.

    Uses the same RAG pipeline as /chat but enriches the question
    with financial analysis framing so Claude gives advisory responses
    with spending breakdowns and budgeting suggestions.

    Example questions:
      - "How much did I spend last month?"
      - "What do I spend most of my money on?"
      - "How can I save KES 5,000 this month?"
      - "Am I spending more than I earn?"
    """
    logger.info("POST /analyse — question: '%s'", request.question[:80])

    try:
        history = [
            {"role": msg.role, "content": msg.content}
            for msg in request.history
        ]

        result = analyse_statement(
            question=request.question,
            history=history,
        )
        return AnalyseResponse(**result)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error("Error in /analyse: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while analysing your statement. Please try again.",
        )


# POST /upload 

@router.post(
    "/upload",
    response_model=UploadResponse,
    summary="Upload a PDF and add it to the knowledge base",
    description=(
        "Upload an M-Pesa statement or any other PDF. The file is parsed, "
        "chunked, embedded, and added to ChromaDB instantly. You can then "
        "ask questions about it via /chat or /analyse."
    ),
)
async def upload(
    file: UploadFile = File(...),
    _: None = Depends(verify_api_keys),
):
    """
    Upload a PDF file and ingest it into ChromaDB.

    Handles the full ingestion flow for a single uploaded file:
      1. Validate file type and size
      2. Save to a temp file on disk
      3. Parse text via loader.load_single_document()
      4. Chunk via splitter.split_single_document()
      5. Embed and store via vectorstore.add_chunks()
      6. Return confirmation with chunk count

    The uploaded file is available for querying immediately after upload.
    """
    logger.info("POST /upload — filename: '%s'", file.filename)

    # Validate file type 
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported. Please upload a .pdf file.",
        )

    # Validate file size 
    max_bytes = settings.frontend.max_upload_size_mb * 1024 * 1024
    contents  = await file.read()

    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"File too large. Maximum size is "
                f"{settings.frontend.max_upload_size_mb}MB."
            ),
        )

    # Save to temp file and ingest 
    try:
        with tempfile.NamedTemporaryFile(
            suffix=".pdf",
            delete=False,
        ) as tmp:
            tmp.write(contents)
            tmp_path = Path(tmp.name)

        # Load + parse
        document = load_single_document(tmp_path)

        # Override source name with original filename
        document["source"] = file.filename

        # Chunk
        chunks = split_single_document(document)

        # Embed + store
        chunks_added = add_chunks(chunks)

        # Clean up temp file
        tmp_path.unlink(missing_ok=True)

        confirmation = UPLOAD_CONFIRMATION.format(
            filename=file.filename,
            chunk_count=chunks_added,
        )

        logger.info(
            "Upload complete — '%s' | %d chunks added",
            file.filename,
            chunks_added,
        )

        return UploadResponse(
            message=confirmation,
            filename=file.filename,
            chunks_added=chunks_added,
        )

    except ValueError as e:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        tmp_path.unlink(missing_ok=True)
        logger.error("Error in /upload: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing your file. Please try again.",
        )


# GET /health 

@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns 200 OK if the app is running. Used by Docker and deployment platforms.",
)
async def health():
    """
    Health check endpoint.

    Returns immediately with status ok and the app version.
    Docker and deployment platforms (Render, Railway) call this
    to verify the container is alive.
    """
    return HealthResponse(
        status="ok",
        version=settings.app.version,
    )