"""Graph self-balance API — fractal equilibrium signals (Spec 170)."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.models.graph_balance import GraphBalanceReport
from app.services import graph_balance_service

router = APIRouter()


@router.get("/graph/balance", response_model=GraphBalanceReport)
async def get_graph_balance(
    max_children: int = Query(
        10,
        ge=5,
        le=100,
        description="Fan-out threshold on outgoing parent-of edges before split signal",
    ),
    concentration_threshold: float = Query(
        0.8,
        ge=0.5,
        le=1.0,
        description="Top-3 energy share at or above this triggers concentration alert",
    ),
) -> GraphBalanceReport:
    """Return split signals, orphan merge clusters, and idea energy entropy."""
    return graph_balance_service.compute_balance_report(
        max_children=max_children,
        concentration_threshold=concentration_threshold,
    )
