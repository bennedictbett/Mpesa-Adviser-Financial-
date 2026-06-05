"""
FastAPI application entry point.

Responsibilities:
  - Create the FastAPI app instance
  - Register all routes from app/routes.py
  - Configure CORS so the Streamlit frontend can call the API
  - Add startup and shutdown event handlers
  - Expose the app object for uvicorn to run

Run the API:
  uvicorn app.main:app --reload         (development)
  uvicorn app.main:app --host 0.0.0.0   (production / Docker)
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import router
from src.rag import settings
from src.rag.vectorstore import load_vectorstore

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


# Create FastAPI app 

app = FastAPI(
    title=settings.app.name,
    version=settings.app.version,
    description=settings.app.description,
    docs_url="/docs",       # interactive API docs at /docs
    redoc_url="/redoc",     # alternative docs at /redoc
)


# CORS middleware 
# Allows the Streamlit frontend (running on a different port)
# to make requests to this FastAPI backend without being blocked
# by the browser's same-origin policy.

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://*.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Startup event 
# Runs once when the app starts — before it accepts any requests.
# Pre-loads ChromaDB into memory so the first request is not slow.

@app.on_event("startup")
async def startup():
    logger.info("=" * 50)
    logger.info("Starting %s v%s", settings.app.name, settings.app.version)
    logger.info("=" * 50)

    try:
        load_vectorstore()
        logger.info("ChromaDB loaded successfully — app is ready")
    except RuntimeError:
        logger.warning(
            "ChromaDB not found — run ingestion pipeline first: "
            "python -m src.rag.pipeline"
        )


#  Shutdown event 

@app.on_event("shutdown")
async def shutdown():
    logger.info("%s shutting down", settings.app.name)


# Register routes 

app.include_router(router, prefix="/api/v1")


# Root endpoint 

@app.get("/")
async def root():
    return {
        "app":     settings.app.name,
        "version": settings.app.version,
        "docs":    "/docs",
        "health":  "/api/v1/health",
    }