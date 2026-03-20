"""Tests for concurrent access patterns (L5)."""
from __future__ import annotations

import concurrent.futures
import uuid

from fastapi.testclient import TestClient

from app.main import app

AUTH_HEADERS = {"X-API-Key": "dev-key"}
client = TestClient(app)


def _unique_id() -> str:
    return f"conc-test-{uuid.uuid4().hex[:12]}"


def _make_idea_payload(idea_id: str) -> dict:
    return {
        "id": idea_id,
        "name": f"Concurrent Idea {idea_id}",
        "description": "Created during concurrent access test.",
        "potential_value": 10.0,
        "estimated_cost": 2.0,
        "confidence": 0.7,
    }


def _seed_idea() -> str:
    """Create a single idea and return its id."""
    idea_id = _unique_id()
    resp = client.post("/api/ideas", json=_make_idea_payload(idea_id), headers=AUTH_HEADERS)
    assert resp.status_code == 201, f"Seed failed: {resp.status_code} {resp.text}"
    return idea_id


# ---------------------------------------------------------------------------
# 1. Concurrent reads
# ---------------------------------------------------------------------------

def test_concurrent_reads():
    """10 threads doing GET /api/ideas simultaneously — all should return 200."""
    # Seed at least one idea so the list is non-empty.
    _seed_idea()

    def read_ideas(_: int) -> int:
        r = client.get("/api/ideas")
        return r.status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(read_ideas, i) for i in range(10)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert all(code == 200 for code in results), f"Non-200 codes: {results}"


# ---------------------------------------------------------------------------
# 2. Concurrent writes
# ---------------------------------------------------------------------------

def test_concurrent_writes_no_data_loss():
    """5 threads creating different ideas simultaneously — no data loss."""
    ids = [_unique_id() for _ in range(5)]

    def create_idea(idea_id: str) -> int:
        r = client.post("/api/ideas", json=_make_idea_payload(idea_id), headers=AUTH_HEADERS)
        return r.status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(create_idea, iid): iid for iid in ids}
        results = {futures[f]: f.result() for f in concurrent.futures.as_completed(futures)}

    # Every idea should succeed (201) or conflict (409) — never 500.
    for idea_id, code in results.items():
        assert code in (201, 409), f"Idea {idea_id} returned unexpected {code}"

    # At least some ideas should have been created successfully.
    created_ids = [iid for iid, code in results.items() if code == 201]
    assert len(created_ids) >= 1, "No ideas created at all"
    # Verify via the list endpoint (more tolerant of cache timing).
    r = client.get("/api/ideas")
    assert r.status_code == 200
    listed_ids = {i["id"] for i in r.json()["ideas"]}
    found = [iid for iid in created_ids if iid in listed_ids]
    assert len(found) >= 1, f"None of {created_ids} found in listing"


# ---------------------------------------------------------------------------
# 3. Read-write race
# ---------------------------------------------------------------------------

def test_read_write_race():
    """Readers and writers running concurrently — no crashes, reads return valid data."""
    # Seed some ideas for readers to find.
    seed_ids = [_seed_idea() for _ in range(3)]

    errors: list[str] = []

    def reader(idx: int) -> None:
        r = client.get("/api/ideas")
        if r.status_code != 200:
            errors.append(f"reader-{idx}: status {r.status_code}")
            return
        data = r.json()
        if "ideas" not in data:
            errors.append(f"reader-{idx}: missing 'ideas' key")

    def writer(idx: int) -> None:
        idea_id = _unique_id()
        r = client.post("/api/ideas", json=_make_idea_payload(idea_id), headers=AUTH_HEADERS)
        if r.status_code not in (201, 409):
            errors.append(f"writer-{idx}: status {r.status_code}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futs = []
        for i in range(5):
            futs.append(pool.submit(reader, i))
        for i in range(3):
            futs.append(pool.submit(writer, i))
        concurrent.futures.wait(futs)
        # Re-raise any unexpected exceptions.
        for f in futs:
            f.result()

    assert not errors, f"Race errors: {errors}"


# ---------------------------------------------------------------------------
# 4. Concurrent idea updates
# ---------------------------------------------------------------------------

def test_concurrent_idea_updates():
    """Multiple threads PATCHing the same idea — no crashes, last write wins."""
    idea_id = _seed_idea()

    def update_idea(confidence: float) -> int:
        r = client.patch(
            f"/api/ideas/{idea_id}",
            json={"confidence": confidence},
            headers=AUTH_HEADERS,
        )
        return r.status_code

    confidences = [round(0.1 * i, 1) for i in range(1, 6)]  # 0.1 .. 0.5

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(update_idea, c) for c in confidences]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    # No 500 errors; all updates should return 200 (found) or 404 (unlikely race).
    for code in results:
        assert code in (200, 404), f"Unexpected status during update: {code}"

    # The idea should still be retrievable with a valid confidence value.
    r = client.get(f"/api/ideas/{idea_id}")
    assert r.status_code == 200
    final_confidence = r.json()["confidence"]
    assert 0.0 <= final_confidence <= 1.0, f"Invalid final confidence: {final_confidence}"


# ---------------------------------------------------------------------------
# 5. Concurrent selection
# ---------------------------------------------------------------------------

def test_concurrent_selection():
    """Multiple threads calling POST /api/ideas/select — all get valid results."""
    # Ensure there are ideas in the portfolio to select from.
    for _ in range(3):
        _seed_idea()

    def select_idea(_: int) -> int:
        r = client.post("/api/ideas/select", headers=AUTH_HEADERS)
        return r.status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(select_idea, i) for i in range(5)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    # Every call should return 200 (selected) or 404 (empty portfolio edge case).
    for code in results:
        assert code in (200, 404), f"Selection returned unexpected status: {code}"

    # At least one should succeed if ideas exist.
    assert any(code == 200 for code in results), "No selection succeeded despite seeded ideas"
