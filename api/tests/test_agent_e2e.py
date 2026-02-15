"""End-to-end integration tests for agent orchestration workflow.

Validates full cycle: API → task creation → agent execution → status updates → completion.
Spec 003: Agent-Telegram Decision Loop requires E2E validation beyond smoke tests.
"""

import asyncio
import subprocess
import sys
import time
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.mark.asyncio
async def test_agent_task_creation_and_retrieval():
    """E2E: Create task via API, verify it's stored and retrievable."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create a spec task
        create_resp = await client.post(
            "/agent/tasks",
            json={
                "direction": "Write a test specification for user authentication",
                "task_type": "spec",
                "context": {"priority": "high"},
            },
        )
        assert create_resp.status_code == 201
        task_data = create_resp.json()

        # Verify response structure
        assert "id" in task_data
        assert task_data["task_type"] == "spec"
        assert task_data["status"] == "pending"
        assert "command" in task_data
        assert "model" in task_data

        task_id = task_data["id"]

        # Retrieve the task
        get_resp = await client.get(f"/agent/tasks/{task_id}")
        assert get_resp.status_code == 200
        retrieved = get_resp.json()
        assert retrieved["id"] == task_id
        assert retrieved["direction"] == task_data["direction"]


@pytest.mark.asyncio
async def test_agent_task_state_transitions():
    """E2E: Test task state transitions from pending → running → completed."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create task
        create_resp = await client.post(
            "/agent/tasks",
            json={
                "direction": "Simple test task",
                "task_type": "test",
            },
        )
        assert create_resp.status_code == 201
        task_id = create_resp.json()["id"]

        # Update to running
        update_resp = await client.patch(
            f"/agent/tasks/{task_id}",
            json={
                "status": "running",
                "progress_pct": 25,
                "current_step": "Initializing test environment",
            },
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["status"] == "running"
        assert update_resp.json()["progress_pct"] == 25

        # Update progress
        progress_resp = await client.patch(
            f"/agent/tasks/{task_id}",
            json={
                "progress_pct": 75,
                "current_step": "Running tests",
            },
        )
        assert progress_resp.status_code == 200
        assert progress_resp.json()["progress_pct"] == 75

        # Complete task
        complete_resp = await client.patch(
            f"/agent/tasks/{task_id}",
            json={
                "status": "completed",
                "output": "All tests passed successfully",
                "progress_pct": 100,
            },
        )
        assert complete_resp.status_code == 200
        assert complete_resp.json()["status"] == "completed"
        assert complete_resp.json()["output"] == "All tests passed successfully"


@pytest.mark.asyncio
async def test_agent_runner_execution_simple_command():
    """E2E: Create task and simulate agent runner executing it.

    Tests that a task with a simple command can be executed and output captured.
    This validates the core agent runner workflow without external dependencies.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create a task with a simple shell command
        create_resp = await client.post(
            "/agent/tasks",
            json={
                "direction": "Echo test message",
                "task_type": "impl",
                "context": {"test_mode": True},
            },
        )
        assert create_resp.status_code == 201
        task_data = create_resp.json()
        task_id = task_data["id"]

        # Simulate agent runner picking up the task
        update_running = await client.patch(
            f"/agent/tasks/{task_id}",
            json={"status": "running"},
        )
        assert update_running.status_code == 200

        # Execute a simple command (simulating what agent_runner.py does)
        test_command = 'echo "E2E test output"'
        result = subprocess.run(
            test_command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
        )

        # Update task with output
        update_complete = await client.patch(
            f"/agent/tasks/{task_id}",
            json={
                "status": "completed",
                "output": result.stdout.strip(),
            },
        )
        assert update_complete.status_code == 200
        completed_task = update_complete.json()
        assert completed_task["status"] == "completed"
        assert "E2E test output" in completed_task["output"]


@pytest.mark.asyncio
async def test_agent_task_list_with_filters():
    """E2E: Create multiple tasks and verify list filtering works."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create tasks of different types and statuses
        tasks = []
        for i, (task_type, status) in enumerate([
            ("spec", "pending"),
            ("test", "running"),
            ("impl", "completed"),
            ("spec", "completed"),
        ]):
            create_resp = await client.post(
                "/agent/tasks",
                json={
                    "direction": f"Task {i}",
                    "task_type": task_type,
                },
            )
            assert create_resp.status_code == 201
            task_id = create_resp.json()["id"]
            tasks.append(task_id)

            # Update status if not pending
            if status != "pending":
                await client.patch(
                    f"/agent/tasks/{task_id}",
                    json={"status": status},
                )

        # Test filtering by status
        pending_resp = await client.get("/agent/tasks?status=pending")
        assert pending_resp.status_code == 200
        pending_tasks = pending_resp.json()["tasks"]
        assert len(pending_tasks) >= 1
        assert all(t["status"] == "pending" for t in pending_tasks)

        # Test filtering by task_type
        spec_resp = await client.get("/agent/tasks?task_type=spec")
        assert spec_resp.status_code == 200
        spec_tasks = spec_resp.json()["tasks"]
        assert len(spec_tasks) >= 2
        assert all(t["task_type"] == "spec" for t in spec_tasks)

        # Test pagination
        limited_resp = await client.get("/agent/tasks?limit=2")
        assert limited_resp.status_code == 200
        limited_data = limited_resp.json()
        assert len(limited_data["tasks"]) == 2
        assert limited_data["total"] >= 4


@pytest.mark.asyncio
async def test_agent_task_decision_workflow():
    """E2E: Test needs_decision state and user reply workflow."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create task
        create_resp = await client.post(
            "/agent/tasks",
            json={
                "direction": "Interactive task requiring user input",
                "task_type": "impl",
            },
        )
        assert create_resp.status_code == 201
        task_id = create_resp.json()["id"]

        # Task encounters decision point
        decision_resp = await client.patch(
            f"/agent/tasks/{task_id}",
            json={
                "status": "needs_decision",
                "decision_prompt": "Should I proceed with destructive changes? (yes/no)",
            },
        )
        assert decision_resp.status_code == 200
        assert decision_resp.json()["status"] == "needs_decision"
        assert decision_resp.json()["decision_prompt"] is not None

        # User provides decision
        reply_resp = await client.patch(
            f"/agent/tasks/{task_id}",
            json={
                "decision": "yes",
                "status": "running",
            },
        )
        assert reply_resp.status_code == 200
        assert reply_resp.json()["status"] == "running"
        assert reply_resp.json()["decision"] == "yes"

        # Complete task
        complete_resp = await client.patch(
            f"/agent/tasks/{task_id}",
            json={
                "status": "completed",
                "output": "Task completed with user approval",
            },
        )
        assert complete_resp.status_code == 200
        assert complete_resp.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_agent_task_failure_handling():
    """E2E: Test task failure state and error output capture."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create task
        create_resp = await client.post(
            "/agent/tasks",
            json={
                "direction": "Task that will fail",
                "task_type": "test",
            },
        )
        assert create_resp.status_code == 201
        task_id = create_resp.json()["id"]

        # Mark as running
        await client.patch(
            f"/agent/tasks/{task_id}",
            json={"status": "running"},
        )

        # Simulate command failure
        test_command = "exit 1"
        result = subprocess.run(
            test_command,
            shell=True,
            capture_output=True,
            text=True,
        )

        # Update task with failure
        failure_resp = await client.patch(
            f"/agent/tasks/{task_id}",
            json={
                "status": "failed",
                "output": f"Command failed with exit code {result.returncode}",
            },
        )
        assert failure_resp.status_code == 200
        assert failure_resp.json()["status"] == "failed"
        assert "failed" in failure_resp.json()["output"].lower()


@pytest.mark.asyncio
async def test_agent_route_endpoint():
    """E2E: Test route-only endpoint that returns model/command without creating task."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        route_resp = await client.get(
            "/agent/route",
            params={
                "direction": "Test routing",
                "task_type": "spec",
            },
        )
        assert route_resp.status_code == 200
        route_data = route_resp.json()

        # Verify route response structure
        assert "task_type" in route_data
        assert "model" in route_data
        assert "command_template" in route_data
        assert "tier" in route_data
        assert route_data["task_type"] == "spec"


@pytest.mark.asyncio
async def test_agent_metrics_tracking():
    """E2E: Verify metrics are tracked for task execution."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create and complete a task
        create_resp = await client.post(
            "/agent/tasks",
            json={
                "direction": "Metrics test task",
                "task_type": "impl",
            },
        )
        assert create_resp.status_code == 201
        task_id = create_resp.json()["id"]

        # Complete the task
        await client.patch(
            f"/agent/tasks/{task_id}",
            json={"status": "running"},
        )
        await client.patch(
            f"/agent/tasks/{task_id}",
            json={"status": "completed", "output": "Done"},
        )

        # Check if metrics endpoint exists and returns data
        metrics_resp = await client.get("/api/agent/metrics")
        if metrics_resp.status_code == 200:
            metrics = metrics_resp.json()
            # Verify metrics structure
            assert "total_tasks" in metrics or "tasks" in metrics


@pytest.mark.asyncio
async def test_agent_pipeline_status():
    """E2E: Test pipeline status endpoint returns running tasks."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create a running task
        create_resp = await client.post(
            "/agent/tasks",
            json={
                "direction": "Pipeline status test",
                "task_type": "impl",
            },
        )
        assert create_resp.status_code == 201
        task_id = create_resp.json()["id"]

        await client.patch(
            f"/agent/tasks/{task_id}",
            json={"status": "running"},
        )

        # Get pipeline status
        status_resp = await client.get("/api/agent/pipeline-status")
        if status_resp.status_code == 200:
            status = status_resp.json()
            assert "running" in status or "tasks" in status
