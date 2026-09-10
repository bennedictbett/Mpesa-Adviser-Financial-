"""FastAPI entry point for the new backend/ architecture."""

import logging

from fastapi import FastAPI, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from backend.api.routes import transactions, analytics, agent, budget
from backend.database.connection import init_db
from backend.rate_limit import limiter

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")

init_db()

# Rate limiter keyed by client IP. Each route opts in individually
# via the @limiter.limit(...) decorator — see agent.py.
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="M-Pesa Financial Advisor — Backend")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(transactions.router)
app.include_router(analytics.router)
app.include_router(agent.router)
app.include_router(budget.router)


@app.get("/health")
def health():
    return {"status": "ok"}