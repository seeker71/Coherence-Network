from __future__ import annotations

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    detail: str
