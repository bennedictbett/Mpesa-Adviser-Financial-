"""FastAPI entry point for the new backend/ architecture."""

import logging

from fastapi import FastAPI

from backend.api.routes import transactions, analytics

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")

app = FastAPI(title="M-Pesa Financial Advisor — Backend")

app.include_router(transactions.router)
app.include_router(analytics.router)


@app.get("/health")
def health():
    return {"status": "ok"}