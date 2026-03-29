# spec: 183-full-traceability-chain
# idea: full-traceability-chain
"""Traceability API: query and backfill the idea->spec->function chain (Spec 183).

Endpoints:
  GET  /traceability                    -> all runtime-traced functions
  GET  /traceability/coverage           -> coverage summary
  GET  /traceability/spec/{spec_id}     -> forward trace to files and functions
  GET  /traceability/idea/{idea_id}     -> functions tracing to an idea
  GET  /traceability/report             -> full traceability report
  GET  /traceability/functions          -> @spec_traced function registry
  GET  /traceability/lineage/{idea_id}  -> full lineage chain
  POST /traceability/backfill           -> trigger background backfill job
  GET  /traceability/backfill/status    -> check backfill job status
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.middleware.traceability import get_all_traces, get_traces_for_spec, get_traces_for_idea
from app.models.traceability import BackfillRequest
from app.services.traceability_service import (
    build_traceability_report,
    get_backfill_status,
    get_function_list,
    get_lineage,
    get_spec_forward_trace,
    start_backfill_job,
)

router = APIRouter()


@router.get("/traceability")
async def list_all_traces(limit: int = Query(100, ge=1, le=500)):
    """List all runtime-traced functions with their spec and idea links."""
    traces = get_all_traces()
    return {"total": len(traces), "traces": traces[:limit]}


@router.get("/traceability/coverage")
async def traceability_coverage():
    """Coverage summary from @traces_to decorator registry."""
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


@router.get("/traceability/report")
async def traceability_report():
    """Return current traceability state across all dimensions."""
    return build_traceability_report().model_dump()


@router.post("/traceability/backfill", status_code=202)
async def trigger_backfill(body: BackfillRequest = BackfillRequest()):
    """Trigger background backfill. Returns 202. Returns 409 if already running."""
    try:
        return start_backfill_job(dry_run=body.dry_run).model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/traceability/backfill/status")
async def backfill_status():
    """Check the status of the most recent backfill job."""
    status = get_backfill_status()
    if status is None:
        return {"status": "no_job", "message": "No backfill job has been run yet."}
    return status


@router.get("/traceability/functions")
async def function_registry(
    spec_id: str | None = Query(None, description="Filter by spec ID"),
    idea_id: str | None = Query(None, description="Filter by idea ID"),
):
    """Return all functions annotated with @spec_traced, with coverage stats."""
    return get_function_list(spec_id=spec_id, idea_id=idea_id).model_dump()


@router.get("/traceability/lineage/{idea_id}")
async def idea_lineage(idea_id: str):
    """Return the complete lineage chain from an idea to its specs, files, and functions."""
    lineage = get_lineage(idea_id)
    if lineage is None:
        raise HTTPException(status_code=404, detail="Idea not found")
    return lineage.model_dump()


@router.get("/traceability/spec/{spec_id}")
async def spec_forward_trace(spec_id: str):
    """Return all files and functions that implement a given spec."""
    trace = get_spec_forward_trace(spec_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Spec not found")
    return trace.model_dump()


@router.get("/traceability/idea/{idea_id}")
async def traces_for_idea_endpoint(idea_id: str):
    """Find @traces_to-decorated functions tracing to a specific idea."""
    traces = get_traces_for_idea(idea_id)
    return {"idea_id": idea_id, "count": len(traces), "functions": traces}
