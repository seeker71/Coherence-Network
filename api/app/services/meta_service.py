"""Metadata self-discovery service.

Introspects the FastAPI app to expose every endpoint as a concept node,
linking routes to specs and ideas via the traceability registry.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional

from app.models.meta import (
    MetaEndpointNode,
    MetaEndpointsResponse,
    MetaModuleNode,
    MetaModulesResponse,
    MetaSummaryResponse,
    MetaTraceResult,
)
from app.services import runtime_service


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


def _get_path_hash(method: str, path: str) -> str:
    return hashlib.sha1(f"{method}:{path}".encode("utf-8")).hexdigest()


def _get_git_contributors(file_path: str) -> list[str]:
    """Get unique contributors for a file using git log."""
    try:
        # Run git log to get author names
        cmd = ["git", "log", "--follow", "--format=%an", "--", file_path]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            return []
        authors = result.stdout.strip().split("\n")
        # Filter out empty strings and return unique names
        return sorted(list(set(a.strip() for a in authors if a.strip())))
    except Exception:
        return []


def list_endpoints(app: Any) -> MetaEndpointsResponse:
    """Walk FastAPI routes and return each as a MetaEndpointNode."""
    registry = _get_trace_registry()
    trace_index = _build_trace_index(registry)
    
    # Get runtime stats for the last 30 days
    try:
        runtime_stats = runtime_service.summarize_by_endpoint(seconds=30 * 24 * 3600)
        stats_map = {s.endpoint: s for s in runtime_stats}
    except Exception:
        stats_map = {}

    nodes: list[MetaEndpointNode] = []

    try:
        routes = app.routes
    except Exception:
        routes = []

    for route in routes:
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", None)
        if not methods or not path:
            continue
            
        # Skip internal/meta-infrastructure paths unless they have tags
        tags = list(getattr(route, "tags", []) or [])
        if not tags and path in ("/", "/openapi.json", "/docs", "/redoc", "/api/admin/reset-database"):
            continue

        summary = getattr(route, "summary", None) or getattr(route, "description", "")
        endpoint_fn = getattr(route, "endpoint", None)
        
        # Get stats for this endpoint
        stats = stats_map.get(path)
        call_count = stats.event_count if stats else 0
        # last_called_at would need more detailed stats or a separate query
        # For Phase 1, we'll leave it as None or try to get it from events
        
        for method in sorted(methods):
            spec_ids = []
            idea_ids = []
            contributors = []
            
            # Look up trace registry
            if endpoint_fn:
                qualname = getattr(endpoint_fn, "__qualname__", "")
                trace = trace_index.get(qualname)
                if trace:
                    if trace.get("spec"):
                        spec_ids.append(trace["spec"])
                    if trace.get("idea"):
                        idea_ids.append(trace["idea"])
                    if not summary:
                        summary = trace.get("description") or ""

            # Try to get contributors from module if possible
            module_name = getattr(endpoint_fn, "__module__", None)
            if module_name:
                # Approximate file path
                file_path = module_name.replace(".", "/") + ".py"
                if os.path.exists(file_path):
                    contributors = _get_git_contributors(file_path)

            nodes.append(MetaEndpointNode(
                path=path,
                method=method,
                path_hash=_get_path_hash(method, path),
                tag=tags[0] if tags else "default",
                summary=summary,
                spec_ids=spec_ids,
                idea_ids=idea_ids,
                contributors=contributors,
                call_count_30d=call_count,
                last_called_at=None,
                status="active"
            ))

    nodes.sort(key=lambda n: (n.path, n.method))
    return MetaEndpointsResponse(
        total=len(nodes), 
        endpoints=nodes,
        generated_at=datetime.now(timezone.utc)
    )


def get_endpoint_by_hash(app: Any, path_hash: str) -> Optional[MetaEndpointNode]:
    """Find a single endpoint by its SHA-1 hash."""
    all_eps = list_endpoints(app)
    for ep in all_eps.endpoints:
        if ep.path_hash == path_hash:
            return ep
    return None


def _get_module_type(path: Path) -> Literal["api_router", "service", "model", "adapter", "web_page", "web_component", "middleware", "other"]:
    p_str = str(path)
    if "routers" in p_str:
        return "api_router"
    if "services" in p_str:
        return "service"
    if "models" in p_str:
        return "model"
    if "adapters" in p_str:
        return "adapter"
    if "middleware" in p_str:
        return "middleware"
    if p_str.endswith(".tsx") or p_str.endswith(".jsx"):
        if "components" in p_str:
            return "web_component"
        return "web_page"
    return "other"


def list_modules(app: Any) -> MetaModulesResponse:
    """Walk the filesystem to discover code modules and their metadata."""
    modules: list[MetaModuleNode] = []
    
    # Define directories to scan
    base_dirs = [
        Path("api/app"),
        Path("web/app"),
        Path("web/components")
    ]
    
    # Trace registry for spec/idea links in Python code
    registry = _get_trace_registry()
    mod_to_specs: dict[str, set[str]] = {}
    mod_to_ideas: dict[str, set[str]] = {}
    for entry in registry:
        mod = entry.get("module", "")
        if mod:
            if entry.get("spec"):
                mod_to_specs.setdefault(mod, set()).add(entry["spec"])
            if entry.get("idea"):
                mod_to_ideas.setdefault(mod, set()).add(entry["idea"])

    for base_dir in base_dirs:
        if not base_dir.exists():
            continue
            
        for path in base_dir.rglob("*"):
            if path.is_dir() or path.suffix not in (".py", ".tsx", ".ts", ".jsx", ".js"):
                continue
                
            if "__pycache__" in str(path) or "__init__.py" in str(path):
                continue

            rel_path = str(path)
            name = path.stem
            if path.suffix == ".py":
                # Convert path to module name
                parts = path.with_suffix("").parts
                if "api" in parts:
                    idx = parts.index("api")
                    name = ".".join(parts[idx+1:])
            
            # Metadata
            stat = path.stat()
            last_modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            
            # Line count and Spec links from comments
            line_count = 0
            spec_ids = set()
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line_count += 1
                        # Look for "Implements: spec-XXX" or "traces_to(spec='XXX')"
                        if "Implements:" in line or "traces_to" in line:
                            import re
                            # Match spec-123 or spec="123"
                            matches = re.findall(r"spec[-=:\s\"']+([a-zA-Z0-9_-]+)", line)
                            for m in matches:
                                spec_ids.add(m)
            except Exception:
                pass
            
            # Merge with registry links
            if name in mod_to_specs:
                spec_ids.update(mod_to_specs[name])
            
            idea_ids = mod_to_ideas.get(name, set())
            
            # Contributors
            contributors = _get_git_contributors(rel_path)
            
            # Test file?
            test_file = None
            if path.suffix == ".py":
                t_path = Path("api/tests") / f"test_{path.name}"
                if t_path.exists():
                    test_file = str(t_path)
            
            modules.append(MetaModuleNode(
                name=name,
                path=rel_path,
                type=_get_module_type(path),
                spec_ids=sorted(list(spec_ids)),
                idea_ids=sorted(list(idea_ids)),
                contributors=contributors,
                line_count=line_count,
                last_modified=last_modified,
                test_file=test_file
            ))

    modules.sort(key=lambda m: m.path)
    return MetaModulesResponse(
        total=len(modules),
        modules=modules,
        generated_at=datetime.now(timezone.utc)
    )


def get_summary(app: Any) -> MetaSummaryResponse:
    """Return a brief overview of system self-description coverage."""
    ep_response = list_endpoints(app)
    mod_response = list_modules(app)

    with_spec = sum(1 for ep in ep_response.endpoints if ep.spec_ids)
    without_spec = ep_response.total - with_spec
    
    with_tests = sum(1 for m in mod_response.modules if m.test_file)
    without_tests = mod_response.total - with_tests

    total = ep_response.total
    score = (with_spec / total) if total > 0 else 0.0

    # Version from git
    try:
        version = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
        version = f"main@{version}"
    except Exception:
        version = "unknown"

    return MetaSummaryResponse(
        system="Coherence Network",
        version=version,
        generated_at=datetime.now(timezone.utc),
        counts={
            "endpoints": total,
            "modules": mod_response.total,
            "specs_linked": len(set(sid for ep in ep_response.endpoints for sid in ep.spec_ids)),
            "ideas_traced": len(set(iid for ep in ep_response.endpoints for iid in ep.idea_ids))
        },
        traceability_score=round(score, 4),
        coverage={
            "endpoints_with_spec": with_spec,
            "endpoints_without_spec": without_spec,
            "modules_with_tests": with_tests,
            "modules_without_tests": without_tests
        }
    )


def trace_id(app: Any, entity_id: str) -> MetaTraceResult:
    """Trace an idea or spec to all its produced artifacts."""
    # This requires looking up the spec/idea title from their respective services
    # and searching through all endpoints and modules.
    
    # Try spec first
    from app.services import spec_registry_service, idea_service
    
    entity_type: Literal["spec", "idea"] = "spec"
    title = "Unknown"
    
    spec = None
    try:
        spec = spec_registry_service.get_spec(entity_id)
        if spec:
            entity_type = "spec"
            title = spec.get("title", "Unknown Spec")
    except Exception:
        pass
        
    if not spec:
        try:
            idea = idea_service.get_idea(entity_id)
            if idea:
                entity_type = "idea"
                title = idea.title
        except Exception:
            pass
            
    if title == "Unknown":
        # Final attempt: maybe it's a spec ID that doesn't have the full object
        entity_type = "spec" if entity_id.isdigit() else "idea"

    ep_response = list_endpoints(app)
    mod_response = list_modules(app)
    
    matching_endpoints = []
    matching_modules = []
    contributors = set()
    call_count = 0
    
    for ep in ep_response.endpoints:
        match = False
        if entity_type == "spec" and entity_id in ep.spec_ids:
            match = True
        elif entity_type == "idea" and entity_id in ep.idea_ids:
            match = True
            
        if match:
            matching_endpoints.append({"method": ep.method, "path": ep.path})
            contributors.update(ep.contributors)
            call_count += ep.call_count_30d
            
    for mod in mod_response.modules:
        match = False
        if entity_type == "spec" and entity_id in mod.spec_ids:
            match = True
        elif entity_type == "idea" and entity_id in mod.idea_ids:
            match = True
            
        if match:
            matching_modules.append({"name": mod.name, "path": mod.path})
            contributors.update(mod.contributors)

    return MetaTraceResult(
        id=entity_id,
        type=entity_type,
        title=title,
        endpoints=matching_endpoints,
        modules=matching_modules,
        contributors=sorted(list(contributors)),
        first_commit=None, # Would need git history scan
        call_count_30d=call_count
    )
