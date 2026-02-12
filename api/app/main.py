"""Coherence Network API — FastAPI entry point."""

import logging
import os

from fastapi import FastAPI

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
_file_handler = logging.FileHandler(os.path.join(_log_dir, "telegram.log"), encoding="utf-8")
_file_handler.setFormatter(logging.Formatter(_LOG_FMT))
_file_handler.setLevel(logging.DEBUG)
logging.getLogger("app.routers.agent").addHandler(_file_handler)
logging.getLogger("app.services.telegram_adapter").addHandler(_file_handler)
from fastapi.middleware.cors import CORSMiddleware

from app.routers import agent, health

app = FastAPI(
    title="Coherence Network API",
    version="0.1.0",
    description="Open Source Contribution Intelligence",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(agent.router, prefix="/api", tags=["agent"])


@app.get("/")
async def root():
    return {"message": "Coherence Network API", "docs": "/docs"}
