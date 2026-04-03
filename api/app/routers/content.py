"""Content router — direct file access for index-oriented memory."""

from __future__ import annotations

import os
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse

router = APIRouter()

# Strict allowlist for file access to prevent path traversal
ALLOWED_ROOTS = ["specs", "docs", "cli/lib/commands", "api/app/services", "skills"]
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

@router.get(
    "/content/file",
    response_class=PlainTextResponse,
    summary="Read raw file content from the repository",
)
def read_repo_file(path: str = Query(..., description="Relative path from repo root")) -> str:
    """Return the raw text content of a file if it is in the allowlist."""
    # 1. Security Check: Block traversal
    if ".." in path or path.startswith("/") or path.startswith("~"):
        raise HTTPException(status_code=403, detail="Illegal path traversal attempt")

    # 2. Security Check: Allowlist
    is_allowed = any(path.startswith(root) for root in ALLOWED_ROOTS)
    if not is_allowed:
        raise HTTPException(status_code=403, detail=f"Path '{path}' is not in the content allowlist")

    full_path = os.path.join(REPO_ROOT, path)
    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    try:
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
