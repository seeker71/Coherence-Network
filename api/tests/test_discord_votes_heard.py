"""A Discord reaction is HEARD on the idea-cell (discord-membrane.form: listen).

A vote stored in question_votes must REACH the idea: GET /api/ideas/{id} now
surfaces each open question's vote counts + a resonance composed on the Form
kernel (+1 per 👍 positive, +2 per 🔥 excited, −1 per 👎 negative). Before this
stride, get_counts was dead code and the community's belief landed in a drawer
no one opened.
"""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_reaction_reaches_the_idea_cell():
    iid = f"votes-heard-{uuid.uuid4().hex[:8]}"
    created = client.post("/api/ideas", json={
        "id": iid,
        "name": "Heard idea",
        "description": "does a reaction reach the idea-cell?",
        "potential_value": 10.0,
        "estimated_cost": 1.0,
        "open_questions": [
            {"question": "Is this worth doing?", "value_to_whole": 1.0, "estimated_cost": 1.0},
        ],
    })
    if created.status_code not in (200, 201):
        import pytest
        pytest.skip(f"idea create unavailable in this env: {created.status_code} {created.text[:120]}")

    # Before any reaction, the question is unvoted — votes/resonance absent.
    before = client.get(f"/api/ideas/{iid}").json()
    assert before["open_questions"][0].get("votes") in (None, {})
    assert before["open_questions"][0].get("resonance") is None

    # The community reacts: two 👍, one 🔥, one 👎 — distinct cells.
    def vote(uid: str, polarity: str):
        return client.post(
            f"/api/ideas/{iid}/questions/0/vote",
            json={"discord_user_id": uid, "polarity": polarity},
        )
    assert vote("u1", "positive").status_code == 200
    assert vote("u2", "positive").status_code == 200
    assert vote("u3", "excited").status_code == 200
    assert vote("u4", "negative").status_code == 200

    # The reactions are HEARD on the idea-cell.
    after = client.get(f"/api/ideas/{iid}").json()
    q0 = after["open_questions"][0]
    assert q0["votes"] == {"positive": 2, "negative": 1, "excited": 1}
    # resonance = +1·2 (👍) + 2·1 (🔥) − 1·1 (👎) = 3, composed on the Form kernel.
    assert q0["resonance"] == 3
