from __future__ import annotations

import scripts.cursor_fact_report as fact_report


def test_routing_policy_proof_uses_current_routing_service() -> None:
    rows = fact_report._routing_policy_proof()

    assert len(rows) >= 3
    assert all(row["selected_executor"] for row in rows)
    assert all("route" in row for row in rows)
    assert any(row["selected_executor"] in {"codex", "openclaw", "claude"} for row in rows)
    assert any(row["selected_executor"] == "cursor" for row in rows)
