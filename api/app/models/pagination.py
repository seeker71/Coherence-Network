from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated list response with metadata."""

    items: list[T] = Field(description="The page of results.")
    total: int = Field(description="Total number of items matching the query.")
    limit: int = Field(description="Maximum items per page.")
    offset: int = Field(description="Number of items skipped.")
