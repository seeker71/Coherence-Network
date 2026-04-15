"""Organ definitions — what we listen to, and how.

An "organ" is a single observable subsystem of the living network. Each organ
declares which upstream endpoint it depends on and a small extractor function
that decides, given a successful HTTP response, whether the organ is actually
breathing or only pretending to breathe (e.g. /api/health can return 200 while
reporting integrity_compromised=true internally).

Organs are grouped by the upstream call they share, so a single round-trip to
/api/health feeds several organ samples. This keeps the witness gentle on the
network it watches.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


# Result of applying an extractor to a successful upstream response.
# ok=False with a detail string means "the call succeeded but the organ is
# not actually breathing" (e.g. integrity flag flipped).
@dataclass(frozen=True)
class OrganVerdict:
    ok: bool
    detail: str | None = None


Extractor = Callable[[int, dict[str, Any] | None], OrganVerdict]


@dataclass(frozen=True)
class Organ:
    """One observable subsystem."""

    name: str                # stable id used in storage + API
    label: str               # human-readable name for the UI
    description: str         # one-line explanation
    upstream: str            # one of UPSTREAM_* below
    extractor: Extractor


# --- upstream labels ------------------------------------------------------

UPSTREAM_API_HEALTH = "api_health"   # {API_BASE}/api/health
UPSTREAM_API_READY = "api_ready"     # {API_BASE}/api/ready
UPSTREAM_WEB_ROOT = "web_root"       # {WEB_BASE}/


# --- extractors -----------------------------------------------------------

def _is_ok(status: int) -> bool:
    return 200 <= status < 300


def extract_api(status: int, body: dict[str, Any] | None) -> OrganVerdict:
    """API organ: /api/health returns 200 with status == "ok"."""
    if not _is_ok(status):
        return OrganVerdict(False, f"HTTP {status}")
    if not body:
        return OrganVerdict(False, "empty response body")
    if body.get("status") != "ok":
        return OrganVerdict(False, f"status={body.get('status')!r}")
    return OrganVerdict(True)


def extract_web(status: int, _body: dict[str, Any] | None) -> OrganVerdict:
    """Web organ: root returns 2xx (body is HTML, we don't parse it)."""
    if not _is_ok(status):
        return OrganVerdict(False, f"HTTP {status}")
    return OrganVerdict(True)


def _ready_503_reason(body: dict[str, Any] | None) -> str:
    """The 503 detail on /api/ready has two distinct causes.

    When graph_store is None the detail is the plain string 'not ready'.
    When the persistence contract fails the detail is a dict with
    error == 'persistence_contract_failed'. We use this to distinguish
    postgres-side failures from neo4j-side failures below.
    """
    if not body:
        return "unknown"
    detail = body.get("detail")
    if isinstance(detail, dict) and detail.get("error") == "persistence_contract_failed":
        return "persistence_contract_failed"
    if detail == "not ready":
        return "graph_store_missing"
    return "unknown"


def extract_postgres(status: int, body: dict[str, Any] | None) -> OrganVerdict:
    """Postgres organ: db_connected true, or persistence contract failing."""
    if status == 503:
        reason = _ready_503_reason(body)
        if reason == "persistence_contract_failed":
            return OrganVerdict(False, "persistence contract failed")
        # graph_store_missing is a neo4j signal, not a postgres signal —
        # we can't tell postgres state from this response, so call it unknown
        # by returning ok=False with a neutral note.
        return OrganVerdict(False, "unknown (ready=503)")
    if not _is_ok(status):
        return OrganVerdict(False, f"HTTP {status}")
    if not body:
        return OrganVerdict(False, "empty response body")
    if not body.get("db_connected"):
        return OrganVerdict(False, "db_connected=false")
    return OrganVerdict(True)


def extract_neo4j(status: int, body: dict[str, Any] | None) -> OrganVerdict:
    """Neo4j organ: 503 only counts when graph_store is specifically missing."""
    if status == 503:
        reason = _ready_503_reason(body)
        if reason == "graph_store_missing":
            return OrganVerdict(False, "graph_store unavailable")
        # 503 for some other reason is not a neo4j signal — neo4j may be fine.
        return OrganVerdict(True)
    if not _is_ok(status):
        return OrganVerdict(False, f"HTTP {status}")
    if not body:
        return OrganVerdict(False, "empty response body")
    if body.get("status") != "ready":
        return OrganVerdict(False, f"ready status={body.get('status')!r}")
    return OrganVerdict(True)


def extract_schema(status: int, body: dict[str, Any] | None) -> OrganVerdict:
    """Schema organ: /api/health body.schema_ok==true."""
    if not _is_ok(status):
        return OrganVerdict(False, f"HTTP {status}")
    if not body:
        return OrganVerdict(False, "empty response body")
    if not body.get("schema_ok", True):
        return OrganVerdict(False, "schema_ok=false")
    return OrganVerdict(True)


def extract_audit(status: int, body: dict[str, Any] | None) -> OrganVerdict:
    """Audit-integrity organ: /api/health body.integrity_compromised==false."""
    if not _is_ok(status):
        return OrganVerdict(False, f"HTTP {status}")
    if not body:
        return OrganVerdict(False, "empty response body")
    if body.get("integrity_compromised"):
        return OrganVerdict(False, "integrity_compromised=true")
    return OrganVerdict(True)


# --- the canonical organ list ---------------------------------------------

ORGANS: list[Organ] = [
    Organ(
        name="api",
        label="API",
        description="The central nervous system — FastAPI, the place where thoughts become actions.",
        upstream=UPSTREAM_API_HEALTH,
        extractor=extract_api,
    ),
    Organ(
        name="web",
        label="Web",
        description="The skin and face — Next.js, how the network meets the world.",
        upstream=UPSTREAM_WEB_ROOT,
        extractor=extract_web,
    ),
    Organ(
        name="postgres",
        label="PostgreSQL",
        description="Long memory — the relational store where facts persist.",
        upstream=UPSTREAM_API_READY,
        extractor=extract_postgres,
    ),
    Organ(
        name="neo4j",
        label="Neo4j",
        description="Association memory — the graph of ideas, specs, and their ties.",
        upstream=UPSTREAM_API_READY,
        extractor=extract_neo4j,
    ),
    Organ(
        name="schema",
        label="Schema",
        description="Structural integrity — core tables present and sound.",
        upstream=UPSTREAM_API_HEALTH,
        extractor=extract_schema,
    ),
    Organ(
        name="audit_integrity",
        label="Audit Integrity",
        description="Conscience — the audit ledger's hash chain is unbroken.",
        upstream=UPSTREAM_API_HEALTH,
        extractor=extract_audit,
    ),
]


def organs_by_name() -> dict[str, Organ]:
    return {o.name: o for o in ORGANS}


def organs_for_upstream(upstream: str) -> list[Organ]:
    return [o for o in ORGANS if o.upstream == upstream]
