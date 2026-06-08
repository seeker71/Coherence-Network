#!/usr/bin/env python3
"""Break down /api/ideas time across public Python, native Go, and same-SQL Python.

The goal is to separate optimization context from out-of-context cost:

* public FastAPI HTTP total includes internet/proxy/Traefik/FastAPI/service work.
* local native Go HTTP total includes loopback HTTP plus the SSH-tunneled DB.
* native timing route reports BML handler-internal segments.
* same-SQL Python reports Python DB/query/shape/json time against the same tunnel.

The script reads database credentials only from a config file and redacts the URL
in its output.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
BML_CATALOG = ROOT / "deploy" / "front-door" / "api.bml"
DEFAULT_DB_CONFIG = Path.home() / ".coherence-network" / "secrets" / "form-kernel-postgres-tunnel.json"
DEFAULT_PUBLIC_BASE = "https://api.coherencycoin.com"
DEFAULT_NATIVE_BASE = "http://127.0.0.1:19086"


def percentile(samples: list[float], pct: float) -> float:
    if not samples:
        return 0.0
    ordered = sorted(samples)
    idx = max(0, min(len(ordered) - 1, round((pct / 100.0) * (len(ordered) - 1))))
    return ordered[idx]


def stats(samples: list[float]) -> dict[str, Any]:
    if not samples:
        return {"count": 0}
    return {
        "count": len(samples),
        "p50_ms": round(percentile(samples, 50), 3),
        "p95_ms": round(percentile(samples, 95), 3),
        "p99_ms": round(percentile(samples, 99), 3),
        "mean_ms": round(statistics.fmean(samples), 3),
        "min_ms": round(min(samples), 3),
        "max_ms": round(max(samples), 3),
        "stdev_ms": round(statistics.pstdev(samples), 3) if len(samples) > 1 else 0.0,
    }


def segment_stats(rows: list[dict[str, float]]) -> dict[str, Any]:
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    return {key: stats([float(row[key]) for row in rows if key in row]) for key in keys}


def profile(label: str, thunk, samples: int, warmup: int) -> dict[str, Any]:
    timings: list[float] = []
    segment_rows: list[dict[str, float]] = []
    sample_rows: list[dict[str, Any]] = []
    last: dict[str, Any] | None = None
    try:
        for _ in range(warmup):
            last = thunk()
        for _ in range(samples):
            start = time.perf_counter()
            last = thunk()
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            timings.append(elapsed_ms)
            sample_row: dict[str, Any] = {"total_ms": elapsed_ms}
            if isinstance(last, dict) and isinstance(last.get("timings_ms"), dict):
                timing_row = {k: float(v) for k, v in last["timings_ms"].items()}
                segment_rows.append(timing_row)
                sample_row["segments_ms"] = timing_row
            sample_rows.append(sample_row)
    except Exception as exc:
        return {
            "label": label,
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
        }

    out: dict[str, Any] = {
        "label": label,
        "status": "ok",
        "total": stats(timings),
    }
    if last is not None:
        for key in ("status_code", "handler_status", "body_bytes", "rows_returned", "summary_rows"):
            if key in last:
                out[key] = last[key]
    if segment_rows:
        out["segments"] = segment_stats(segment_rows)
        out["slowest_samples"] = [
            {
                "total_ms": round(row["total_ms"], 3),
                "segments_ms": {k: round(v, 3) for k, v in row.get("segments_ms", {}).items()},
            }
            for row in sorted(sample_rows, key=lambda item: item["total_ms"], reverse=True)[:5]
        ]
    return out


def request_json(base: str, path: str, query: str, headers: dict[str, str]) -> dict[str, Any]:
    body, status_code, elapsed_ms = request_text(base, path, query, headers)
    parsed = json.loads(body)
    parsed["status_code"] = status_code
    parsed["http_total_ms"] = elapsed_ms
    if "status" in parsed:
        parsed["handler_status"] = parsed["status"]
    return parsed


def request_text(base: str, path: str, query: str, headers: dict[str, str]) -> tuple[str, int, float]:
    url = base.rstrip("/") + path
    if query:
        url += "?" + query
    req = urllib.request.Request(url, headers=headers)
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=30.0) as resp:
            body_bytes = resp.read()
            return body_bytes.decode("utf-8"), int(resp.status), (time.perf_counter() - start) * 1000.0
    except urllib.error.HTTPError as exc:
        body_bytes = exc.read()
        return body_bytes.decode("utf-8"), int(exc.code), (time.perf_counter() - start) * 1000.0


def http_text_probe(base: str, path: str, query: str, headers: dict[str, str]) -> dict[str, Any]:
    body, status_code, _elapsed_ms = request_text(base, path, query, headers)
    return {
        "status_code": status_code,
        "body_bytes": len(body.encode("utf-8")),
    }


def route_query(args: argparse.Namespace) -> str:
    values: dict[str, Any] = {
        "limit": args.limit,
        "offset": args.offset,
        "sort": args.sort,
    }
    if args.query:
        values["query"] = args.query
    if args.include_internal is not None:
        values["include_internal"] = "true" if args.include_internal else "false"
    if args.only_unvalidated:
        values["only_unvalidated"] = "true"
    if args.curated_only:
        values["curated_only"] = "true"
    if args.pillar:
        values["pillar"] = args.pillar
    if args.workspace_id:
        values["workspace_id"] = args.workspace_id
    if args.tags:
        values["tags"] = args.tags
    return urllib.parse.urlencode(values)


def extract_bml_string_function(name: str) -> str:
    text = BML_CATALOG.read_text()
    match = re.search(rf'def {re.escape(name)}\(\) = "([^"]*)";', text)
    if not match:
        raise RuntimeError(f"{name} not found in {BML_CATALOG}")
    return match.group(1)


def psycopg_sql(sql: str) -> str:
    escaped = sql.replace("%", "%%")
    return re.sub(r"\$(\d+)", r"%(p\1)s", escaped)


def sql_params(values: list[Any]) -> dict[str, Any]:
    return {f"p{i + 1}": value for i, value in enumerate(values)}


def load_database_url(path: Path) -> str:
    data = json.loads(path.read_text())
    if isinstance(data.get("database"), dict) and data["database"].get("url"):
        return str(data["database"]["url"])
    if data.get("database_url"):
        return str(data["database_url"])
    raise RuntimeError(f"database.url not found in {path}")


def redact_database_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    redacted_netloc = f"***:***@{host}{port}" if parsed.username else f"{host}{port}"
    return urllib.parse.urlunsplit((parsed.scheme, redacted_netloc, parsed.path, parsed.query, parsed.fragment))


def query_arg_lists(args: argparse.Namespace) -> tuple[list[Any], list[Any]]:
    sort_value = "marginal_cc" if args.sort == "marginal_cc" else "free_energy"
    include_internal = True if args.include_internal is None else bool(args.include_internal)
    summary = [
        args.query or "",
        include_internal,
        bool(args.only_unvalidated),
        bool(args.curated_only),
        args.pillar or "",
        args.workspace_id or "",
        args.tags or "",
    ]
    page = [*summary, sort_value, int(args.limit), int(args.offset)]
    return summary, page


def json_load_text(value: Any, default: Any) -> Any:
    if value is None or value == "":
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(str(value))
    except json.JSONDecodeError:
        return default


def number(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    return float(value)


def nullable_string(value: Any) -> str | None:
    text = "" if value is None else str(value)
    return None if text == "" else text


def idea_json_row(row: dict[str, Any]) -> dict[str, Any]:
    estimated_cost = number(row.get("estimated_cost"))
    potential_value = number(row.get("potential_value"))
    return {
        "id": str(row.get("id") or ""),
        "name": str(row.get("name") or ""),
        "description": str(row.get("description") or ""),
        "potential_value": potential_value,
        "actual_value": number(row.get("actual_value")),
        "estimated_cost": estimated_cost,
        "actual_cost": number(row.get("actual_cost")),
        "resistance_risk": number(row.get("resistance_risk")),
        "confidence": number(row.get("confidence")),
        "manifestation_status": str(row.get("manifestation_status") or "none"),
        "interfaces": json_load_text(row.get("interfaces_json"), []),
        "open_questions": json_load_text(row.get("open_questions_json"), []),
        "idea_type": str(row.get("idea_type") or "standalone"),
        "parent_idea_id": nullable_string(row.get("parent_idea_id")),
        "child_idea_ids": json_load_text(row.get("child_idea_ids_json"), []),
        "stage": str(row.get("stage") or "none"),
        "work_type": nullable_string(row.get("work_type")),
        "lifecycle": str(row.get("lifecycle") or "active"),
        "duplicate_of": nullable_string(row.get("duplicate_of")),
        "last_activity_at": nullable_string(row.get("last_activity_at")),
        "value_basis": json_load_text(row.get("value_basis_json"), None),
        "cost_vector": {
            "compute_cc": estimated_cost * 0.6,
            "infrastructure_cc": estimated_cost * 0.15,
            "human_attention_cc": estimated_cost * 0.25,
            "opportunity_cc": 0.0,
            "external_cc": 0.0,
            "total_cc": estimated_cost,
        },
        "value_vector": {
            "adoption_cc": potential_value * 0.5,
            "lineage_cc": potential_value * 0.3,
            "friction_avoided_cc": potential_value * 0.2,
            "revenue_cc": 0.0,
            "total_cc": potential_value,
        },
        "tags": json_load_text(row.get("tags_json"), []),
        "workspace_git_url": nullable_string(row.get("workspace_git_url")),
        "slug": str(row.get("slug") or ""),
        "slug_history": json_load_text(row.get("slug_history_json"), []),
        "is_curated": bool(row.get("is_curated")),
        "pillar": nullable_string(row.get("pillar")),
        "workspace_id": str(row.get("workspace_id") or "coherence-network"),
        "rollup_condition": nullable_string(row.get("rollup_condition")),
        "free_energy_score": number(row.get("free_energy_score")),
        "value_gap": number(row.get("value_gap")),
        "content_markdown": "",
        "marginal_cc_score": number(row.get("marginal_cc_score")),
        "selection_weight": number(row.get("selection_weight")),
        "remaining_cost_cc": number(row.get("remaining_cost_cc")),
        "value_gap_cc": number(row.get("value_gap_cc")),
        "roi_cc": number(row.get("roi_cc")),
    }


def idea_response(summary: dict[str, Any], rows: list[dict[str, Any]], limit: int, offset: int) -> dict[str, Any]:
    total = int(summary.get("total_ideas") or 0)
    returned = len(rows)
    return {
        "ideas": [idea_json_row(row) for row in rows],
        "summary": {
            "total_ideas": total,
            "unvalidated_ideas": int(summary.get("unvalidated_ideas") or 0),
            "validated_ideas": int(summary.get("validated_ideas") or 0),
            "total_potential_value": number(summary.get("total_potential_value")),
            "total_actual_value": number(summary.get("total_actual_value")),
            "total_value_gap": number(summary.get("total_value_gap")),
        },
        "pagination": {
            "total": total,
            "limit": int(limit),
            "offset": int(offset),
            "returned": returned,
            "has_more": (int(offset) + returned) < total,
        },
    }


def compact_json_bytes(value: Any) -> bytes:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def python_same_sql_thunk(database_url: str, args: argparse.Namespace):
    import psycopg2
    import psycopg2.extras

    summary_sql = psycopg_sql(extract_bml_string_function("api-ideas-summary-sql"))
    page_sql = psycopg_sql(extract_bml_string_function("api-ideas-page-sql"))
    summary_values, page_values = query_arg_lists(args)

    def thunk() -> dict[str, Any]:
        t0 = time.perf_counter()
        conn = psycopg2.connect(database_url)
        t_connect = time.perf_counter()
        summary_params = sql_params(summary_values)
        page_params = sql_params(page_values)
        t_params = time.perf_counter()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(summary_sql, summary_params)
                summary_rows = [dict(row) for row in cur.fetchall()]
                t_summary = time.perf_counter()
                cur.execute(page_sql, page_params)
                page_rows = [dict(row) for row in cur.fetchall()]
                t_page = time.perf_counter()
        finally:
            conn.close()
        t_close = time.perf_counter()
        response = idea_response(summary_rows[0], page_rows, int(args.limit), int(args.offset))
        t_shape = time.perf_counter()
        body = compact_json_bytes(response)
        t_emit = time.perf_counter()
        return {
            "status_code": 200,
            "body_bytes": len(body),
            "rows_returned": len(page_rows),
            "summary_rows": len(summary_rows),
            "timings_ms": {
                "connect": (t_connect - t0) * 1000.0,
                "params": (t_params - t_connect) * 1000.0,
                "summary_query": (t_summary - t_params) * 1000.0,
                "page_query": (t_page - t_summary) * 1000.0,
                "close": (t_close - t_page) * 1000.0,
                "shape_dicts": (t_shape - t_close) * 1000.0,
                "json_dumps": (t_emit - t_shape) * 1000.0,
                "handler_total": (t_emit - t0) * 1000.0,
            },
        }

    return thunk


def parse_bool(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"invalid bool: {value}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--limit", type=int, default=2)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--sort", choices=["free_energy", "marginal_cc"], default="marginal_cc")
    parser.add_argument("--query", default="")
    parser.add_argument("--include-internal", type=parse_bool, default=None)
    parser.add_argument("--only-unvalidated", action="store_true")
    parser.add_argument("--curated-only", action="store_true")
    parser.add_argument("--pillar", default="")
    parser.add_argument("--workspace-id", default="")
    parser.add_argument("--tags", default="")
    parser.add_argument("--public-base", default=DEFAULT_PUBLIC_BASE)
    parser.add_argument("--native-base", default=DEFAULT_NATIVE_BASE)
    parser.add_argument("--db-config", type=Path, default=DEFAULT_DB_CONFIG)
    parser.add_argument("--skip-public", action="store_true")
    parser.add_argument("--skip-native", action="store_true")
    parser.add_argument("--skip-python-sql", action="store_true")
    args = parser.parse_args()

    query = route_query(args)
    headers = {"Accept": "application/json", "User-Agent": "CoherenceRouteTiming/1.0"}
    observe_headers = {
        "Accept": "application/json",
        "User-Agent": "CoherenceRouteTiming/1.0",
        "X-Form-Observe": "1",
    }
    out: dict[str, Any] = {
        "route": "/api/ideas",
        "query": query,
        "samples": args.samples,
        "warmup": args.warmup,
        "optimization_scope": {
            "inside_scope": [
                "handler parameter projection",
                "database query execution",
                "row-to-response shaping",
                "Form json-emit / Python json.dumps",
                "JIT dispatch and primitive lowering",
            ],
            "outside_scope": [
                "process startup",
                "public internet path",
                "Cloudflare/proxy traversal",
                "TCP accept",
                "client response download",
            ],
        },
    }

    if not args.skip_public:
        out["public_fastapi_http_total"] = profile(
            "public_fastapi_http_total",
            lambda: http_text_probe(args.public_base, "/api/ideas", query, headers),
            args.samples,
            args.warmup,
        )

    if not args.skip_native:
        out["native_go_http_total"] = profile(
            "native_go_http_total",
            lambda: http_text_probe(args.native_base, "/api/ideas", query, headers),
            args.samples,
            args.warmup,
        )
        out["native_go_handler_timing"] = profile(
            "native_go_handler_timing",
            lambda: request_json(args.native_base, "/api/_form/ideas-timing", query, observe_headers),
            args.samples,
            args.warmup,
        )

    if not args.skip_python_sql:
        try:
            database_url = load_database_url(args.db_config)
            out["python_same_sql"] = {
                "database_url": redact_database_url(database_url),
                "profile": profile(
                    "python_same_sql",
                    python_same_sql_thunk(database_url, args),
                    args.samples,
                    args.warmup,
                ),
            }
        except Exception as exc:
            out["python_same_sql"] = {
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
            }

    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
