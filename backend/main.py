"""FastAPI entry point for the new backend/ architecture."""

import logging
import contextlib

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from backend.api.routes import transactions, analytics, agent, budget
from backend.database.connection import init_db
from backend.rate_limit import limiter
from backend.mcp_server import mcp

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")

init_db()


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # The MCP server's session manager must be running for its
    # streamable-http app to handle requests — without this, mounting
    # mcp.streamable_http_app() below raises "Task group is not
    # initialized. Make sure to use run()." on the first request.
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="M-Pesa Financial Advisor — Backend", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(transactions.router)
app.include_router(analytics.router)
app.include_router(agent.router)
app.include_router(budget.router)

# Mounts the MCP server at /mcp — any MCP-compatible client can connect
# via the streamable-http transport at this path.
app.mount("/mcp-server", mcp.streamable_http_app())


@app.get("/health")
def health():
    return {"status": "ok"}