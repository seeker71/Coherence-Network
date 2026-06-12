#!/usr/bin/env python3
"""Live proof for the BML idea detail/write family.

This harness starts the kernel directly against the BML front-door catalog
(`/routes/api.bml` in deployment terms), provisions throwaway Postgres, seeds
the smallest idea graph that can fail the route contracts, and then exercises:

  - PATCH /api/ideas/{idea_id}
  - POST  /api/ideas/{idea_id}/questions
  - POST  /api/ideas/{idea_id}/questions/answer

The result is machine-readable proof that the BML route family is not only
declared but executable: native router, native handler, DB persistence, and
route-local response shape.
"""

from __future__ import annotations

import argparse
import http.server
import json
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
BIN = REPO_ROOT / "form" / "form-kernel-rust" / "target" / "release" / "form-kernel-rust"
BML_ROUTES = REPO_ROOT / "deploy" / "front-door" / "api.bml"
STDLIB = REPO_ROOT / "form" / "form-stdlib"

if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from mutation_public_gate_harness import (  # noqa: E402
    cleanup_kernel_config,
    provision_postgres,
    run_psql,
    sql_quote,
    stop_postgres,
    write_kernel_config,
)


@dataclass(frozen=True)
class HTTPObservation:
    status: int
    router: str
    handler: str
    python_authority: str
    body: str
    parsed: dict[str, Any]


@dataclass(frozen=True)
class CaseObservation:
    name: str
    passed: bool
    checks: dict[str, bool]
    status: int
    router: str
    handler: str
    detail: str


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def wait_for_port(port: int, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket() as s:
            s.settimeout(0.3)
            try:
                s.connect(("127.0.0.1", port))
                return
            except OSError:
                time.sleep(0.1)
    raise RuntimeError(f"listener never came up on 127.0.0.1:{port}")


class MockUpstream(http.server.BaseHTTPRequestHandler):
    def _respond(self) -> None:
        n = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(n).decode("utf-8") if n else ""
        payload = json.dumps(
            {
                "upstream": "mock-cpython",
                "method": self.command,
                "path": self.path,
                "body": raw_body,
            },
            separators=(",", ":"),
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        self._respond()

    def do_POST(self) -> None:  # noqa: N802
        self._respond()

    def do_PATCH(self) -> None:  # noqa: N802
        self._respond()

    def log_message(self, *_args: object) -> None:
        return


def http_request(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    body: str = "",
) -> HTTPObservation:
    data = body.encode("utf-8") if body else None
    req = urllib.request.Request(
        base_url + path,
        data=data,
        method=method,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10.0) as response:
            status = int(response.status)
            body_text = response.read().decode("utf-8")
            router = response.headers.get("X-Form-Router", "")
            handler = response.headers.get("X-Form-Handler", "")
            python_authority = response.headers.get("X-Form-Python-Authority", "")
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        body_text = exc.read().decode("utf-8")
        router = exc.headers.get("X-Form-Router", "")
        handler = exc.headers.get("X-Form-Handler", "")
        python_authority = exc.headers.get("X-Form-Python-Authority", "")
    try:
        parsed = json.loads(body_text) if body_text else {}
    except json.JSONDecodeError:
        parsed = {}
    return HTTPObservation(
        status=status,
        router=router,
        handler=handler,
        python_authority=python_authority,
        body=body_text,
        parsed=parsed,
    )


def reset_idea_family_schema(dsn: str) -> None:
    run_psql(
        dsn,
        """
DROP TABLE IF EXISTS entity_views;
DROP TABLE IF EXISTS graph_edges;
DROP TABLE IF EXISTS graph_node_revisions;
DROP TABLE IF EXISTS graph_nodes;
CREATE TABLE graph_nodes (
    id VARCHAR(255) PRIMARY KEY,
    type VARCHAR(50) NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    properties JSONB NOT NULL DEFAULT '{}'::jsonb,
    phase VARCHAR(20) NOT NULL DEFAULT 'water',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE graph_node_revisions (
    id VARCHAR(255) PRIMARY KEY,
    node_id VARCHAR(255) NOT NULL,
    revision_number INTEGER NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source VARCHAR(32) NOT NULL DEFAULT 'api',
    author VARCHAR(255) NOT NULL DEFAULT '',
    fields_changed JSONB NOT NULL DEFAULT '[]'::jsonb,
    snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT uq_node_revisions_node_rev UNIQUE (node_id, revision_number)
);
CREATE TABLE graph_edges (
    id VARCHAR(255) PRIMARY KEY,
    from_id VARCHAR(255) NOT NULL,
    to_id VARCHAR(255) NOT NULL,
    type VARCHAR(100) NOT NULL,
    properties JSONB NOT NULL DEFAULT '{}'::jsonb,
    strength DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    created_by VARCHAR(255) NOT NULL DEFAULT 'system',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE entity_views (
    id VARCHAR(255) PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(255) NOT NULL,
    lang VARCHAR(32) NOT NULL,
    content_title TEXT NOT NULL DEFAULT '',
    content_description TEXT NOT NULL DEFAULT '',
    content_markdown TEXT NOT NULL DEFAULT '',
    content_hash VARCHAR(255) NOT NULL DEFAULT '',
    status VARCHAR(32) NOT NULL DEFAULT 'canonical',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
        """,
    )


def insert_idea(
    dsn: str,
    *,
    idea_id: str,
    name: str,
    description: str,
    properties: dict[str, Any],
) -> None:
    run_psql(
        dsn,
        "INSERT INTO graph_nodes (id, type, name, description, properties, phase) VALUES ("
        f"{sql_quote(idea_id)}, 'idea', {sql_quote(name)}, {sql_quote(description)}, "
        f"{sql_quote(json.dumps(properties))}::jsonb, 'water');",
    )


def seed_patch_case(dsn: str) -> None:
    reset_idea_family_schema(dsn)
    insert_idea(
        dsn,
        idea_id="idea-parent-old",
        name="Parent Old",
        description="old parent",
        properties={
            "child_idea_ids": ["idea-bml-native"],
            "workspace_id": "coherence-network",
        },
    )
    insert_idea(
        dsn,
        idea_id="idea-parent-new",
        name="Parent New",
        description="new parent",
        properties={
            "child_idea_ids": [],
            "workspace_id": "coherence-network",
        },
    )
    insert_idea(
        dsn,
        idea_id="idea-bml-native",
        name="Idea BML Native",
        description="seed idea",
        properties={
            "potential_value": 50.0,
            "actual_value": 2.0,
            "estimated_cost": 10.0,
            "actual_cost": 1.0,
            "resistance_risk": 1.0,
            "confidence": 0.5,
            "manifestation_status": "partial",
            "interfaces": ["legacy:one"],
            "open_questions": [],
            "idea_type": "child",
            "parent_idea_id": "idea-parent-old",
            "child_idea_ids": [],
            "stage": "specced",
            "work_type": "feature",
            "lifecycle": "active",
            "duplicate_of": None,
            "workspace_git_url": None,
            "slug": "idea-bml-native",
            "slug_history": [],
            "is_curated": False,
            "workspace_id": "coherence-network",
            "tags": [],
        },
    )


def seed_question_create_case(dsn: str) -> None:
    reset_idea_family_schema(dsn)
    insert_idea(
        dsn,
        idea_id="idea-question-native",
        name="Idea Question Native",
        description="question seed",
        properties={
            "potential_value": 30.0,
            "actual_value": 0.0,
            "estimated_cost": 5.0,
            "actual_cost": 0.0,
            "resistance_risk": 1.0,
            "confidence": 0.6,
            "manifestation_status": "none",
            "interfaces": [],
            "open_questions": [],
            "idea_type": "standalone",
            "child_idea_ids": [],
            "stage": "none",
            "lifecycle": "active",
            "workspace_id": "coherence-network",
            "slug": "idea-question-native",
            "slug_history": [],
            "tags": [],
        },
    )


def seed_question_answer_case(dsn: str) -> None:
    reset_idea_family_schema(dsn)
    insert_idea(
        dsn,
        idea_id="idea-answer-native",
        name="Idea Answer Native",
        description="answer seed",
        properties={
            "potential_value": 30.0,
            "actual_value": 0.0,
            "estimated_cost": 5.0,
            "actual_cost": 0.0,
            "resistance_risk": 1.0,
            "confidence": 0.6,
            "manifestation_status": "none",
            "interfaces": [],
            "open_questions": [
                {
                    "question": "What changed?",
                    "value_to_whole": 4.0,
                    "estimated_cost": 1.0,
                    "answer": None,
                    "measured_delta": None,
                }
            ],
            "idea_type": "standalone",
            "child_idea_ids": [],
            "stage": "none",
            "lifecycle": "active",
            "workspace_id": "coherence-network",
            "slug": "idea-answer-native",
            "slug_history": [],
            "tags": [],
        },
    )


def patch_db_checks(dsn: str) -> dict[str, bool]:
    row = run_psql(
        dsn,
        """
SELECT
  COALESCE(properties->>'parent_idea_id','') || '|' ||
  COALESCE(properties->>'stage','') || '|' ||
  COALESCE(properties->>'manifestation_status','') || '|' ||
  COALESCE(properties->>'workspace_git_url','') || '|' ||
  COALESCE(properties->>'last_activity_at','') || '|' ||
  COALESCE(properties->'interfaces','[]'::jsonb)::text
FROM graph_nodes
WHERE id = 'idea-bml-native';
        """,
    )
    old_parent = run_psql(
        dsn,
        "SELECT COALESCE(properties->'child_idea_ids','[]'::jsonb)::text FROM graph_nodes WHERE id = 'idea-parent-old';",
    )
    new_parent = run_psql(
        dsn,
        "SELECT COALESCE(properties->'child_idea_ids','[]'::jsonb)::text FROM graph_nodes WHERE id = 'idea-parent-new';",
    )
    return {
        "db_patch_child_updated": row.startswith(
            'idea-parent-new|complete|validated|https://example.com/repo.git|'
        )
        and '["human:web", "machine:api"]' in row,
        "db_patch_last_activity_present": "||" not in row,
        "db_patch_old_parent_removed": old_parent == "[]",
        "db_patch_new_parent_added": new_parent == '["idea-bml-native"]',
    }


def question_create_db_checks(dsn: str) -> dict[str, bool]:
    row = run_psql(
        dsn,
        "SELECT COALESCE(properties->'open_questions','[]'::jsonb)::text FROM graph_nodes WHERE id = 'idea-question-native';",
    )
    return {
        "db_question_created": '"question": "What blocks proof?"' in row,
        "db_question_value": '"value_to_whole": 8' in row or '"value_to_whole": 8.0' in row,
    }


def question_answer_db_checks(dsn: str) -> dict[str, bool]:
    row = run_psql(
        dsn,
        "SELECT COALESCE(properties->'open_questions','[]'::jsonb)::text FROM graph_nodes WHERE id = 'idea-answer-native';",
    )
    return {
        "db_answer_written": '"answer": "The kernel now carries the route."' in row,
        "db_measured_delta_written": '"measured_delta": 2.5' in row,
    }


def seed_detail_failure_case(dsn: str) -> None:
    reset_idea_family_schema(dsn)
    run_psql(dsn, "DROP TABLE graph_nodes;")


def error_detail_text(observation: HTTPObservation) -> str:
    detail = observation.parsed.get("detail")
    if isinstance(detail, dict):
        nested = detail.get("detail")
        if isinstance(nested, str):
            return nested
    return ""


def evaluate_empty_patch(observation: HTTPObservation) -> CaseObservation:
    checks = {
        "status_400": observation.status == 400,
        "router_native": observation.router == "native-kernel",
        "handler_absent_on_error": observation.handler == "",
        "detail_message": observation.parsed.get("detail") == "At least one field required",
    }
    return CaseObservation(
        name="idea-update-empty-body",
        passed=all(checks.values()),
        checks=checks,
        status=observation.status,
        router=observation.router,
        handler=observation.handler,
        detail=error_detail_text(observation),
    )


def evaluate_patch_case(
    observation: HTTPObservation,
    detail: HTTPObservation,
    *,
    db_checks: dict[str, bool],
) -> CaseObservation:
    checks = {
        "status_200": observation.status == 200,
        "router_native": observation.router == "native-kernel",
        "handler_update": observation.handler == "api_idea_update",
        "python_authority_false": observation.python_authority == "false",
        "response_name": observation.parsed.get("name") == "Idea BML Native Updated",
        "response_description": observation.parsed.get("description") == "carried by BML",
        "response_stage": observation.parsed.get("stage") == "complete",
        "response_manifestation_status": observation.parsed.get("manifestation_status") == "validated",
        "response_parent": observation.parsed.get("parent_idea_id") == "idea-parent-new",
        "response_workspace_git_url": observation.parsed.get("workspace_git_url") == "https://example.com/repo.git",
        "response_interfaces": observation.parsed.get("interfaces") == ["human:web", "machine:api"],
        "detail_handler": detail.handler == "api_idea_detail",
        "detail_roundtrip_name": detail.parsed.get("name") == "Idea BML Native Updated",
        "detail_roundtrip_parent": detail.parsed.get("parent_idea_id") == "idea-parent-new",
        **db_checks,
    }
    return CaseObservation(
        name="idea-update",
        passed=all(checks.values()),
        checks=checks,
        status=observation.status,
        router=observation.router,
        handler=observation.handler,
        detail="",
    )


def evaluate_question_create_case(
    observation: HTTPObservation,
    detail: HTTPObservation,
    *,
    db_checks: dict[str, bool],
) -> CaseObservation:
    questions = observation.parsed.get("open_questions") or []
    detail_questions = detail.parsed.get("open_questions") or []
    checks = {
        "status_200": observation.status == 200,
        "router_native": observation.router == "native-kernel",
        "handler_create": observation.handler == "api_idea_question_create",
        "python_authority_false": observation.python_authority == "false",
        "one_question_returned": len(questions) == 1,
        "question_text": questions and questions[0].get("question") == "What blocks proof?",
        "detail_roundtrip_question": len(detail_questions) == 1
        and detail_questions[0].get("question") == "What blocks proof?",
        **db_checks,
    }
    return CaseObservation(
        name="idea-question-create",
        passed=all(checks.values()),
        checks=checks,
        status=observation.status,
        router=observation.router,
        handler=observation.handler,
        detail="",
    )


def evaluate_question_answer_case(
    observation: HTTPObservation,
    detail: HTTPObservation,
    *,
    db_checks: dict[str, bool],
) -> CaseObservation:
    questions = observation.parsed.get("open_questions") or []
    detail_questions = detail.parsed.get("open_questions") or []
    checks = {
        "status_200": observation.status == 200,
        "router_native": observation.router == "native-kernel",
        "handler_answer": observation.handler == "api_idea_question_answer",
        "python_authority_false": observation.python_authority == "false",
        "answer_returned": questions and questions[0].get("answer") == "The kernel now carries the route.",
        "measured_delta_returned": questions and questions[0].get("measured_delta") == 2.5,
        "detail_roundtrip_answer": detail_questions
        and detail_questions[0].get("answer") == "The kernel now carries the route.",
        **db_checks,
    }
    return CaseObservation(
        name="idea-question-answer",
        passed=all(checks.values()),
        checks=checks,
        status=observation.status,
        router=observation.router,
        handler=observation.handler,
        detail="",
    )


def evaluate_detail_failure_case(observation: HTTPObservation) -> CaseObservation:
    detail_text = error_detail_text(observation)
    detail_object = observation.parsed.get("detail")
    error_code = detail_object.get("error") if isinstance(detail_object, dict) else ""
    checks = {
        "status_503": observation.status == 503,
        "router_native": observation.router == "native-kernel",
        "handler_absent_on_error": observation.handler == "",
        "error_code_persistence": error_code == "persistence",
        "detail_mentions_graph_nodes": "graph_nodes" in detail_text,
        "detail_mentions_missing_relation": "does not exist" in detail_text,
    }
    return CaseObservation(
        name="idea-detail-schema-failure",
        passed=all(checks.values()),
        checks=checks,
        status=observation.status,
        router=observation.router,
        handler=observation.handler,
        detail=detail_text,
    )


def build_report(observations: list[CaseObservation]) -> dict[str, Any]:
    total = len(observations)
    passed = sum(1 for item in observations if item.passed)
    confidence = (passed / total) if total else 0.0
    return {
        "gate": "bml_idea_family_live_proof",
        "bml_routes_file": str(BML_ROUTES),
        "passed_cases": passed,
        "total_cases": total,
        "confidence": round(confidence, 4),
        "gate_pass": passed == total,
        "cases": [asdict(item) for item in observations],
    }


def run_observation() -> dict[str, Any]:
    if not BIN.exists():
        raise RuntimeError(f"SKIP: build first: cargo build --release ({BIN} missing)")
    if not BML_ROUTES.exists():
        raise RuntimeError(f"missing BML routes: {BML_ROUTES}")

    pg = provision_postgres()
    config_path = write_kernel_config(pg.dsn)
    upstream_port = free_port()
    router_port = free_port()
    upstream = http.server.ThreadingHTTPServer(("127.0.0.1", upstream_port), MockUpstream)
    upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    upstream_thread.start()
    router_proc: subprocess.Popen[bytes] | None = None
    try:
        wait_for_port(upstream_port)
        router_proc = subprocess.Popen(
            [
                str(BIN),
                "serve",
                "--host",
                "127.0.0.1",
                "--port",
                str(router_port),
                "--workers",
                "1",
                "--routes",
                str(BML_ROUTES),
                "--stdlib",
                str(STDLIB),
                "--config",
                str(config_path),
                "--upstream",
                f"http://127.0.0.1:{upstream_port}",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            wait_for_port(router_port)
        except RuntimeError:
            out, err = router_proc.communicate(timeout=3)
            raise RuntimeError(
                "kernel-router failed to start with BML catalog\n"
                f"stdout={out.decode(errors='replace')}\n"
                f"stderr={err.decode(errors='replace')}"
            )

        base_url = f"http://127.0.0.1:{router_port}"
        observations: list[CaseObservation] = []

        seed_patch_case(pg.dsn)
        observations.append(
            evaluate_empty_patch(
                http_request(base_url, "/api/ideas/idea-bml-native", method="PATCH", body="{}")
            )
        )

        seed_detail_failure_case(pg.dsn)
        observations.append(
            evaluate_detail_failure_case(
                http_request(base_url, "/api/ideas/idea-bml-native")
            )
        )

        seed_patch_case(pg.dsn)
        patch_observation = http_request(
            base_url,
            "/api/ideas/idea-bml-native",
            method="PATCH",
            body=json.dumps(
                {
                    "name": "Idea BML Native Updated",
                    "description": "carried by BML",
                    "confidence": 0.9,
                    "stage": "complete",
                    "parent_idea_id": "idea-parent-new",
                    "workspace_git_url": "https://example.com/repo.git",
                    "interfaces": ["human:web", "machine:api"],
                }
            ),
        )
        patch_detail = http_request(base_url, "/api/ideas/idea-bml-native")
        observations.append(
            evaluate_patch_case(
                patch_observation,
                patch_detail,
                db_checks=patch_db_checks(pg.dsn),
            )
        )

        seed_question_create_case(pg.dsn)
        question_create = http_request(
            base_url,
            "/api/ideas/idea-question-native/questions",
            method="POST",
            body=json.dumps(
                {
                    "question": "What blocks proof?",
                    "value_to_whole": 8.0,
                    "estimated_cost": 2.0,
                }
            ),
        )
        question_create_detail = http_request(base_url, "/api/ideas/idea-question-native")
        observations.append(
            evaluate_question_create_case(
                question_create,
                question_create_detail,
                db_checks=question_create_db_checks(pg.dsn),
            )
        )

        seed_question_answer_case(pg.dsn)
        question_answer = http_request(
            base_url,
            "/api/ideas/idea-answer-native/questions/answer",
            method="POST",
            body=json.dumps(
                {
                    "question": "What changed?",
                    "answer": "The kernel now carries the route.",
                    "measured_delta": 2.5,
                }
            ),
        )
        question_answer_detail = http_request(base_url, "/api/ideas/idea-answer-native")
        observations.append(
            evaluate_question_answer_case(
                question_answer,
                question_answer_detail,
                db_checks=question_answer_db_checks(pg.dsn),
            )
        )

        return build_report(observations)
    finally:
        if router_proc is not None:
            router_proc.terminate()
            try:
                router_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                router_proc.kill()
        upstream.shutdown()
        cleanup_kernel_config(config_path)
        stop_postgres(pg)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    try:
        report = run_observation()
    except Exception as exc:
        if str(exc).startswith("SKIP:"):
            report = {
                "gate": "bml_idea_family_live_proof",
                "gate_pass": False,
                "skipped": True,
                "skip_reason": str(exc),
            }
            if args.json:
                print(json.dumps(report, indent=2, sort_keys=True))
            else:
                print(str(exc))
            return 0
        print(f"bml idea family harness failed: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(json.dumps(report, indent=2))
    return 0 if report["gate_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
