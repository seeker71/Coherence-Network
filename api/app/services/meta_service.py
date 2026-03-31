"""Metadata self-discovery service.

Introspects the FastAPI app to expose every endpoint, module, and Pydantic model
as a concept node — the codex.meta namespace.

  codex.meta/route/<METHOD>/<path>  — every registered API route
  codex.meta/module/<dotted.name>   — every code module
  codex.meta/type/<ClassName>       — every Pydantic model

Nodes carry edges to specs and ideas via the traceability registry, and to each
other (routes to modules, routes to types, modules to types).
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Any, get_args, get_origin

from pydantic import BaseModel

from app.models.meta import (
    EndpointEdge,
    EndpointNode,
    MetaEndpointsResponse,
    MetaGraphEdge,
    MetaGraphNode,
    MetaGraphResponse,
    MetaModulesResponse,
    MetaSummaryResponse,
    MetaTypesResponse,
    ModuleNode,
    TypeField,
    TypeNode,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_trace_registry() -> list[dict[str, Any]]:
    try:
        from app.middleware.traceability import _TRACE_REGISTRY
        return _TRACE_REGISTRY
    except Exception:
        return []


def _build_trace_index(registry: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for entry in registry:
        fn = entry.get("function", "")
        if fn:
            index[fn] = entry
    return index


def _type_str(annotation: Any) -> str:
    if annotation is inspect.Parameter.empty:
        return "Any"
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is not None:
        origin_name = getattr(origin, "__name__", str(origin))
        if args:
            args_str = ", ".join(_type_str(a) for a in args)
            return f"{origin_name}[{args_str}]"
        return origin_name
    if hasattr(annotation, "__name__"):
        return annotation.__name__
    return str(annotation)


def _make_type_id(cls: type) -> str:
    return f"codex.meta/type/{cls.__name__}"


def _is_pydantic(obj: Any) -> bool:
    try:
        return (
            isinstance(obj, type)
            and issubclass(obj, BaseModel)
            and obj is not BaseModel
        )
    except TypeError:
        return False


# ---------------------------------------------------------------------------
# Endpoint introspection
# ---------------------------------------------------------------------------

def list_endpoints(app: Any) -> MetaEndpointsResponse:
    """Walk FastAPI routes and return each as an EndpointNode concept node."""
    registry = _get_trace_registry()
    trace_index = _build_trace_index(registry)
    nodes: list[EndpointNode] = []

    try:
        routes = app.routes
    except Exception:
        routes = []

    _SKIP = {"/", "/openapi.json", "/docs", "/redoc", "/api/admin/reset-database"}

    for route in routes:
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", None)
        if not methods or not path or path in _SKIP:
            continue

        name = getattr(route, "name", "") or ""
        tags = list(getattr(route, "tags", []) or [])
        summary = getattr(route, "summary", None) or getattr(route, "description", None)
        endpoint_fn = getattr(route, "endpoint", None)
        module_name: str | None = None
        if endpoint_fn:
            module_name = getattr(endpoint_fn, "__module__", None)

        # Link to response type from FastAPI route annotation
        response_model = getattr(route, "response_model", None)
        response_model_id: str | None = None
        if response_model and _is_pydantic(response_model):
            response_model_id = _make_type_id(response_model)

        # Infer request body type from endpoint function signature
        request_model_id: str | None = None
        if endpoint_fn:
            try:
                sig = inspect.signature(endpoint_fn)
                for param in sig.parameters.values():
                    ann = param.annotation
                    if _is_pydantic(ann):
                        request_model_id = _make_type_id(ann)
                        break
            except (ValueError, TypeError):
                pass

        for method in sorted(methods):
            node_id = f"{method} {path}"
            edges: list[EndpointEdge] = []
            spec_id: str | None = None
            idea_id: str | None = None

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
            if response_model_id:
                edges.append(EndpointEdge(
                    type="returns_type",
                    target_id=response_model_id,
                    target_label=response_model_id.split("/")[-1],
                ))
            if request_model_id:
                edges.append(EndpointEdge(
                    type="accepts_type",
                    target_id=request_model_id,
                    target_label=request_model_id.split("/")[-1],
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
                request_model=request_model_id,
                response_model=response_model_id,
                edges=edges,
            ))

    nodes.sort(key=lambda n: (n.path, n.method))
    return MetaEndpointsResponse(total=len(nodes), endpoints=nodes)


# ---------------------------------------------------------------------------
# Module introspection
# ---------------------------------------------------------------------------

def list_modules(app: Any) -> MetaModulesResponse:
    """Return code modules as concept nodes linked to endpoints, specs, and ideas."""
    registry = _get_trace_registry()
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
            module_data[module_name] = {"spec_ids": set(), "idea_ids": set(), "endpoint_count": 0}
        module_data[module_name]["endpoint_count"] += len(methods)

    for entry in registry:
        mod = entry.get("module", "")
        if not mod:
            continue
        if mod not in module_data:
            module_data[mod] = {"spec_ids": set(), "idea_ids": set(), "endpoint_count": 0}
        if entry.get("spec"):
            module_data[mod]["spec_ids"].add(entry["spec"])
        if entry.get("idea"):
            module_data[mod]["idea_ids"].add(entry["idea"])

    nodes: list[ModuleNode] = []
    for mod_name, data in sorted(module_data.items()):
        short_name = mod_name.split(".")[-1]
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
            edges.append(EndpointEdge(
                type="implements_spec",
                target_id=f"spec-{sid}",
                target_label=f"Spec {sid}",
            ))
        for iid in idea_ids:
            edges.append(EndpointEdge(
                type="traces_idea",
                target_id=iid,
                target_label=iid,
            ))

        nodes.append(ModuleNode(
            id=mod_name,
            name=short_name,
            module_type=module_type,
            file_path=mod_name.replace(".", "/") + ".py",
            spec_ids=spec_ids,
            idea_ids=idea_ids,
            endpoint_count=data["endpoint_count"],
            edges=edges,
        ))

    return MetaModulesResponse(total=len(nodes), modules=nodes)


# ---------------------------------------------------------------------------
# Type introspection  (codex.meta/type nodes)
# ---------------------------------------------------------------------------

def _discover_pydantic_models() -> dict[str, type]:
    """Walk app.models package and collect all Pydantic BaseModel subclasses."""
    models: dict[str, type] = {}
    try:
        import app.models as models_pkg
        pkg_path = models_pkg.__path__
        pkg_name = models_pkg.__name__
    except Exception:
        return models

    for _finder, mod_name, _ispkg in pkgutil.walk_packages(pkg_path, prefix=pkg_name + "."):
        try:
            mod = importlib.import_module(mod_name)
        except Exception:
            continue
        for attr_name in dir(mod):
            obj = getattr(mod, attr_name, None)
            if not _is_pydantic(obj):
                continue
            # Only include classes defined in this specific module (not re-exports)
            if getattr(obj, "__module__", None) != mod_name:
                continue
            key = f"{mod_name}.{obj.__name__}"
            models[key] = obj

    return models


def _build_type_node(cls: type, endpoint_ids: list[str]) -> TypeNode:
    type_id = _make_type_id(cls)
    module = getattr(cls, "__module__", "unknown")

    fields: list[TypeField] = []
    try:
        for field_name, field_info in cls.model_fields.items():
            ann = field_info.annotation
            type_annotation = _type_str(ann) if ann is not None else "Any"
            required = field_info.is_required()
            default = None
            if not required:
                default_val = field_info.default
                if default_val is not None:
                    try:
                        default = repr(default_val)
                    except Exception:
                        default = str(default_val)
            description = getattr(field_info, "description", None)
            fields.append(TypeField(
                name=field_name,
                type_str=type_annotation,
                required=required,
                default=default,
                description=description,
            ))
    except Exception:
        pass

    base_classes = [
        b.__name__ for b in cls.__mro__
        if b is not cls and b is not object and b is not BaseModel
        and isinstance(b, type)
    ]

    edges: list[EndpointEdge] = [
        EndpointEdge(type="used_by_endpoint", target_id=ep_id, target_label=ep_id)
        for ep_id in endpoint_ids
    ]

    return TypeNode(
        id=type_id,
        name=cls.__name__,
        module=module,
        fields=fields,
        used_in_endpoints=endpoint_ids,
        base_classes=base_classes,
        edges=edges,
    )


def list_types(app: Any) -> MetaTypesResponse:
    """Return all Pydantic models in app.models as TypeNode concept nodes."""
    # Build endpoint model usage index first
    ep_response = list_endpoints(app)
    type_usage: dict[str, list[str]] = {}
    for ep in ep_response.endpoints:
        for type_id in [ep.request_model, ep.response_model]:
            if type_id:
                type_usage.setdefault(type_id, []).append(ep.id)

    all_models = _discover_pydantic_models()
    nodes: list[TypeNode] = []
    for _key, cls in sorted(all_models.items(), key=lambda kv: kv[1].__name__):
        type_id = _make_type_id(cls)
        node = _build_type_node(cls, type_usage.get(type_id, []))
        nodes.append(node)

    nodes.sort(key=lambda n: n.name)
    return MetaTypesResponse(total=len(nodes), types=nodes)


# ---------------------------------------------------------------------------
# Full meta-node graph  (nodes + edges for traversal/visualization)
# ---------------------------------------------------------------------------

def get_graph(app: Any) -> MetaGraphResponse:
    """Return the complete meta-node graph as nodes + edges for graph traversal."""
    ep_response = list_endpoints(app)
    mod_response = list_modules(app)
    type_response = list_types(app)

    graph_nodes: list[MetaGraphNode] = []
    graph_edges: list[MetaGraphEdge] = []
    seen_node_ids: set[str] = set()

    def add_node(node_id: str, label: str, node_type: str, props: dict | None = None) -> None:
        if node_id not in seen_node_ids:
            seen_node_ids.add(node_id)
            graph_nodes.append(MetaGraphNode(
                id=node_id,
                label=label,
                node_type=node_type,
                properties=props or {},
            ))

    def add_edge(source: str, target: str, edge_type: str) -> None:
        graph_edges.append(MetaGraphEdge(source=source, target=target, edge_type=edge_type))

    for ep in ep_response.endpoints:
        add_node(ep.id, f"{ep.method} {ep.path}", "route", {
            "method": ep.method,
            "path": ep.path,
            "tags": ep.tags,
            "traced": bool(ep.spec_id or ep.idea_id),
        })
        for edge in ep.edges:
            tgt = edge.target_id
            if tgt.startswith("spec-"):
                add_node(tgt, edge.target_label or tgt, "spec")
            elif tgt.startswith("codex.meta/type/"):
                add_node(tgt, tgt.split("/")[-1], "type")
            elif "." in tgt:
                add_node(tgt, tgt.split(".")[-1], "module")
            else:
                add_node(tgt, edge.target_label or tgt, "idea")
            add_edge(ep.id, tgt, edge.type)

    for mod in mod_response.modules:
        add_node(mod.id, mod.name, "module", {
            "module_type": mod.module_type,
            "endpoint_count": mod.endpoint_count,
        })
        for edge in mod.edges:
            tgt = edge.target_id
            if tgt.startswith("spec-"):
                add_node(tgt, edge.target_label or tgt, "spec")
            else:
                add_node(tgt, edge.target_label or tgt, "idea")
            add_edge(mod.id, tgt, edge.type)

    for tn in type_response.types:
        add_node(tn.id, tn.name, "type", {
            "module": tn.module,
            "field_count": len(tn.fields),
        })
        for edge in tn.edges:
            add_edge(tn.id, edge.target_id, edge.type)

    return MetaGraphResponse(
        nodes=graph_nodes,
        edges=graph_edges,
        node_count=len(graph_nodes),
        edge_count=len(graph_edges),
    )


# ---------------------------------------------------------------------------
# Auto-generated Markdown docs
# ---------------------------------------------------------------------------

def get_docs(app: Any) -> str:
    """Generate a Markdown document describing the full API surface."""
    ep_response = list_endpoints(app)
    mod_response = list_modules(app)
    type_response = list_types(app)
    summary = get_summary(app)

    lines: list[str] = [
        "# Coherence Network - Auto-Generated API Reference",
        "",
        f"> Generated by codex.meta introspection: "
        f"{summary.endpoint_count} endpoints, "
        f"{summary.module_count} modules, "
        f"{summary.type_count} types, "
        f"{round(summary.spec_coverage * 100, 1)}% traced to specs.",
        "",
        "## Endpoints",
        "",
    ]

    by_tag: dict[str, list] = {}
    for ep in ep_response.endpoints:
        tag = ep.tags[0] if ep.tags else "other"
        by_tag.setdefault(tag, []).append(ep)

    for tag in sorted(by_tag):
        lines.append(f"### {tag}")
        lines.append("")
        for ep in by_tag[tag]:
            traced = " (traced)" if (ep.spec_id or ep.idea_id) else ""
            lines.append(f"#### {ep.method} {ep.path}{traced}")
            if ep.summary:
                lines.extend(["", ep.summary])
            meta_parts = []
            if ep.spec_id:
                meta_parts.append(f"spec: {ep.spec_id}")
            if ep.idea_id:
                meta_parts.append(f"idea: {ep.idea_id}")
            if ep.module:
                meta_parts.append(f"module: {ep.module}")
            if ep.response_model:
                meta_parts.append(f"returns: {ep.response_model.split('/')[-1]}")
            if ep.request_model:
                meta_parts.append(f"accepts: {ep.request_model.split('/')[-1]}")
            if meta_parts:
                lines.extend(["", "  " + " | ".join(meta_parts)])
            lines.append("")

    lines.extend(["## Data Types", ""])
    for tn in type_response.types:
        lines.extend([f"### {tn.name}", f"module: {tn.module}", ""])
        if tn.fields:
            lines.extend(["| Field | Type | Required |", "|-------|------|----------|"])
            for f in tn.fields:
                lines.append(f"| {f.name} | {f.type_str} | {'yes' if f.required else 'no'} |")
        lines.append("")

    lines.extend(["## Code Modules", ""])
    for mod in mod_response.modules:
        lines.append(f"- {mod.name} ({mod.module_type}) - {mod.endpoint_count} endpoints")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def get_summary(app: Any) -> MetaSummaryResponse:
    """Return a brief overview of system self-description coverage."""
    ep_response = list_endpoints(app)
    mod_response = list_modules(app)
    type_response = list_types(app)

    traced = sum(1 for ep in ep_response.endpoints if ep.spec_id or ep.idea_id)
    total = ep_response.total
    coverage = (traced / total) if total > 0 else 0.0

    return MetaSummaryResponse(
        endpoint_count=total,
        module_count=mod_response.total,
        type_count=type_response.total,
        traced_count=traced,
        spec_coverage=round(coverage, 4),
    )
