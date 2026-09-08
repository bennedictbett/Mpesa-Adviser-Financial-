"""
Database connection setup.

Defaults to a local SQLite file for development — zero setup, no
external service needed. Set DATABASE_URL to a Postgres connection
string (e.g. on Railway) to switch backends with no code changes,
since SQLAlchemy abstracts the dialect.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./mpesa_advisor.db")

# SQLite needs this flag for use with FastAPI's threaded request
# handling; Postgres doesn't need it and ignores it if passed.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency — yields a DB session, closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables. Call once at startup (see backend/main.py)."""
    from backend.database import models  # noqa: F401 — ensures models are registered
    Base.metadata.create_all(bind=engine)