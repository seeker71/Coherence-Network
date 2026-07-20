"""Shared scaffolding for the transmuted kernel-served /api/utils endpoints.

The endpoint bodies live as Form recipes, not Python functions (see the
``kernel_*`` sibling modules). This module holds what every family shares:
the single ``/utils`` ``APIRouter`` the families decorate, the module logger,
and the query/result coercion helpers. Splitting the endpoints across focused
modules keeps each one small; sharing one router object keeps every route at
its exact ``/api/utils/...`` path with a single ``include_router`` call in
``app.main``.

Each endpoint executes on c-bootstrapped fkwu through ``serve_via_kernel``.
CPython, Go, Rust, and TypeScript remain differential references for the same
primitive/native assumptions; they are not runtime fallbacks.
"""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.services.form_kernel_bridge import (
    active_runtime,
    kernel_available,
    kernel_bin_path,
    serve_via_kernel,
)

__all__ = [
    "Annotated",
    "APIRouter",
    "BaseModel",
    "ConfigDict",
    "Field",
    "HTTPException",
    "Query",
    "active_runtime",
    "kernel_available",
    "kernel_bin_path",
    "logger",
    "router",
    "serve_via_kernel",
    "_coerce_float_list",
    "_parse_floats",
    "_parse_values",
]

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/utils", tags=["utils"])


def _parse_values(values: str) -> list[int]:
    """Parse the comma-separated query param into a list of ints."""
    if not values.strip():
        return []
    out: list[int] = []
    for part in values.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"invalid integer in values: {part!r}",
            ) from e
    return out


def _parse_floats(raw: str, label: str) -> list[float]:
    """Parse a comma-separated string of floats; HTTPException on bad input."""
    if not raw.strip():
        return []
    out: list[float] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(float(part))
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"invalid float in {label}: {part!r}",
            ) from e
    return out


def _coerce_float_list(value: object) -> list[float]:
    """Coerce a kernel result into a list[float].

    Direct fkwu hands back the kernel's display string, e.g.
    ``[0.09003057317038046, 0.24472847105479764, 0.6652409557748218]``. One
    coercion preserves the numeric list at the HTTP membrane.
    """
    if isinstance(value, (list, tuple)):
        return [float(v) for v in value]
    s = str(value).strip()
    if s in ("", "[]", "(list)"):
        return []
    s = s.strip("[]() ")
    if not s:
        return []
    # Comma- or space-separated floats; `(list a b c)` collapses to space-sep.
    sep = "," if "," in s else None
    parts = s.split(sep) if sep else s.split()
    return [float(p.strip().rstrip(",")) for p in parts if p.strip().rstrip(",")]


def _coerce_int_list(value: object) -> list[int]:
    """Coerce a kernel result into a list[int].

    Direct fkwu hands back the kernel's display string, e.g. ``[3, 10, 2,
    7]``. One coercion serves both kernel carriers so the route reads
    ``runtime`` honestly regardless of path.
    """
    if isinstance(value, (list, tuple)):
        return [int(v) for v in value]
    s = str(value).strip()
    if s in ("", "[]", "(list)"):
        return []
    s = s.strip("[]() ")
    if not s:
        return []
    sep = "," if "," in s else None
    parts = s.split(sep) if sep else s.split()
    return [int(float(p.strip().rstrip(","))) for p in parts if p.strip().rstrip(",")]
