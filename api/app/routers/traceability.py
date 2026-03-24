"""Traceability API: query the idea→spec→function chain at runtime.

Spec: full-traceability-chain
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.middleware.traceability import get_all_traces, get_traces_for_spec, get_traces_for_idea

router = APIRouter()


@router.get("/traceability")
async def list_all_traces(
    limit: int = Query(100, ge=1, le=500),
):
    """List all runtime-traced functions with their spec and idea links."""
    traces = get_all_traces()
    return {
        "total": len(traces),
        "traces": traces[:limit],
    }


@router.get("/traceability/spec/{spec_id}")
async def traces_for_spec(spec_id: str):
    """Find all functions that implement a specific spec."""
    traces = get_traces_for_spec(spec_id)
    return {
        "spec_id": spec_id,
        "count": len(traces),
        "functions": traces,
    }


@router.get("/traceability/idea/{idea_id}")
async def traces_for_idea(idea_id: str):
    """Find all functions that trace back to a specific idea."""
    traces = get_traces_for_idea(idea_id)
    return {
        "idea_id": idea_id,
        "count": len(traces),
        "functions": traces,
    }


@router.get("/traceability/coverage")
async def traceability_coverage():
    """Report traceability coverage: how many functions are traced, which specs/ideas are covered."""
    traces = get_all_traces()
    specs = set(t["spec"] for t in traces if t.get("spec"))
    ideas = set(t["idea"] for t in traces if t.get("idea"))
    return {
        "traced_functions": len(traces),
        "unique_specs": len(specs),
        "unique_ideas": len(ideas),
        "specs": sorted(specs),
        "ideas": sorted(ideas),
    }
