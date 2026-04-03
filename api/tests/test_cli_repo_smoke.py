from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import threading
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import uvicorn

from app.main import app
from app.services import graph_service

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI_ENTRYPOINT = REPO_ROOT / "cli" / "bin" / "cc.mjs"
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def _serve_app() -> str:
    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None  # type: ignore[assignment]
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while not server.started:
        if not thread.is_alive():
            raise RuntimeError("uvicorn test server exited before startup")
        if time.time() > deadline:
            raise RuntimeError("timed out waiting for uvicorn test server")
        time.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def _run_cli(api_base: str, *args: str) -> str:
    env = os.environ.copy()
    env["COHERENCE_API_URL"] = api_base
    env.pop("COHERENCE_HUB_URL", None)
    completed = subprocess.run(
        ["node", str(CLI_ENTRYPOINT), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
        env=env,
    )
    output = ANSI_RE.sub("", completed.stdout)
    assert completed.returncode == 0, completed.stderr or output
    return output


def test_repo_cli_reports_honest_empty_states() -> None:
    with _serve_app() as api_base:
        nodes_output = _run_cli(api_base, "nodes")
        providers_output = _run_cli(api_base, "providers", "stats")

    assert "FEDERATION NODES" in nodes_output
    assert "No nodes registered." in nodes_output
    assert "PROVIDER STATS" in providers_output
    assert "No provider measurements found." in providers_output


def test_repo_cli_lists_seeded_snapshot_entities() -> None:
    contributor_id = str(uuid4())
    idea_id = f"cli-smoke-idea-{uuid4().hex[:8]}"
    graph_service.create_node(
        id=f"contributor:cli-smoke-{contributor_id}",
        type="contributor",
        name="CLI Smoke User",
        description="HUMAN contributor",
        phase="water",
        properties={
            "contributor_type": "HUMAN",
            "email": f"cli-smoke-{contributor_id}@coherence.network",
            "legacy_id": contributor_id,
        },
    )
    graph_service.create_node(
        id=idea_id,
        type="idea",
        name="CLI Smoke Idea",
        description="Seeded for repo CLI smoke coverage",
        phase="gas",
        properties={
            "potential_value": 21.0,
            "estimated_cost": 8.0,
            "actual_value": 0.0,
            "actual_cost": 0.0,
            "confidence": 0.55,
            "manifestation_status": "none",
            "stage": "none",
            "idea_type": "standalone",
            "interfaces": [],
            "open_questions": [],
        },
    )

    with _serve_app() as api_base:
        contributors_output = _run_cli(api_base, "contributors", "5")
        ideas_output = _run_cli(api_base, "ideas", "5")

    assert "CLI Smoke User" in contributors_output
    assert "CLI Smoke Idea" in ideas_output


def test_repo_cli_shows_seeded_detail_entities() -> None:
    contributor_id = str(uuid4())
    idea_id = f"cli-detail-idea-{uuid4().hex[:8]}"
    graph_service.create_node(
        id=f"contributor:cli-detail-{contributor_id}",
        type="contributor",
        name="CLI Detail User",
        description="HUMAN contributor",
        phase="water",
        properties={
            "contributor_type": "HUMAN",
            "email": f"cli-detail-{contributor_id}@coherence.network",
            "legacy_id": contributor_id,
            "wallet_address": "0xcli-detail",
        },
    )
    graph_service.create_node(
        id=idea_id,
        type="idea",
        name="CLI Detail Idea",
        description="Seeded detail route for repo CLI coverage",
        phase="water",
        properties={
            "potential_value": 144.0,
            "estimated_cost": 34.0,
            "actual_value": 55.0,
            "actual_cost": 13.0,
            "confidence": 0.82,
            "manifestation_status": "partial",
            "stage": "validation",
            "idea_type": "standalone",
            "interfaces": [],
            "open_questions": ["What evidence should close the loop?"],
            "roi_cc": 21.0,
            "free_energy_score": 1.75,
        },
    )

    with _serve_app() as api_base:
        contributor_output = _run_cli(api_base, "contributor", contributor_id)
        idea_output = _run_cli(api_base, "idea", idea_id)

    assert "CLI Detail User" in contributor_output
    assert contributor_id in contributor_output
    assert "CLI Detail Idea" in idea_output
    assert idea_id in idea_output
    assert "ROI (CC):" in idea_output


def test_repo_cli_shows_seeded_contributor_contributions() -> None:
    contributor_id = str(uuid4())
    asset_id = str(uuid4())
    contribution_id = str(uuid4())
    description = "CLI contribution proof"

    contributor_node_id = f"contributor:cli-contrib-{contributor_id}"
    asset_node_id = f"asset:cli-contrib-{asset_id}"
    graph_service.create_node(
        id=contributor_node_id,
        type="contributor",
        name="CLI Contribution User",
        description="HUMAN contributor",
        phase="water",
        properties={
            "contributor_type": "HUMAN",
            "email": f"cli-contrib-{contributor_id}@coherence.network",
            "legacy_id": contributor_id,
        },
    )
    graph_service.create_node(
        id=asset_node_id,
        type="asset",
        name="CLI Contribution Asset",
        description="Seeded asset for contributor contribution smoke coverage",
        phase="water",
        properties={"legacy_id": asset_id},
    )
    graph_service.create_edge(
        from_id=contributor_node_id,
        to_id=asset_node_id,
        type="contribution",
        properties={
            "contribution_id": contribution_id,
            "contributor_id": contributor_id,
            "asset_id": asset_id,
            "cost_amount": "12.5",
            "coherence_score": 0.8,
            "metadata": {"description": description, "type": "code"},
        },
        strength=0.8,
        created_by="test_cli_repo_smoke",
    )

    with _serve_app() as api_base:
        contributions_output = _run_cli(api_base, "contributor", contributor_id, "contributions")

    assert "CONTRIBUTIONS" in contributions_output
    assert description in contributions_output
    assert "12.5 CC" in contributions_output


def test_repo_cli_shows_seeded_idea_tasks() -> None:
    idea_id = f"cli-task-idea-{uuid4().hex[:8]}"
    graph_service.create_node(
        id=idea_id,
        type="idea",
        name="CLI Task Idea",
        description="Seeded for repo CLI idea-task coverage",
        phase="gas",
        properties={
            "potential_value": 34.0,
            "estimated_cost": 13.0,
            "actual_value": 0.0,
            "actual_cost": 0.0,
            "confidence": 0.61,
            "manifestation_status": "none",
            "stage": "none",
            "idea_type": "standalone",
            "interfaces": [],
            "open_questions": [],
        },
    )
    with _serve_app() as api_base:
        request = urllib.request.Request(
            f"{api_base}/api/agent/tasks",
            data=json.dumps(
                {
                    "direction": "Implement CLI task smoke validation",
                    "task_type": "impl",
                    "context": {"idea_id": idea_id},
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            assert response.status == 201
        tasks_output = _run_cli(api_base, "idea", idea_id, "tasks")

    assert f"TASKS for {idea_id}" in tasks_output
    assert "impl" in tasks_output
    assert "Implement CLI task smoke validation" in tasks_output


def test_repo_cli_lists_snapshot_providers() -> None:
    with _serve_app() as api_base:
        providers_output = _run_cli(api_base, "providers")

    assert "PROVIDERS" in providers_output
    assert "openrouter" in providers_output
    assert "cursor" in providers_output
