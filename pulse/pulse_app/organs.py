"""Organ definitions — what we listen to, and how.

An "organ" is a single observable subsystem of the living network. Each organ
declares which upstream endpoint it depends on and a small extractor function
that decides, given a successful HTTP response, whether the organ is actually
healthy. Extractors may check status, parsed JSON body shape, or rendered
response text — whatever the organ needs.

Two tiers:

  - Infrastructure organs probe /api/health, /api/ready, and / for status
    and structural health. They answer "is the plumbing up?".

  - Outcome organs probe specific pages and API endpoints with assertions
    on the rendered content or response shape. They answer "does this
    surface actually give users what it's supposed to give?". An outcome
    organ would have caught the /vitality shape-drift crash earlier in
    this session, where the status was 200 but the page rendered
    "Something went wrong".

Organs are grouped by the upstream call they share, so a single round-trip
to /api/health feeds several organ samples. The probe dispatcher issues
exactly one GET per distinct upstream label per round.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from pulse_app.probe import UpstreamResult


# Result of applying an extractor to an upstream response.
# ok=False with a detail string means the organ is not healthy; the detail
# is a short human explanation of what the witness saw.
@dataclass(frozen=True)
class OrganVerdict:
    ok: bool
    detail: str | None = None


Extractor = Callable[["UpstreamResult"], OrganVerdict]


@dataclass(frozen=True)
class Organ:
    """One observable subsystem."""

    name: str               # stable id used in storage + API
    label: str              # human-readable name for the UI
    description: str        # one-line explanation
    upstream: str           # one of UPSTREAM_* below
    extractor: Extractor


# --- upstream labels ------------------------------------------------------

UPSTREAM_API_HEALTH = "api_health"     # {API_BASE}/api/health
UPSTREAM_API_READY = "api_ready"       # {API_BASE}/api/ready
UPSTREAM_API_IDEAS = "api_ideas"       # {API_BASE}/api/ideas
UPSTREAM_API_VITALITY = "api_vitality"  # {API_BASE}/api/workspaces/coherence-network/vitality
UPSTREAM_WEB_ROOT = "web_root"         # {WEB_BASE}/
UPSTREAM_WEB_PULSE = "web_pulse"       # {WEB_BASE}/pulse
UPSTREAM_WEB_VITALITY = "web_vitality"  # {WEB_BASE}/vitality


# Error boundary marker rendered by the Next.js root error.tsx. When this
# string appears in an HTML response body we know the page crashed during
# SSR or client hydration — regardless of the 200 status code.
_NEXT_ERROR_MARKER = "Something went wrong"


# --- helpers --------------------------------------------------------------

def _is_ok(status: int) -> bool:
    return 200 <= status < 300


def _require_body(result: "UpstreamResult") -> dict | None:
    """Return the parsed JSON body or None. Used by JSON-shaped extractors."""
    return result.body if isinstance(result.body, dict) else None


def _require_text(result: "UpstreamResult") -> str | None:
    """Return the raw text body or None. Used by text/HTML-shaped extractors."""
    return result.text if isinstance(result.text, str) and result.text else None


# ==========================================================================
# Infrastructure extractors — status + JSON shape
# ==========================================================================

def extract_api(r: "UpstreamResult") -> OrganVerdict:
    """API organ: /api/health returns 200 with status == "ok"."""
    if not _is_ok(r.status):
        return OrganVerdict(False, f"HTTP {r.status}")
    body = _require_body(r)
    if body is None:
        return OrganVerdict(False, "empty response body")
    if body.get("status") != "ok":
        return OrganVerdict(False, f"status={body.get('status')!r}")
    return OrganVerdict(True)


def extract_schema(r: "UpstreamResult") -> OrganVerdict:
    """Schema organ: /api/health body.schema_ok == true."""
    if not _is_ok(r.status):
        return OrganVerdict(False, f"HTTP {r.status}")
    body = _require_body(r)
    if body is None:
        return OrganVerdict(False, "empty response body")
    if not body.get("schema_ok", True):
        return OrganVerdict(False, "schema_ok=false")
    return OrganVerdict(True)


def extract_audit(r: "UpstreamResult") -> OrganVerdict:
    """Audit-integrity organ: /api/health body.integrity_compromised == false."""
    if not _is_ok(r.status):
        return OrganVerdict(False, f"HTTP {r.status}")
    body = _require_body(r)
    if body is None:
        return OrganVerdict(False, "empty response body")
    if body.get("integrity_compromised"):
        return OrganVerdict(False, "integrity_compromised=true")
    return OrganVerdict(True)


def _ready_503_reason(body: dict | None) -> str:
    """/api/ready returns 503 for two distinct causes — distinguish them."""
    if not body:
        return "unknown"
    detail = body.get("detail")
    if isinstance(detail, dict) and detail.get("error") == "persistence_contract_failed":
        return "persistence_contract_failed"
    if detail == "not ready":
        return "graph_store_missing"
    return "unknown"


def extract_postgres(r: "UpstreamResult") -> OrganVerdict:
    """Postgres organ: db_connected true, or persistence contract failing."""
    if r.status == 503:
        reason = _ready_503_reason(r.body)
        if reason == "persistence_contract_failed":
            return OrganVerdict(False, "persistence contract failed")
        return OrganVerdict(False, "unknown (ready=503)")
    if not _is_ok(r.status):
        return OrganVerdict(False, f"HTTP {r.status}")
    body = _require_body(r)
    if body is None:
        return OrganVerdict(False, "empty response body")
    if not body.get("db_connected"):
        return OrganVerdict(False, "db_connected=false")
    return OrganVerdict(True)


def extract_neo4j(r: "UpstreamResult") -> OrganVerdict:
    """Neo4j organ: 503 only counts when graph_store is specifically missing."""
    if r.status == 503:
        reason = _ready_503_reason(r.body)
        if reason == "graph_store_missing":
            return OrganVerdict(False, "graph_store unavailable")
        return OrganVerdict(True)
    if not _is_ok(r.status):
        return OrganVerdict(False, f"HTTP {r.status}")
    body = _require_body(r)
    if body is None:
        return OrganVerdict(False, "empty response body")
    if body.get("status") != "ready":
        return OrganVerdict(False, f"ready status={body.get('status')!r}")
    return OrganVerdict(True)


# ==========================================================================
# Outcome extractors — status + rendered content / full response shape
# ==========================================================================

def extract_web(r: "UpstreamResult") -> OrganVerdict:
    """Web root organ: homepage serves HTML with Coherence Network branding."""
    if not _is_ok(r.status):
        return OrganVerdict(False, f"HTTP {r.status}")
    text = _require_text(r)
    if text is None:
        return OrganVerdict(False, "empty response body")
    if _NEXT_ERROR_MARKER in text:
        return OrganVerdict(False, "error boundary rendered")
    if "Coherence Network" not in text:
        return OrganVerdict(False, "missing Coherence Network branding")
    return OrganVerdict(True)


def extract_web_pulse(r: "UpstreamResult") -> OrganVerdict:
    """/pulse page renders the Pulse header and doesn't trip the error boundary."""
    if not _is_ok(r.status):
        return OrganVerdict(False, f"HTTP {r.status}")
    text = _require_text(r)
    if text is None:
        return OrganVerdict(False, "empty response body")
    if _NEXT_ERROR_MARKER in text:
        return OrganVerdict(False, "error boundary rendered")
    if ">Pulse<" not in text:
        return OrganVerdict(False, "missing Pulse h1")
    return OrganVerdict(True)


def extract_web_vitality(r: "UpstreamResult") -> OrganVerdict:
    """/vitality page renders the Vitality header and Diversity Index signal.

    This is the outcome organ that would have caught the signals.map crash
    earlier in the session, where /vitality returned HTTP 200 with an
    error boundary HTML body because the api response shape had drifted
    and the frontend was calling .map on a dict.
    """
    if not _is_ok(r.status):
        return OrganVerdict(False, f"HTTP {r.status}")
    text = _require_text(r)
    if text is None:
        return OrganVerdict(False, "empty response body")
    if _NEXT_ERROR_MARKER in text:
        return OrganVerdict(False, "error boundary rendered")
    if "Vitality" not in text:
        return OrganVerdict(False, "missing Vitality header")
    if "Diversity Index" not in text:
        return OrganVerdict(False, "missing Diversity Index signal")
    return OrganVerdict(True)


def extract_api_ideas(r: "UpstreamResult") -> OrganVerdict:
    """/api/ideas returns a dict with an 'ideas' list (the prod shape)."""
    if not _is_ok(r.status):
        return OrganVerdict(False, f"HTTP {r.status}")
    body = _require_body(r)
    if body is None:
        return OrganVerdict(False, "empty response body")
    ideas = body.get("ideas")
    if ideas is None:
        return OrganVerdict(False, "missing 'ideas' key")
    if not isinstance(ideas, list):
        return OrganVerdict(False, f"ideas is {type(ideas).__name__}, expected list")
    return OrganVerdict(True)


def extract_api_vitality(r: "UpstreamResult") -> OrganVerdict:
    """/api/workspaces/coherence-network/vitality returns the expected signals shape.

    This is the companion to extract_web_vitality — if the api shape
    drifts, this organ flags it directly, before the frontend has a
    chance to render an error boundary.
    """
    if not _is_ok(r.status):
        return OrganVerdict(False, f"HTTP {r.status}")
    body = _require_body(r)
    if body is None:
        return OrganVerdict(False, "empty response body")
    signals = body.get("signals")
    if signals is None:
        return OrganVerdict(False, "missing 'signals' key")
    if not isinstance(signals, dict):
        return OrganVerdict(False, f"signals is {type(signals).__name__}, expected dict")
    if "diversity_index" not in signals:
        return OrganVerdict(False, "missing signals.diversity_index")
    return OrganVerdict(True)


# ==========================================================================
# The canonical organ list
# ==========================================================================

ORGANS: list[Organ] = [
    # --- infrastructure ---
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
    # --- outcome organs: rendered pages ---
    Organ(
        name="page_pulse",
        label="Pulse page",
        description="The /pulse surface — the organ that shows the other organs to the world.",
        upstream=UPSTREAM_WEB_PULSE,
        extractor=extract_web_pulse,
    ),
    Organ(
        name="page_vitality",
        label="Vitality page",
        description="The /vitality surface — the deeper signal of life, rendered for humans.",
        upstream=UPSTREAM_WEB_VITALITY,
        extractor=extract_web_vitality,
    ),
    # --- outcome organs: api surface shape ---
    Organ(
        name="endpoint_ideas",
        label="Ideas endpoint",
        description="GET /api/ideas — the primary data surface for the idea pipeline.",
        upstream=UPSTREAM_API_IDEAS,
        extractor=extract_api_ideas,
    ),
    Organ(
        name="endpoint_vitality",
        label="Vitality endpoint",
        description="GET /api/workspaces/coherence-network/vitality — the living signals shape.",
        upstream=UPSTREAM_API_VITALITY,
        extractor=extract_api_vitality,
    ),
]


def organs_by_name() -> dict[str, Organ]:
    return {o.name: o for o in ORGANS}


def organs_for_upstream(upstream: str) -> list[Organ]:
    return [o for o in ORGANS if o.upstream == upstream]


def upstreams_in_use() -> list[str]:
    """Return the distinct upstream labels any organ is currently using.

    Order is stable (first-seen-in-ORGANS), so the probe dispatcher
    issues requests in a predictable, debuggable order.
    """
    seen: list[str] = []
    for organ in ORGANS:
        if organ.upstream not in seen:
            seen.append(organ.upstream)
    return seen
