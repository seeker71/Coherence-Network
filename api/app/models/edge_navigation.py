"""Pydantic envelopes for edge navigation OpenAPI (optional)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EdgeListEnvelope(BaseModel):
    items: list[dict[str, Any]]
    total: int
    limit: int
    offset: int


class RelationshipTypesEnvelope(BaseModel):
    total: int
    items: list[dict[str, Any]] = Field(default_factory=list)
