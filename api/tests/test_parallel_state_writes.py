from __future__ import annotations

import json
import multiprocessing as mp
import os
from pathlib import Path


def _agent_runner_records_worker(run_records_path: str, worker_idx: int, writes_per_worker: int) -> None:
    from scripts import agent_runner

    agent_runner.RUN_RECORDS_FILE = run_records_path
    for offset in range(writes_per_worker):
        run_id = f"run-{worker_idx}-{offset}"
        agent_runner._record_run_update(
            run_id,
            {
                "task_id": f"task-{worker_idx}-{offset}",
                "attempt": offset + 1,
                "status": "running",
            },
        )


def _run_state_worker(root_dir: str, worker_idx: int, claims_per_worker: int) -> None:
    os.environ["AGENT_RUN_STATE_DATABASE_URL"] = ""
    os.environ["DATABASE_URL"] = ""
    from app.services import agent_run_state_service

    root = Path(root_dir)
    agent_run_state_service._repo_root = lambda: root
    for offset in range(claims_per_worker):
        task_id = f"task-{worker_idx}-{offset}"
        run_id = f"run-{worker_idx}-{offset}"
        worker_id = f"worker-{worker_idx}"
        agent_run_state_service.claim_run_state(
            task_id=task_id,
            run_id=run_id,
            worker_id=worker_id,
            lease_seconds=60,
            attempt=1,
        )
        agent_run_state_service.update_run_state(
            task_id=task_id,
            run_id=run_id,
            worker_id=worker_id,
            patch={"status": "completed"},
            require_owner=True,
        )


def _runner_registry_worker(root_dir: str, worker_idx: int, beats_per_worker: int) -> None:
    os.environ["AGENT_RUNNER_REGISTRY_DATABASE_URL"] = ""
    os.environ["DATABASE_URL"] = ""
    from app.services import agent_runner_registry_service

    root = Path(root_dir)
    agent_runner_registry_service._repo_root = lambda: root
    for offset in range(beats_per_worker):
        agent_runner_registry_service.heartbeat_runner(
            runner_id=f"runner-{worker_idx}-{offset}",
            status="running",
            host="localhost",
            pid=1000 + worker_idx,
            version="test",
            active_task_id=f"task-{worker_idx}-{offset}",
            active_run_id=f"run-{worker_idx}-{offset}",
            lease_seconds=30,
        )


def _run_workers(target, args_factory, *, workers: int) -> None:
    ctx = mp.get_context("spawn")
    processes = []
    for idx in range(workers):
        process = ctx.Process(target=target, args=args_factory(idx))
        process.start()
        processes.append(process)
    for process in processes:
        process.join(timeout=30)
        assert process.exitcode == 0


def test_parallel_agent_runner_run_records_writes_are_safe(tmp_path: Path) -> None:
    run_records_path = tmp_path / "logs" / "agent_runner_runs.json"
    _run_workers(
        _agent_runner_records_worker,
        lambda idx: (str(run_records_path), idx, 40),
        workers=4,
    )
    payload = json.loads(run_records_path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    assert isinstance(payload.get("runs"), list)
    assert len(payload["runs"]) > 0
    assert not list(run_records_path.parent.glob(f"{run_records_path.name}.*.tmp"))


def test_parallel_run_state_local_writes_are_safe(tmp_path: Path) -> None:
    _run_workers(
        _run_state_worker,
        lambda idx: (str(tmp_path), idx, 20),
        workers=4,
    )
    run_state_path = tmp_path / "logs" / "agent_run_state.json"
    payload = json.loads(run_state_path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    assert isinstance(payload.get("tasks"), dict)
    assert len(payload["tasks"]) > 0
    assert not list(run_state_path.parent.glob("agent_run_state.json.*.tmp"))


def test_parallel_runner_registry_local_writes_are_safe(tmp_path: Path) -> None:
    _run_workers(
        _runner_registry_worker,
        lambda idx: (str(tmp_path), idx, 20),
        workers=4,
    )
    registry_path = tmp_path / "logs" / "agent_runners.json"
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    assert isinstance(payload.get("runners"), dict)
    assert len(payload["runners"]) > 0
    assert not list(registry_path.parent.glob("agent_runners.json.*.tmp"))
