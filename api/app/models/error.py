"""Error response schema for 400, 404, 500 (spec 009). 422 uses FastAPI default; do not override."""

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """Simple error response: single top-level field detail (string). No extra keys."""

    detail: str
