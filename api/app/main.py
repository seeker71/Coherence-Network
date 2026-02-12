"""Coherence Network API — FastAPI entry point."""

import logging
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse

try:
    from dotenv import load_dotenv
    _api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(_api_dir, ".env"))
except ImportError:
    pass

_LOG_FMT = "%(asctime)s %(levelname)s %(name)s %(message)s"
logging.basicConfig(level=logging.INFO, format=_LOG_FMT)

# Log Telegram flow to api/logs/telegram.log for diagnostics
_log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(_log_dir, exist_ok=True)

# Env validation: warn if Telegram chat IDs set but token missing
if os.environ.get("TELEGRAM_CHAT_IDS") and not os.environ.get("TELEGRAM_BOT_TOKEN"):
    logging.getLogger(__name__).warning("TELEGRAM_CHAT_IDS set but TELEGRAM_BOT_TOKEN missing — alerts may fail")
_file_handler = logging.FileHandler(os.path.join(_log_dir, "telegram.log"), encoding="utf-8")
_file_handler.setFormatter(logging.Formatter(_LOG_FMT))
_file_handler.setLevel(logging.DEBUG)
logging.getLogger("app.routers.agent").addHandler(_file_handler)
logging.getLogger("app.services.telegram_adapter").addHandler(_file_handler)
from fastapi.middleware.cors import CORSMiddleware

from app.adapters.graph_store import InMemoryGraphStore
from app.routers import agent, health, import_stack, projects

app = FastAPI(
    title="Coherence Network API",
    version="0.1.0",
    description="Open Source Contribution Intelligence",
    docs_url=None,  # we serve /docs ourselves so GET /docs returns 200 (spec 007)
    openapi_url="/openapi.json",
)

_cors_origins = os.environ.get("ALLOWED_ORIGINS", "*")
_origins_list = (
    [o.strip() for o in _cors_origins.split(",") if o.strip()]
    if _cors_origins and _cors_origins.strip() != "*"
    else ["*"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Spec 007: GET /docs returns 200 (OpenAPI UI reachable) — serve at /docs and /docs/
@app.get("/docs", include_in_schema=False)
async def swagger_ui_docs():
    resp = get_swagger_ui_html(openapi_url="/openapi.json", title=f"{app.title} - Swagger UI")
    resp.status_code = 200  # spec 007: GET /docs returns 200
    return resp


@app.get("/docs/", include_in_schema=False)
async def swagger_ui_docs_slash():
    resp = get_swagger_ui_html(openapi_url="/openapi.json", title=f"{app.title} - Swagger UI")
    resp.status_code = 200
    return resp


app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(agent.router, prefix="/api", tags=["agent"])
app.include_router(projects.router, prefix="/api", tags=["projects"])
app.include_router(import_stack.router, prefix="/api", tags=["import"])

# GraphStore: in-memory with optional JSON persistence (spec 019)
_graph_path = os.path.join(_log_dir, "graph_store.json")
app.state.graph_store = InMemoryGraphStore(persist_path=_graph_path)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Return 500 with generic message for unhandled exceptions (spec 009)."""
    if isinstance(exc, HTTPException):
        raise exc
    logging.getLogger(__name__).exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.get("/")
async def root():
    return {
        "name": "Coherence Network API",
        "version": app.version,
        "docs": "/docs",
        "health": "/api/health",
    }
