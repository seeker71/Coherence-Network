"""Real tool telemetry groups into the rows the Form embodiment gate consumes.

The verdict — which lane holds a tool's body — is proven four-way by
form/form-stdlib/tests/tool-embodiment-band.fk. This test proves the other
half: the Python fan-out turns real RuntimeEvents into the exact
[lane, locality, completed, failed, runtime_ms] rows te-embody-lanes reads,
grouped by (tool, lane), with no embodiment logic on the carrier side.
"""
from types import SimpleNamespace

from app.services import runtime_service
from app.services import agent_service_usage_visibility as viz


def _ev(tool: str, executor: str, status: int, ms: float, task_id: str):
    return SimpleNamespace(
        source="worker",
        endpoint=f"tool:{tool}",
        status_code=status,
        runtime_ms=ms,
        id=f"{tool}-{executor}-{status}",
        recorded_at="2026-06-14T00:00:00Z",
        metadata={"task_id": task_id, "executor": executor, "provider": executor},
    )


def test_embodiment_rows_group_by_tool_and_lane(monkeypatch):
    # one tool, two lanes: a local Form-native lane and a remote claude lane.
    events = []
    events += [_ev("search", "form-native", 200, 30.0, "t1") for _ in range(8)]
    events += [_ev("search", "form-native", 500, 30.0, "t1") for _ in range(2)]
    events += [_ev("search", "claude", 200, 120.0, "t1") for _ in range(9)]
    events += [_ev("search", "claude", 500, 120.0, "t1") for _ in range(1)]
    monkeypatch.setattr(runtime_service, "list_events", lambda **_: events)

    summary = viz._execution_usage_summary(["t1"])
    rows_by_tool = summary["embodiment_rows_by_tool"]

    assert "search" in rows_by_tool
    rows = {r[0]: r for r in rows_by_tool["search"]}

    # every row is the exact shape te-embody-lanes reads.
    for r in rows_by_tool["search"]:
        assert len(r) == 5  # [lane, locality, completed, failed, runtime_ms]

    fn = rows["form-native"]
    assert fn[1] == "local"      # locality derived, not asserted as sovereignty
    assert fn[2] == 8 and fn[3] == 2
    assert fn[4] == 300          # 10 events (8 completed + 2 failed), 30ms each

    cl = rows["claude"]
    assert cl[1] == "remote"
    assert cl[2] == 9 and cl[3] == 1
    assert cl[4] == 1200         # 10 events, 120ms each


def test_visibility_summary_surfaces_embodiment(monkeypatch):
    monkeypatch.setattr(
        runtime_service,
        "list_events",
        lambda **_: [_ev("read_file", "form-native", 200, 5.0, "t2")],
    )
    out = viz.get_visibility_summary()
    assert "embodiment" in out
    assert out["embodiment"]["row_shape"] == ["lane", "locality", "completed", "failed", "runtime_ms"]
    assert out["embodiment"]["gate"] == "te-embody-lanes"
    assert "read_file" in out["embodiment"]["rows_by_tool"]
