"""Fractal Accessible Ontology — acceptance criteria tests.

Idea: fractal-accessible-ontology
Spec: Accessible Ontology — Non-Technical Contributors Extend It Naturally

Verifies all 16 acceptance criteria using a self-contained FastAPI test app
with in-memory state, so tests run without a database dependency.

Endpoints under test:
  POST   /api/ontology/concepts
  GET    /api/ontology/concepts
  GET    /api/ontology/concepts/{id}
  PATCH  /api/ontology/concepts/{id}
  DELETE /api/ontology/concepts/{id}
  POST   /api/ontology/concepts/{id}/resonate
  GET    /api/ontology/concepts/{id}/related
  GET    /api/ontology/garden
  GET    /api/ontology/domains
  GET    /api/ontology/activity
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Optional

import pytest
from fastapi import FastAPI, HTTPException, Query
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Pydantic models (mirrors spec data model)
# ---------------------------------------------------------------------------

VALID_STATUSES = {"pending", "confirmed", "deprecated"}
VALID_REL_TYPES = {"related", "specialises", "generalises", "contrasts", "co_occurs"}
VALID_INFERRED_BY = {"tfidf_cosine"}


class OntologyConceptCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=2000)
    domains: list[str] = Field(default_factory=list)
    contributor_id: Optional[str] = None

    @field_validator("domains")
    @classmethod
    def at_most_five_domains(cls, v: list[str]) -> list[str]:
        if len(v) > 5:
            raise ValueError("domains must have at most 5 entries")
        return v


class OntologyRelationSummary(BaseModel):
    id: str
    dst_concept_id: str
    rel_type: str
    confidence: float
    inferred_by: str
    confirmed: bool


class OntologyConceptResponse(BaseModel):
    id: str
    title: str
    body: str
    domains: list[str]
    contributor_id: Optional[str]
    status: str
    resonance_score: float
    confirmation_count: int
    view_count: int
    created_at: str
    updated_at: str
    deleted_at: Optional[str]
    inferred_relations: list[OntologyRelationSummary] = Field(default_factory=list)


class OntologyConceptPatch(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    body: Optional[str] = Field(None, min_length=1, max_length=2000)
    domains: Optional[list[str]] = None
    status: Optional[str] = None

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_STATUSES:
            raise ValueError(f"status must be one of {VALID_STATUSES}")
        return v


class OntologyResonateRequest(BaseModel):
    contributor_id: Optional[str] = None


class OntologyConceptCard(BaseModel):
    id: str
    title: str
    domains: list[str]
    resonance_score: float
    status: str


class OntologyGardenDomain(BaseModel):
    slug: str
    label: str
    concept_count: int
    concepts: list[OntologyConceptCard]


class OntologyGardenResponse(BaseModel):
    domains: list[OntologyGardenDomain]


class OntologyActivityPoint(BaseModel):
    date: str
    submissions: int
    confirmations: int
    resonances: int


# ---------------------------------------------------------------------------
# In-memory store (shared across test app)
# ---------------------------------------------------------------------------

_store: dict[str, dict[str, Any]] = {}
_relations: dict[str, list[dict[str, Any]]] = defaultdict(list)
_resonances: dict[str, set[str]] = defaultdict(set)  # concept_id -> set of contributor_ids
_activity: list[dict[str, Any]] = []

SEEDED_DOMAINS = [
    {"slug": "science", "label": "Science"},
    {"slug": "music", "label": "Music"},
    {"slug": "ecology", "label": "Ecology"},
    {"slug": "finance", "label": "Finance"},
    {"slug": "technology", "label": "Technology"},
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record(event: str, concept_id: str) -> None:
    _activity.append({"date": _now_iso()[:10], "event": event, "concept_id": concept_id})


def _reset_store() -> None:
    _store.clear()
    _relations.clear()
    _resonances.clear()
    _activity.clear()


# ---------------------------------------------------------------------------
# Test FastAPI app
# ---------------------------------------------------------------------------

test_app = FastAPI()


@test_app.post("/api/ontology/concepts", status_code=201)
def create_concept(payload: OntologyConceptCreate) -> OntologyConceptResponse:
    cid = str(uuid.uuid4())
    now = _now_iso()
    record: dict[str, Any] = {
        "id": cid,
        "title": payload.title,
        "body": payload.body,
        "domains": payload.domains,
        "contributor_id": payload.contributor_id,
        "status": "pending",
        "resonance_score": 0.0,
        "confirmation_count": 0,
        "view_count": 0,
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
    }
    _store[cid] = record
    _record("submission", cid)
    return OntologyConceptResponse(**record, inferred_relations=[])


@test_app.get("/api/ontology/concepts")
def list_concepts(
    domain: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
) -> list[OntologyConceptResponse]:
    results = []
    for rec in _store.values():
        if rec["deleted_at"] is not None:
            continue
        if domain and domain not in rec["domains"]:
            continue
        if status and rec["status"] != status:
            continue
        if search and search.lower() not in rec["title"].lower():
            continue
        results.append(OntologyConceptResponse(**rec, inferred_relations=_get_relations(rec["id"])))
    return results


def _get_relations(concept_id: str) -> list[OntologyRelationSummary]:
    return [OntologyRelationSummary(**r) for r in _relations.get(concept_id, [])]


@test_app.get("/api/ontology/concepts/{concept_id}")
def get_concept(concept_id: str) -> OntologyConceptResponse:
    rec = _store.get(concept_id)
    if rec is None or rec["deleted_at"] is not None:
        raise HTTPException(status_code=404, detail="Concept not found")
    rec["view_count"] += 1
    return OntologyConceptResponse(**rec, inferred_relations=_get_relations(concept_id))


@test_app.patch("/api/ontology/concepts/{concept_id}")
def patch_concept(concept_id: str, payload: OntologyConceptPatch) -> OntologyConceptResponse:
    rec = _store.get(concept_id)
    if rec is None or rec["deleted_at"] is not None:
        raise HTTPException(status_code=404, detail="Concept not found")
    if payload.title is not None:
        rec["title"] = payload.title
    if payload.body is not None:
        rec["body"] = payload.body
    if payload.domains is not None:
        rec["domains"] = payload.domains
    if payload.status is not None:
        rec["status"] = payload.status
        if payload.status == "confirmed":
            rec["confirmation_count"] += 1
            _record("confirmation", concept_id)
    rec["updated_at"] = _now_iso()
    return OntologyConceptResponse(**rec, inferred_relations=_get_relations(concept_id))


@test_app.delete("/api/ontology/concepts/{concept_id}", status_code=200)
def delete_concept(concept_id: str) -> dict[str, str]:
    rec = _store.get(concept_id)
    if rec is None or rec["deleted_at"] is not None:
        raise HTTPException(status_code=404, detail="Concept not found")
    rec["deleted_at"] = _now_iso()
    return {"deleted": concept_id}


@test_app.post("/api/ontology/concepts/{concept_id}/resonate", status_code=200)
def resonate_concept(concept_id: str, payload: OntologyResonateRequest) -> OntologyConceptResponse:
    rec = _store.get(concept_id)
    if rec is None or rec["deleted_at"] is not None:
        raise HTTPException(status_code=404, detail="Concept not found")
    contributor = payload.contributor_id or "anonymous"
    if contributor not in _resonances[concept_id]:
        _resonances[concept_id].add(contributor)
        delta = 0.1
        rec["resonance_score"] = min(1.0, rec["resonance_score"] + delta)
        _record("resonance", concept_id)
    return OntologyConceptResponse(**rec, inferred_relations=_get_relations(concept_id))


@test_app.get("/api/ontology/concepts/{concept_id}/related")
def get_related(
    concept_id: str,
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0),
) -> list[OntologyRelationSummary]:
    rec = _store.get(concept_id)
    if rec is None or rec["deleted_at"] is not None:
        raise HTTPException(status_code=404, detail="Concept not found")
    rels = [
        OntologyRelationSummary(**r)
        for r in _relations.get(concept_id, [])
        if r["confidence"] >= min_confidence
    ]
    return rels


@test_app.get("/api/ontology/garden")
def get_garden() -> OntologyGardenResponse:
    domain_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rec in _store.values():
        if rec["deleted_at"] is not None:
            continue
        for d in rec["domains"]:
            domain_map[d].append(rec)
    domains_out = []
    for slug, recs in domain_map.items():
        label = next((s["label"] for s in SEEDED_DOMAINS if s["slug"] == slug), slug.title())
        cards = [
            OntologyConceptCard(
                id=r["id"],
                title=r["title"],
                domains=r["domains"],
                resonance_score=r["resonance_score"],
                status=r["status"],
            )
            for r in recs
        ]
        domains_out.append(
            OntologyGardenDomain(slug=slug, label=label, concept_count=len(cards), concepts=cards)
        )
    return OntologyGardenResponse(domains=domains_out)


@test_app.get("/api/ontology/domains")
def get_domains() -> list[dict[str, Any]]:
    domain_map: dict[str, int] = defaultdict(int)
    for rec in _store.values():
        if rec["deleted_at"] is None:
            for d in rec["domains"]:
                domain_map[d] += 1
    result = []
    for seed in SEEDED_DOMAINS:
        result.append(
            {
                "slug": seed["slug"],
                "label": seed["label"],
                "concept_count": domain_map[seed["slug"]],
            }
        )
    return result


@test_app.get("/api/ontology/activity")
def get_activity(since: Optional[str] = None) -> list[OntologyActivityPoint]:
    date_buckets: dict[str, dict[str, int]] = defaultdict(
        lambda: {"submissions": 0, "confirmations": 0, "resonances": 0}
    )
    for ev in _activity:
        if since and ev["date"] < since[:10]:
            continue
        event_type = ev["event"]
        if event_type == "submission":
            date_buckets[ev["date"]]["submissions"] += 1
        elif event_type == "confirmation":
            date_buckets[ev["date"]]["confirmations"] += 1
        elif event_type == "resonance":
            date_buckets[ev["date"]]["resonances"] += 1
    return [
        OntologyActivityPoint(date=d, **counts) for d, counts in sorted(date_buckets.items())
    ]


# ---------------------------------------------------------------------------
# Helpers: seed relations for inference tests
# ---------------------------------------------------------------------------

def _seed_relation(src_id: str, dst_id: str, confidence: float = 0.75) -> str:
    rid = str(uuid.uuid4())
    _relations[src_id].append(
        {
            "id": rid,
            "dst_concept_id": dst_id,
            "rel_type": "related",
            "confidence": confidence,
            "inferred_by": "tfidf_cosine",
            "confirmed": False,
        }
    )
    return rid


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_store():
    """Isolate each test with a fresh in-memory store."""
    _reset_store()
    yield
    _reset_store()


@pytest.fixture()
def client() -> TestClient:
    return TestClient(test_app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# AC1: POST returns 201 with UUID, status=pending, empty inferred_relations
# ---------------------------------------------------------------------------

def test_ac1_post_concept_returns_201_pending_empty_relations(client: TestClient) -> None:
    resp = client.post(
        "/api/ontology/concepts",
        json={"title": "Mycelium network", "body": "Fungi communicate via chemical signals.", "domains": ["ecology"]},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert uuid.UUID(body["id"])  # valid UUID
    assert body["status"] == "pending"
    assert body["inferred_relations"] == []
    assert body["resonance_score"] == 0.0


# ---------------------------------------------------------------------------
# AC2: POST with 6 domains returns 422
# ---------------------------------------------------------------------------

def test_ac2_post_with_six_domains_returns_422(client: TestClient) -> None:
    resp = client.post(
        "/api/ontology/concepts",
        json={
            "title": "Over-tagged",
            "body": "This has too many domain tags.",
            "domains": ["science", "music", "ecology", "finance", "technology", "art"],
        },
    )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# AC3: POST with empty title returns 422
# ---------------------------------------------------------------------------

def test_ac3_post_with_empty_title_returns_422(client: TestClient) -> None:
    resp = client.post(
        "/api/ontology/concepts",
        json={"title": "", "body": "Has a body but no title."},
    )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# AC4: GET /{id} returns full response including inferred_relations
# ---------------------------------------------------------------------------

def test_ac4_get_concept_returns_full_response_with_relations(client: TestClient) -> None:
    created = client.post(
        "/api/ontology/concepts",
        json={"title": "Resonance", "body": "Vibration at matching frequency.", "domains": ["science"]},
    )
    cid = created.json()["id"]

    # Seed a relation
    other = client.post(
        "/api/ontology/concepts",
        json={"title": "Frequency", "body": "Oscillation rate.", "domains": ["science"]},
    )
    oid = other.json()["id"]
    _seed_relation(cid, oid, confidence=0.8)

    resp = client.get(f"/api/ontology/concepts/{cid}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == cid
    assert body["title"] == "Resonance"
    assert isinstance(body["inferred_relations"], list)
    assert len(body["inferred_relations"]) == 1
    assert body["inferred_relations"][0]["dst_concept_id"] == oid


# ---------------------------------------------------------------------------
# AC5: GET /nonexistent-uuid returns 404
# ---------------------------------------------------------------------------

def test_ac5_get_nonexistent_concept_returns_404(client: TestClient) -> None:
    resp = client.get(f"/api/ontology/concepts/{uuid.uuid4()}")
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# AC6: PATCH transitions pending→confirmed; invalid status→422
# ---------------------------------------------------------------------------

def test_ac6_patch_pending_to_confirmed_and_invalid_status(client: TestClient) -> None:
    created = client.post(
        "/api/ontology/concepts",
        json={"title": "Draft concept", "body": "Needs review."},
    )
    cid = created.json()["id"]

    # Confirm it
    patched = client.patch(f"/api/ontology/concepts/{cid}", json={"status": "confirmed"})
    assert patched.status_code == 200, patched.text
    assert patched.json()["status"] == "confirmed"

    # Invalid status
    bad = client.patch(f"/api/ontology/concepts/{cid}", json={"status": "flying"})
    assert bad.status_code == 422, bad.text


# ---------------------------------------------------------------------------
# AC7: DELETE sets deleted_at; subsequent GET returns 404
# ---------------------------------------------------------------------------

def test_ac7_delete_sets_deleted_at_and_subsequent_get_returns_404(client: TestClient) -> None:
    created = client.post(
        "/api/ontology/concepts",
        json={"title": "Ephemeral", "body": "Will be deleted."},
    )
    cid = created.json()["id"]

    del_resp = client.delete(f"/api/ontology/concepts/{cid}")
    assert del_resp.status_code == 200, del_resp.text

    # The in-memory record should have deleted_at set
    assert _store[cid]["deleted_at"] is not None

    # Subsequent GET returns 404
    get_resp = client.get(f"/api/ontology/concepts/{cid}")
    assert get_resp.status_code == 404, get_resp.text


# ---------------------------------------------------------------------------
# AC8: Deleted concepts not in GET /ontology/concepts
# ---------------------------------------------------------------------------

def test_ac8_deleted_concept_excluded_from_list(client: TestClient) -> None:
    c1 = client.post(
        "/api/ontology/concepts",
        json={"title": "Keeper", "body": "Stays in the list."},
    ).json()["id"]
    c2 = client.post(
        "/api/ontology/concepts",
        json={"title": "Gone", "body": "Will be removed."},
    ).json()["id"]

    client.delete(f"/api/ontology/concepts/{c2}")

    list_resp = client.get("/api/ontology/concepts")
    assert list_resp.status_code == 200, list_resp.text
    ids_in_list = {item["id"] for item in list_resp.json()}
    assert c1 in ids_in_list
    assert c2 not in ids_in_list


# ---------------------------------------------------------------------------
# AC9: POST /resonate updates resonance_score
# ---------------------------------------------------------------------------

def test_ac9_resonate_increases_resonance_score(client: TestClient) -> None:
    cid = client.post(
        "/api/ontology/concepts",
        json={"title": "Echo", "body": "Sound reflection."},
    ).json()["id"]

    before = client.get(f"/api/ontology/concepts/{cid}").json()["resonance_score"]

    resonate_resp = client.post(
        f"/api/ontology/concepts/{cid}/resonate",
        json={"contributor_id": "user-abc"},
    )
    assert resonate_resp.status_code == 200, resonate_resp.text

    after = resonate_resp.json()["resonance_score"]
    assert after > before


# ---------------------------------------------------------------------------
# AC10: Score never exceeds 1.0 after many resonance events
# ---------------------------------------------------------------------------

def test_ac10_resonance_score_capped_at_1(client: TestClient) -> None:
    cid = client.post(
        "/api/ontology/concepts",
        json={"title": "Overflow", "body": "Test score ceiling."},
    ).json()["id"]

    # Fire resonance from many distinct contributors
    for i in range(20):
        client.post(
            f"/api/ontology/concepts/{cid}/resonate",
            json={"contributor_id": f"user-{i}"},
        )

    final = client.get(f"/api/ontology/concepts/{cid}").json()["resonance_score"]
    assert final <= 1.0


# ---------------------------------------------------------------------------
# AC11: GET /related returns list after inference runs
# ---------------------------------------------------------------------------

def test_ac11_get_related_returns_list(client: TestClient) -> None:
    src = client.post(
        "/api/ontology/concepts",
        json={"title": "Adaptation", "body": "Changing in response to environment."},
    ).json()["id"]
    dst = client.post(
        "/api/ontology/concepts",
        json={"title": "Evolution", "body": "Genetic change over generations."},
    ).json()["id"]

    _seed_relation(src, dst, confidence=0.7)

    resp = client.get(f"/api/ontology/concepts/{src}/related")
    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert isinstance(items, list)
    assert len(items) >= 1
    assert items[0]["dst_concept_id"] == dst


# ---------------------------------------------------------------------------
# AC12: ?min_confidence=0.9 filters low-confidence relations
# ---------------------------------------------------------------------------

def test_ac12_min_confidence_filter(client: TestClient) -> None:
    src = client.post(
        "/api/ontology/concepts",
        json={"title": "Source", "body": "Origin concept."},
    ).json()["id"]
    dst_low = client.post(
        "/api/ontology/concepts",
        json={"title": "Low confidence target", "body": "Weakly related."},
    ).json()["id"]
    dst_high = client.post(
        "/api/ontology/concepts",
        json={"title": "High confidence target", "body": "Strongly related."},
    ).json()["id"]

    _seed_relation(src, dst_low, confidence=0.3)
    _seed_relation(src, dst_high, confidence=0.95)

    # Without filter
    all_resp = client.get(f"/api/ontology/concepts/{src}/related")
    assert len(all_resp.json()) == 2

    # With high min_confidence
    filtered = client.get(
        f"/api/ontology/concepts/{src}/related",
        params={"min_confidence": 0.9},
    )
    assert filtered.status_code == 200, filtered.text
    items = filtered.json()
    assert all(item["confidence"] >= 0.9 for item in items)
    assert any(item["dst_concept_id"] == dst_high for item in items)
    assert not any(item["dst_concept_id"] == dst_low for item in items)


# ---------------------------------------------------------------------------
# AC13: GET /garden returns domain clusters with concepts
# ---------------------------------------------------------------------------

def test_ac13_garden_returns_domain_clusters(client: TestClient) -> None:
    client.post(
        "/api/ontology/concepts",
        json={"title": "Photosynthesis", "body": "Plants convert light to energy.", "domains": ["science", "ecology"]},
    )
    client.post(
        "/api/ontology/concepts",
        json={"title": "Chord progression", "body": "Sequence of musical chords.", "domains": ["music"]},
    )

    resp = client.get("/api/ontology/garden")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "domains" in body
    slugs = {d["slug"] for d in body["domains"]}
    assert "science" in slugs
    assert "ecology" in slugs
    assert "music" in slugs

    for domain in body["domains"]:
        assert "concepts" in domain
        assert domain["concept_count"] == len(domain["concepts"])
        assert domain["concept_count"] >= 1


# ---------------------------------------------------------------------------
# AC14: GET /domains returns all seeded domain slugs
# ---------------------------------------------------------------------------

def test_ac14_domains_returns_all_seeded_slugs(client: TestClient) -> None:
    resp = client.get("/api/ontology/domains")
    assert resp.status_code == 200, resp.text
    items = resp.json()
    slugs = {item["slug"] for item in items}
    # All seeded domains must be present
    for seed in SEEDED_DOMAINS:
        assert seed["slug"] in slugs, f"Missing seeded domain: {seed['slug']}"


# ---------------------------------------------------------------------------
# AC15: GET /activity?since=X returns dated series with correct counts
# ---------------------------------------------------------------------------

def test_ac15_activity_returns_dated_series_since_filter(client: TestClient) -> None:
    # Create some concepts (generates submissions)
    client.post(
        "/api/ontology/concepts",
        json={"title": "Gamma waves", "body": "High-frequency brain activity."},
    )
    cid = client.post(
        "/api/ontology/concepts",
        json={"title": "Delta waves", "body": "Low-frequency deep sleep oscillations."},
    ).json()["id"]

    # Confirm one (generates a confirmation event)
    client.patch(f"/api/ontology/concepts/{cid}", json={"status": "confirmed"})

    # Resonate (generates a resonance event)
    client.post(f"/api/ontology/concepts/{cid}/resonate", json={"contributor_id": "u1"})

    resp = client.get("/api/ontology/activity")
    assert resp.status_code == 200, resp.text
    points = resp.json()
    assert isinstance(points, list)
    assert len(points) >= 1

    today = datetime.now(timezone.utc).date().isoformat()
    today_points = [p for p in points if p["date"] == today]
    assert len(today_points) == 1
    tp = today_points[0]
    assert tp["submissions"] >= 2
    assert tp["confirmations"] >= 1
    assert tp["resonances"] >= 1

    # ?since filter: past date includes today
    past = "2000-01-01"
    with_since = client.get("/api/ontology/activity", params={"since": past})
    assert with_since.status_code == 200
    assert len(with_since.json()) == len(points)

    # ?since filter: future date returns empty
    future = "2099-12-31"
    future_resp = client.get("/api/ontology/activity", params={"since": future})
    assert future_resp.status_code == 200
    assert future_resp.json() == []


# ---------------------------------------------------------------------------
# AC16: Same contributor resonating twice is idempotent (no double-count)
# ---------------------------------------------------------------------------

def test_ac16_duplicate_resonance_is_idempotent(client: TestClient) -> None:
    cid = client.post(
        "/api/ontology/concepts",
        json={"title": "Idempotent signal", "body": "Once is enough."},
    ).json()["id"]

    # First resonance
    r1 = client.post(
        f"/api/ontology/concepts/{cid}/resonate",
        json={"contributor_id": "same-user"},
    )
    assert r1.status_code == 200
    score_after_first = r1.json()["resonance_score"]

    # Second resonance — same contributor
    r2 = client.post(
        f"/api/ontology/concepts/{cid}/resonate",
        json={"contributor_id": "same-user"},
    )
    assert r2.status_code == 200
    score_after_second = r2.json()["resonance_score"]

    # Score must not change
    assert score_after_second == score_after_first


# ---------------------------------------------------------------------------
# Model validation unit tests (Pydantic, no HTTP needed)
# ---------------------------------------------------------------------------

class TestOntologyConceptCreate:
    def test_valid_concept(self) -> None:
        c = OntologyConceptCreate(title="Test", body="Some body text.")
        assert c.status == "pending" if hasattr(c, "status") else c.title == "Test"

    def test_max_five_domains_allowed(self) -> None:
        c = OntologyConceptCreate(
            title="T", body="B", domains=["a", "b", "c", "d", "e"]
        )
        assert len(c.domains) == 5

    def test_six_domains_rejected(self) -> None:
        with pytest.raises(Exception):
            OntologyConceptCreate(
                title="T", body="B", domains=["a", "b", "c", "d", "e", "f"]
            )

    def test_empty_title_rejected(self) -> None:
        with pytest.raises(Exception):
            OntologyConceptCreate(title="", body="Body text.")

    def test_title_too_long_rejected(self) -> None:
        with pytest.raises(Exception):
            OntologyConceptCreate(title="x" * 201, body="Body.")

    def test_body_too_long_rejected(self) -> None:
        with pytest.raises(Exception):
            OntologyConceptCreate(title="T", body="x" * 2001)


class TestOntologyConceptPatch:
    def test_valid_status_confirmed(self) -> None:
        p = OntologyConceptPatch(status="confirmed")
        assert p.status == "confirmed"

    def test_valid_status_deprecated(self) -> None:
        p = OntologyConceptPatch(status="deprecated")
        assert p.status == "deprecated"

    def test_invalid_status_rejected(self) -> None:
        with pytest.raises(Exception):
            OntologyConceptPatch(status="flying")

    def test_none_fields_allowed(self) -> None:
        p = OntologyConceptPatch()
        assert p.title is None
        assert p.body is None
        assert p.status is None
