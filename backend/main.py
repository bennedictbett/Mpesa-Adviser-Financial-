"""FastAPI entry point for the new backend/ architecture."""

import logging

from fastapi import FastAPI

from backend.api.routes import transactions, analytics, agent
from backend.database.connection import init_db

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")

# Create tables immediately at import time — don't rely solely on the
# startup event, which can be skipped or reordered under --reload.
init_db()

app = FastAPI(title="M-Pesa Financial Advisor — Backend")

app.include_router(transactions.router)
app.include_router(analytics.router)
app.include_router(agent.router)

@app.get("/health")
def health():
    return {"status": "ok"}