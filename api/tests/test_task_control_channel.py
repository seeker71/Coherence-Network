"""Contract tests for task control channel."""

import pytest
import uuid
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_issue_command():
    task_id = f"test-task-{uuid.uuid4()}"
    response = client.post(
        f"/api/agent/tasks/{task_id}/control/issue",
        json={"command": "report", "payload": {"foo": "bar"}}
    )
    assert response.status_code == 201
    data = response.json()
    assert "command_id" in data
    assert data["task_id"] == task_id
    assert data["duplicate"] is False


def test_issue_duplicate_command():
    task_id = f"test-task-{uuid.uuid4()}"
    client_id = str(uuid.uuid4())
    
    # First issue
    response1 = client.post(
        f"/api/agent/tasks/{task_id}/control/issue",
        json={"command": "checkpoint", "client_command_id": client_id}
    )
    assert response1.status_code == 201
    id1 = response1.json()["command_id"]
    
    # Second issue (duplicate)
    response2 = client.post(
        f"/api/agent/tasks/{task_id}/control/issue",
        json={"command": "checkpoint", "client_command_id": client_id}
    )
    assert response2.status_code == 201
    data2 = response2.json()
    assert data2["command_id"] == id1
    assert data2["duplicate"] is True


def test_acknowledge_command():
    task_id = f"test-task-{uuid.uuid4()}"
    
    # Issue
    issue_res = client.post(
        f"/api/agent/tasks/{task_id}/control/issue",
        json={"command": "steer", "payload": {"new_direction": "go left"}}
    )
    command_id = issue_res.json()["command_id"]
    
    # Ack
    ack_res = client.post(
        f"/api/agent/tasks/{task_id}/control/ack",
        json={"command_id": command_id, "status": "applied", "detail": "steered left"}
    )
    assert ack_res.status_code == 201
    assert ack_res.json() == {"ok": True}


def test_resolve_permission():
    task_id = f"test-task-{uuid.uuid4()}"
    
    # Issue ask
    issue_res = client.post(
        f"/api/agent/tasks/{task_id}/control/issue",
        json={"command": "ask", "payload": {"prompt": "Can I delete this?"}}
    )
    command_id = issue_res.json()["command_id"]
    
    # Resolve
    res_res = client.post(
        f"/api/agent/tasks/{task_id}/control/permission",
        json={"command_id": command_id, "decision": "allow", "note": "Yes you can"}
    )
    assert res_res.status_code == 200
    assert res_res.json() == {"ok": True}


def test_control_sse_stream():
    task_id = f"test-task-{uuid.uuid4()}"
    
    # Issue a command
    client.post(
        f"/api/agent/tasks/{task_id}/control/issue",
        json={"command": "report"}
    )
    
    # Read stream (partial read)
    with client.stream("GET", f"/api/agent/tasks/{task_id}/control-stream") as response:
        assert response.status_code == 200
        # Check first data line
        for line in response.iter_lines():
            line_str = line.decode("utf-8")
            if line_str.startswith("data:"):
                data = json.loads(line_str[5:])
                assert data["type"] == "control_command"
                assert data["command"] == "report"
                break
            if line_str == ": ping":
                continue

import json
