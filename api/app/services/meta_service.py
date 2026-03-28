"""Metadata self-discovery service.

Introspects the FastAPI app to expose every endpoint as a concept node,
linking routes to specs and ideas via the traceability registry.
"""

from __future__ import annotations

import os
from typing import Any

from app.models.meta import (
    EndpointEdge,
    EndpointNode,
    MetaEndpointsResponse,
    MetaModulesResponse,
    MetaSummaryResponse,
    ModuleNode,
)


def _get_trace_registry() -> list[dict[str, Any]]:
    try:
        from app.middleware.traceability import _TRACE_REGISTRY
        return _TRACE_REGISTRY
    except Exception:
        return []


def _build_trace_index(registry: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Build an index from function qualname to trace entry."""
    index: dict[str, dict[str, Any]] = {}
    for entry in registry:
        fn = entry.get("function", "")
        if fn:
            index[fn] = entry
    return index


def list_endpoints(app: Any) -> MetaEndpointsResponse:
    """Walk FastAPI routes and return each as an EndpointNode concept node."""
    registry = _get_trace_registry()
    trace_index = _build_trace_index(registry)

    nodes: list[EndpointNode] = []

    try:
        routes = app.routes
    except Exception:
        routes = []

    for route in routes:
        # Only include APIRoute instances (not static files, mounts, etc.)
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", None)
        if not methods or not path:
            continue
        # Skip internal/meta-infrastructure paths
        if path in ("/", "/openapi.json", "/docs", "/redoc", "/api/admin/reset-database"):
            continue

        name = getattr(route, "name", "") or ""
        tags = list(getattr(route, "tags", []) or [])
        summary = getattr(route, "summary", None) or getattr(route, "description", None)
        endpoint_fn = getattr(route, "endpoint", None)
        module_name: str | None = None
        if endpoint_fn:
            module_name = getattr(endpoint_fn, "__module__", None)

        for method in sorted(methods):
            node_id = f"{method} {path}"
            edges: list[EndpointEdge] = []
            spec_id: str | None = None
            idea_id: str | None = None

            # Look up trace registry by function qualname
            if endpoint_fn:
                qualname = getattr(endpoint_fn, "__qualname__", "")
                trace = trace_index.get(qualname)
                if trace:
                    spec_id = trace.get("spec")
                    idea_id = trace.get("idea")
                    if not summary:
                        summary = trace.get("description")

            if spec_id:
                edges.append(EndpointEdge(
                    type="implements_spec",
                    target_id=f"spec-{spec_id}",
                    target_label=f"Spec {spec_id}",
                ))
            if idea_id:
                edges.append(EndpointEdge(
                    type="traces_idea",
                    target_id=idea_id,
                    target_label=idea_id,
                ))
            if module_name:
                edges.append(EndpointEdge(
                    type="defined_in_module",
                    target_id=module_name,
                    target_label=module_name.split(".")[-1],
                ))

            nodes.append(EndpointNode(
                id=node_id,
                method=method,
                path=path,
                name=name,
                summary=summary,
                tags=tags,
                spec_id=spec_id,
                idea_id=idea_id,
                module=module_name,
                edges=edges,
            ))

    nodes.sort(key=lambda n: (n.path, n.method))
    return MetaEndpointsResponse(total=len(nodes), endpoints=nodes)


def list_modules(app: Any) -> MetaModulesResponse:
    """Return code modules as concept nodes linked to endpoints, specs, and ideas."""
    registry = _get_trace_registry()

    # Aggregate by module
    module_data: dict[str, dict] = {}

    try:
        routes = app.routes
    except Exception:
        routes = []

    for route in routes:
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", None)
        if not methods or not path:
            continue
        endpoint_fn = getattr(route, "endpoint", None)
        if not endpoint_fn:
            continue
        module_name = getattr(endpoint_fn, "__module__", None)
        if not module_name:
            continue

        if module_name not in module_data:
            module_data[module_name] = {
                "spec_ids": set(),
                "idea_ids": set(),
                "endpoint_count": 0,
            }
        module_data[module_name]["endpoint_count"] += len(methods)

    # Add spec/idea links from trace registry
    for entry in registry:
        mod = entry.get("module", "")
        if mod and mod in module_data:
            if entry.get("spec"):
                module_data[mod]["spec_ids"].add(entry["spec"])
            if entry.get("idea"):
                module_data[mod]["idea_ids"].add(entry["idea"])

    # Also add any traced modules not yet in module_data
    for entry in registry:
        mod = entry.get("module", "")
        if mod and mod not in module_data:
            module_data[mod] = {
                "spec_ids": set(),
                "idea_ids": set(),
                "endpoint_count": 0,
            }
        if mod:
            if entry.get("spec"):
                module_data[mod]["spec_ids"].add(entry["spec"])
            if entry.get("idea"):
                module_data[mod]["idea_ids"].add(entry["idea"])

    nodes: list[ModuleNode] = []
    for mod_name, data in sorted(module_data.items()):
        short_name = mod_name.split(".")[-1]
        # Determine type from module path
        if ".routers." in mod_name or mod_name.endswith(".routers"):
            module_type = "router"
        elif ".services." in mod_name or mod_name.endswith(".services"):
            module_type = "service"
        elif ".models." in mod_name or mod_name.endswith(".models"):
            module_type = "model"
        elif ".middleware." in mod_name:
            module_type = "middleware"
        else:
            module_type = "module"

        spec_ids = sorted(data["spec_ids"])
        idea_ids = sorted(data["idea_ids"])

        edges: list[EndpointEdge] = []
        for sid in spec_ids:
            edges.append(EndpointEdge(type="implements_spec", target_id=f"spec-{sid}", target_label=f"Spec {sid}"))
        for iid in idea_ids:
            edges.append(EndpointEdge(type="traces_idea", target_id=iid, target_label=iid))

        # Approximate file path from module dotted name
        file_path = mod_name.replace(".", "/") + ".py"

        nodes.append(ModuleNode(
            id=mod_name,
            name=short_name,
            module_type=module_type,
            file_path=file_path,
            spec_ids=spec_ids,
            idea_ids=idea_ids,
            endpoint_count=data["endpoint_count"],
            edges=edges,
        ))

    return MetaModulesResponse(total=len(nodes), modules=nodes)


def get_summary(app: Any) -> MetaSummaryResponse:
    """Return a brief overview of system self-description coverage."""
    ep_response = list_endpoints(app)
    mod_response = list_modules(app)

    traced = sum(
        1 for ep in ep_response.endpoints
        if ep.spec_id or ep.idea_id
    )
    total = ep_response.total
    coverage = (traced / total) if total > 0 else 0.0

    return MetaSummaryResponse(
        endpoint_count=total,
        module_count=mod_response.total,
        traced_count=traced,
        spec_coverage=round(coverage, 4),
    )
