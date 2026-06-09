#!/usr/bin/env python3
"""Observation gate for native mutation default invitation and public gate.

This is the movement after A/B preview confidence:

  A: no mutation gate header -> must accept the implicit native invitation.
  B: X-Form-Native-Preview -> must remain a non-executing native SQL preview.
  C: X-Form-Native-Public-Gate -> must select the public-gate native route and
     carry a route-local rollback receipt.
  D: X-Form-Python-Fallback -> explicit refusal/control signal, fanned out.

The HTTP native route still keeps DB execution honest in its response. The live
Postgres receipt proof lives in form/scripts/native-mutation-public-gate-test.sh.
"""

from __future__ import annotations

import argparse
import http.server
import json
import shutil
import socket
import subprocess
import sys
import tempfile
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
PRODUCTION_ROUTES = HERE / "production-routes.fk"
STDLIB = REPO_ROOT / "form" / "form-stdlib"
PREVIEW_HEADER = "X-Form-Native-Preview"
PUBLIC_GATE_HEADER = "X-Form-Native-Public-Gate"
PYTHON_FALLBACK_HEADER = "X-Form-Python-Fallback"
IMPLICIT_NATIVE_PROTOCOL = "implicit-native-invitation"

SCHEMA_SQL = """
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
CREATE UNIQUE INDEX ix_graph_edges_pair ON graph_edges (from_id, to_id, type);
"""


@dataclass(frozen=True)
class PublicGateCase:
    name: str
    method: str
    path: str
    body: str
    operation: str
    node_id: str
    sql_contains: tuple[str, ...]


@dataclass(frozen=True)
class HTTPObservation:
    status: int
    router: str
    body: str
    parsed: dict[str, Any]


@dataclass(frozen=True)
class PublicGateObservation:
    name: str
    passed: bool
    checks: dict[str, bool]
    default_status: int
    default_router: str
    preview_status: int
    preview_router: str
    public_gate_status: int
    public_gate_router: str
    both_headers_status: int
    both_headers_router: str
    fallback_status: int
    fallback_router: str
    operation: str
    node_id: str


@dataclass(frozen=True)
class ProvisionedPostgres:
    dsn: str
    directory: Path
    port: int


CASES: tuple[PublicGateCase, ...] = (
    PublicGateCase(
        name="idea-create",
        method="POST",
        path="/api/ideas",
        body='{"id":"idea-public-gate","name":"Public Gate Idea","description":"gate","manifestation_status":"partial"}',
        operation="create-idea",
        node_id="idea-public-gate",
        sql_contains=(
            "INSERT INTO graph_nodes",
            "INSERT INTO graph_node_revisions",
            "kernel-router-public-gate",
            "'idea-public-gate'",
            "'water'",
        ),
    ),
    PublicGateCase(
        name="idea-update",
        method="PATCH",
        path="/api/ideas/idea-public-gate",
        body='{"name":"Public Gate Idea Updated","description":"gate observed","manifestation_status":"validated"}',
        operation="update-idea",
        node_id="idea-public-gate",
        sql_contains=(
            "UPDATE graph_nodes SET",
            "properties = properties ||",
            "kernel-router-public-gate",
            "'idea-public-gate'",
            "'ice'",
        ),
    ),
    PublicGateCase(
        name="spec-create",
        method="POST",
        path="/api/spec-registry",
        body='{"spec_id":"public-gate-spec","title":"Public Gate Spec","summary":"gate"}',
        operation="create-spec",
        node_id="spec-public-gate-spec",
        sql_contains=(
            "INSERT INTO graph_nodes",
            "INSERT INTO graph_node_revisions",
            "kernel-router-public-gate",
            "'spec-public-gate-spec'",
            "'spec'",
        ),
    ),
    PublicGateCase(
        name="spec-update",
        method="PATCH",
        path="/api/spec-registry/public-gate-spec",
        body='{"title":"Public Gate Spec Updated","summary":"gate observed"}',
        operation="update-spec",
        node_id="spec-public-gate-spec",
        sql_contains=(
            "UPDATE graph_nodes SET",
            "properties = properties ||",
            "kernel-router-public-gate",
            "'spec-public-gate-spec'",
        ),
    ),
    PublicGateCase(
        name="spec-delete",
        method="DELETE",
        path="/api/spec-registry/public-gate-spec",
        body="",
        operation="delete-spec",
        node_id="spec-public-gate-spec",
        sql_contains=(
            "WITH deleted_edges AS",
            "DELETE FROM graph_edges",
            "DELETE FROM graph_nodes",
            "'spec-public-gate-spec'",
        ),
    ),
)


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


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"SKIP: {name} not found - cannot self-provision throwaway Postgres")
    return path


def run_psql(dsn: str, sql: str) -> str:
    result = subprocess.run(
        ["psql", dsn, "-v", "ON_ERROR_STOP=1", "-Atc", sql],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"psql failed: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.strip()


def provision_postgres() -> ProvisionedPostgres:
    initdb = require_tool("initdb")
    pg_ctl = require_tool("pg_ctl")
    require_tool("psql")
    directory = Path(tempfile.mkdtemp(prefix="kernel-http-mutation-pg."))
    port = free_port()
    data_dir = directory / "data"
    subprocess.run(
        [initdb, "-D", str(data_dir), "-U", "postgres", "--auth=trust"],
        text=True,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        [
            pg_ctl,
            "-D",
            str(data_dir),
            "-o",
            f"-p {port} -k {directory}",
            "-l",
            str(directory / "log"),
            "start",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    maintenance_dsn = f"postgresql://postgres@127.0.0.1:{port}/postgres"
    run_psql(maintenance_dsn, "CREATE DATABASE native_http_mutation_test;")
    dsn = f"postgresql://postgres@127.0.0.1:{port}/native_http_mutation_test"
    run_psql(dsn, SCHEMA_SQL)
    return ProvisionedPostgres(dsn=dsn, directory=directory, port=port)


def stop_postgres(pg: ProvisionedPostgres | None) -> None:
    if pg is None:
        return
    pg_ctl = shutil.which("pg_ctl")
    if pg_ctl:
        subprocess.run(
            [pg_ctl, "-D", str(pg.directory / "data"), "stop", "-m", "fast"],
            text=True,
            capture_output=True,
            check=False,
        )
    shutil.rmtree(pg.directory, ignore_errors=True)


def write_kernel_config(dsn: str) -> Path:
    directory = Path(tempfile.mkdtemp(prefix="kernel-http-mutation-config."))
    path = directory / "config.json"
    path.write_text(json.dumps({"database": {"url": dsn}}), encoding="utf-8")
    return path


def cleanup_kernel_config(path: Path | None) -> None:
    if path is not None:
        shutil.rmtree(path.parent, ignore_errors=True)


def sql_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def reset_schema(dsn: str) -> None:
    run_psql(dsn, SCHEMA_SQL)


def seed_case(dsn: str, case: PublicGateCase) -> None:
    if not case.operation.startswith(("update-", "delete-")):
        return
    node_type = "spec" if case.node_id.startswith("spec-") else "idea"
    run_psql(
        dsn,
        "INSERT INTO graph_nodes (id, type, name, description, properties, phase) "
        f"VALUES ({sql_quote(case.node_id)}, {sql_quote(node_type)}, 'Seed Node', "
        "'seeded for native HTTP mutation harness', '{}'::jsonb, 'water');",
    )
    if case.operation.startswith("delete-"):
        run_psql(
            dsn,
            "INSERT INTO graph_nodes (id, type, name, properties, phase) "
            "VALUES ('seed-peer', 'idea', 'Seed Peer', '{}'::jsonb, 'water'); "
            "INSERT INTO graph_edges (id, from_id, to_id, type, properties, created_by) "
            f"VALUES ('seed-edge', 'seed-peer', {sql_quote(case.node_id)}, 'references', "
            "'{}'::jsonb, 'harness');",
        )


def expected_node_name(case: PublicGateCase) -> str:
    if not case.body:
        return ""
    body = json.loads(case.body)
    return str(body.get("title") or body.get("name") or "")


def expected_node_phase(case: PublicGateCase) -> str:
    if case.operation.startswith("create-spec") or case.operation.startswith("update-spec"):
        return "ice"
    if not case.body:
        return "water"
    body = json.loads(case.body)
    return "ice" if body.get("manifestation_status") == "validated" else "water"


def persistence_readback_checks(dsn: str, case: PublicGateCase) -> dict[str, bool]:
    if case.operation.startswith("delete-"):
        node_count = run_psql(
            dsn,
            f"SELECT count(*) FROM graph_nodes WHERE id = {sql_quote(case.node_id)};",
        )
        edge_count = run_psql(
            dsn,
            f"SELECT count(*) FROM graph_edges WHERE from_id = {sql_quote(case.node_id)} "
            f"OR to_id = {sql_quote(case.node_id)};",
        )
        return {
            "native_persistence_deleted_node": node_count == "0",
            "native_persistence_deleted_edges": edge_count == "0",
        }

    node_type = "spec" if case.node_id.startswith("spec-") else "idea"
    expected = f"{node_type}:{expected_node_name(case)}:{expected_node_phase(case)}"
    row = run_psql(
        dsn,
        "SELECT type || ':' || name || ':' || phase FROM graph_nodes "
        f"WHERE id = {sql_quote(case.node_id)};",
    )
    revisions = run_psql(
        dsn,
        f"SELECT count(*) FROM graph_node_revisions WHERE node_id = {sql_quote(case.node_id)};",
    )
    return {
        "native_persistence_node_readback": row == expected,
        "native_persistence_revision_readback": revisions == "1",
    }


def executing_http_request(
    base_url: str,
    case: PublicGateCase,
    *,
    headers: dict[str, str],
    dsn: str,
) -> tuple[HTTPObservation, dict[str, bool]]:
    reset_schema(dsn)
    seed_case(dsn, case)
    observation = http_request(base_url, case, headers=headers)
    checks = persistence_readback_checks(dsn, case) if observation.status == 202 else {}
    return observation, checks


def repeated_create_case(suffix: str) -> PublicGateCase:
    node_id = f"idea-public-gate-repeat-{suffix}"
    return PublicGateCase(
        name=f"idea-create-repeat-{suffix}",
        method="POST",
        path="/api/ideas",
        body=(
            '{"id":"'
            + node_id
            + '","name":"Repeated Public Gate Idea '
            + suffix
            + '","description":"revision id collision probe","manifestation_status":"partial"}'
        ),
        operation="create-idea",
        node_id=node_id,
        sql_contains=(
            "INSERT INTO graph_nodes",
            "INSERT INTO graph_node_revisions",
            "kernel-router-public-gate",
            f"'{node_id}'",
            "'water'",
        ),
    )


def repeated_create_collision_checks(
    base_url: str,
    dsn: str,
    *,
    prefix: str,
    headers: dict[str, str],
) -> dict[str, bool]:
    reset_schema(dsn)
    first = repeated_create_case(prefix + "-one")
    second = repeated_create_case(prefix + "-two")
    first_observation = http_request(base_url, first, headers=headers)
    second_observation = http_request(base_url, second, headers=headers)
    revision_counts = run_psql(
        dsn,
        "SELECT count(*) || ':' || count(DISTINCT id) FROM graph_node_revisions "
        f"WHERE node_id IN ({sql_quote(first.node_id)}, {sql_quote(second.node_id)});",
    )
    node_count = run_psql(
        dsn,
        "SELECT count(*) FROM graph_nodes "
        f"WHERE id IN ({sql_quote(first.node_id)}, {sql_quote(second.node_id)});",
    )
    return {
        f"{prefix}_first_create_status": first_observation.status == 202,
        f"{prefix}_second_create_status": second_observation.status == 202,
        f"{prefix}_first_create_router": first_observation.router == "native-kernel",
        f"{prefix}_second_create_router": second_observation.router == "native-kernel",
        f"{prefix}_node_rows": node_count == "2",
        f"{prefix}_revision_rows_distinct_ids": revision_counts == "2:2",
    }


class MockMutationUpstream(http.server.BaseHTTPRequestHandler):
    def _respond(self) -> None:
        n = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(n).decode("utf-8") if n else ""
        payload = json.dumps(
            {
                "variant": "A",
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

    def do_POST(self) -> None:  # noqa: N802
        self._respond()

    def do_PATCH(self) -> None:  # noqa: N802
        self._respond()

    def do_DELETE(self) -> None:  # noqa: N802
        self._respond()

    def log_message(self, *_args: object) -> None:
        return


def http_request(base_url: str, case: PublicGateCase, *, headers: dict[str, str]) -> HTTPObservation:
    data = case.body.encode("utf-8") if case.body else None
    request_headers = {"Content-Type": "application/json"}
    request_headers.update(headers)
    req = urllib.request.Request(
        base_url + case.path,
        data=data,
        method=case.method,
        headers=request_headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=10.0) as response:
            status = int(response.status)
            body = response.read().decode("utf-8")
            router = response.headers.get("X-Form-Router", "")
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        body = exc.read().decode("utf-8")
        router = exc.headers.get("X-Form-Router", "")
    try:
        parsed = json.loads(body) if body else {}
    except json.JSONDecodeError:
        parsed = {}
    return HTTPObservation(status=status, router=router, body=body, parsed=parsed)


def _gate_checks(
    case: PublicGateCase,
    observation: HTTPObservation,
    *,
    expected_protocol: str,
    expected_selected_path: str,
    expected_route_binding: str,
    expected_required_header: str | None,
    expected_default_invitation: bool,
    expected_sql_contains: tuple[str, ...] | None = None,
) -> dict[str, bool]:
    parsed = observation.parsed
    sql = str(parsed.get("sql") or "")
    sql_contains = expected_sql_contains or case.sql_contains
    receipt = parsed.get("route_local_rollback_receipt")
    if not isinstance(receipt, dict):
        receipt = {}
    trust = parsed.get("trust_envelope")
    if not isinstance(trust, dict):
        trust = {}
    decision = parsed.get("decision_receipt")
    if not isinstance(decision, dict):
        decision = {}
    decision_candidates = decision.get("candidates")
    if not isinstance(decision_candidates, list):
        decision_candidates = []
    decision_signature = decision.get("signature")
    if not isinstance(decision_signature, dict):
        decision_signature = {}
    reversible_gate = trust.get("reversible_gate")
    if not isinstance(reversible_gate, dict):
        reversible_gate = {}
    persistence = parsed.get("persistence")
    if not isinstance(persistence, dict):
        persistence = {}
    return {
        "public_gate_native": observation.router == "native-kernel",
        "public_gate_status": observation.status == 202,
        "public_gate_declared": parsed.get("native_public_gate") is True,
        "default_invitation_declared": (
            parsed.get("native_default_invitation") is True
            if expected_default_invitation
            else parsed.get("native_default_invitation") is not True
        ),
        "public_gate_not_preview": parsed.get("native_preview") is False,
        "public_gate_required_header": parsed.get("required_header") == expected_required_header,
        "public_gate_fallback_header": parsed.get("fallback_header") in (None, PYTHON_FALLBACK_HEADER),
        "public_gate_route_binding": parsed.get("route_binding") == expected_route_binding,
        "public_gate_operation": parsed.get("operation") == case.operation,
        "public_gate_node_id": parsed.get("node_id") == case.node_id,
        "public_gate_executes_persistence": parsed.get("executes") is True,
        "public_gate_db_execution": parsed.get("db_execution") == "performed-by-http-native-persistence",
        "public_gate_persistence_carrier": persistence.get("carrier") == "config_database_url",
        "public_gate_persistence_executed": persistence.get("executes") is True,
        "public_gate_persistence_rows": isinstance(persistence.get("rows_affected"), int)
        and persistence.get("rows_affected") >= 0,
        "public_gate_persistence_closed": persistence.get("close_code") == 0,
        "public_gate_executes_gate": parsed.get("route_local_gate_executes") is True,
        "public_gate_sql_shape": all(part in sql for part in sql_contains),
        "public_gate_body_seen": parsed.get("request_body", "") == (case.body or "{}"),
        "rollback_receipt_state": receipt.get("state") == "route-local-rollback-receipt",
        "rollback_receipt_node": receipt.get("node_id") == case.node_id,
        "rollback_receipt_rollback": (
            PYTHON_FALLBACK_HEADER in str(receipt.get("rollback") or "")
            and "default native route row" in str(receipt.get("rollback") or "")
        ),
        "decision_receipt_state": decision.get("state") == "native-mutation-gate-decision-receipt",
        "decision_receipt_gate": decision.get("gate") == "native_mutation_public_gate",
        "decision_receipt_protocol": decision.get("protocol") == expected_protocol,
        "decision_receipt_operation": decision.get("operation") == case.operation,
        "decision_receipt_node": decision.get("node_id") == case.node_id,
        "decision_receipt_selected_path": decision.get("selected_path") == expected_selected_path,
        "decision_receipt_outcome": decision.get("outcome") == "success",
        "decision_receipt_choice": decision.get("choice") == 1,
        "decision_receipt_candidates": (
            len(decision_candidates) == 4
            and any(
                candidate.get("path") == IMPLICIT_NATIVE_PROTOCOL
                and candidate.get("outcome") == "success"
                and candidate.get("selected") is (expected_selected_path == IMPLICIT_NATIVE_PROTOCOL)
                for candidate in decision_candidates
                if isinstance(candidate, dict)
            )
            and any(
                candidate.get("path") == PREVIEW_HEADER
                and candidate.get("outcome") == "preview"
                and candidate.get("selected") is (expected_selected_path == PREVIEW_HEADER)
                for candidate in decision_candidates
                if isinstance(candidate, dict)
            )
            and any(
                candidate.get("path") == PUBLIC_GATE_HEADER
                and candidate.get("outcome") == "success"
                and candidate.get("selected") is (expected_selected_path == PUBLIC_GATE_HEADER)
                for candidate in decision_candidates
                if isinstance(candidate, dict)
            )
            and any(
                candidate.get("path") == PYTHON_FALLBACK_HEADER
                and candidate.get("outcome") == "refusal-signal"
                and candidate.get("selected") is (expected_selected_path == PYTHON_FALLBACK_HEADER)
                for candidate in decision_candidates
                if isinstance(candidate, dict)
            )
        ),
        "decision_receipt_reversible": (
            decision.get("ordinary_traffic_flip_performed") is True
            and decision.get("reversible") is True
            and decision.get("can_contradict_intent") is True
            and decision.get("fail") == "explicit-python-fallback"
            and decision.get("stop") == "native-default-observed"
            and decision.get("bma") == "native-mutation-public-gate"
        ),
        "decision_receipt_signature": (
            decision_signature.get("category") == "native-mutation-gate"
            and decision_signature.get("selected_path") == expected_selected_path
            and decision_signature.get("outcome_code") == 1
            and decision_signature.get("candidate_count") == 4
            and decision_signature.get("operation") == case.operation
            and decision_signature.get("node_id") == case.node_id
        ),
        "trust_protocol": trust.get("protocol") == expected_protocol,
        "trust_selected_path": trust.get("selected_path") == expected_selected_path,
        "trust_choice_success": trust.get("choice_success") == 1,
        "trust_fail": trust.get("fail") == "explicit-python-fallback",
        "trust_stop": trust.get("stop") == "native-default-observed",
        "trust_bma": trust.get("bma") == "native-mutation-public-gate",
        "trust_reversible_gate": (
            reversible_gate.get("default_route") == "native-kernel"
            and reversible_gate.get("default_protocol") == IMPLICIT_NATIVE_PROTOCOL
            and reversible_gate.get("preview_route") == PREVIEW_HEADER
            and reversible_gate.get("public_gate_route") == PUBLIC_GATE_HEADER
            and reversible_gate.get("fallback_route") == PYTHON_FALLBACK_HEADER
            and reversible_gate.get("public_gate_allowed") is True
            and reversible_gate.get("ordinary_traffic_flip_performed") is True
        ),
    }


def evaluate_case(
    case: PublicGateCase,
    default: HTTPObservation,
    preview: HTTPObservation,
    public_gate: HTTPObservation,
    both_headers: HTTPObservation,
    fallback: HTTPObservation,
    *,
    default_db_checks: dict[str, bool] | None = None,
    public_gate_db_checks: dict[str, bool] | None = None,
    both_headers_db_checks: dict[str, bool] | None = None,
) -> PublicGateObservation:
    preview_checks = {
        "preview_native": preview.router == "native-kernel",
        "preview_status": preview.status == 202,
        "preview_declared": preview.parsed.get("native_preview") is True,
        "preview_observes_only": preview.parsed.get("executes") is False,
        "preview_protocol": (preview.parsed.get("trust_envelope") or {}).get("protocol") == PREVIEW_HEADER,
    }
    checks = {
        **{
            f"default_{name}": ok
            for name, ok in _gate_checks(
                case,
                default,
                expected_protocol=IMPLICIT_NATIVE_PROTOCOL,
                expected_selected_path=IMPLICIT_NATIVE_PROTOCOL,
                expected_route_binding="kernel-http-native-default-invitation",
                expected_required_header=None,
                expected_default_invitation=True,
                expected_sql_contains=tuple(
                    part.replace("kernel-router-public-gate", "kernel-router-native-default")
                    for part in case.sql_contains
                ),
            ).items()
        },
        **{f"default_{name}": ok for name, ok in (default_db_checks or {}).items()},
        "fallback_fanned_out": fallback.router == "fanout-python",
        "fallback_status_ok": fallback.status == 200,
        "fallback_method_seen": fallback.parsed.get("method") == case.method,
        "fallback_path_seen": fallback.parsed.get("path") == case.path,
        "fallback_body_seen": fallback.parsed.get("body", "") == case.body,
        **{f"preview_{name}": ok for name, ok in preview_checks.items()},
        **_gate_checks(
            case,
            public_gate,
            expected_protocol=PUBLIC_GATE_HEADER,
            expected_selected_path=PUBLIC_GATE_HEADER,
            expected_route_binding="kernel-http-public-rollback-gated",
            expected_required_header=PUBLIC_GATE_HEADER,
            expected_default_invitation=False,
        ),
        **(public_gate_db_checks or {}),
        **{
            f"both_headers_{name}": ok
            for name, ok in _gate_checks(
                case,
                both_headers,
                expected_protocol=PUBLIC_GATE_HEADER,
                expected_selected_path=PUBLIC_GATE_HEADER,
                expected_route_binding="kernel-http-public-rollback-gated",
                expected_required_header=PUBLIC_GATE_HEADER,
                expected_default_invitation=False,
            ).items()
        },
        **{f"both_headers_{name}": ok for name, ok in (both_headers_db_checks or {}).items()},
    }
    return PublicGateObservation(
        name=case.name,
        passed=all(checks.values()),
        checks=checks,
        default_status=default.status,
        default_router=default.router,
        preview_status=preview.status,
        preview_router=preview.router,
        public_gate_status=public_gate.status,
        public_gate_router=public_gate.router,
        both_headers_status=both_headers.status,
        both_headers_router=both_headers.router,
        fallback_status=fallback.status,
        fallback_router=fallback.router,
        operation=str(public_gate.parsed.get("operation") or ""),
        node_id=str(public_gate.parsed.get("node_id") or ""),
    )


def build_gate_report(
    observations: list[PublicGateObservation],
    *,
    min_confidence: float,
    production_collision_checks: dict[str, bool],
) -> dict[str, Any]:
    total = len(observations)
    passed = sum(1 for obs in observations if obs.passed)
    confidence = (passed / total) if total else 0.0
    collision_pass = all(production_collision_checks.values())
    gate_pass = confidence >= min_confidence and passed == total and collision_pass
    return {
        "gate": "native_mutation_public_gate",
        "variant_a": "native-kernel implicit invitation without native mutation headers",
        "variant_b": "native-kernel SQL preview with X-Form-Native-Preview",
        "variant_c": "native-kernel public gate with X-Form-Native-Public-Gate",
        "variant_d": "fanout-python explicit fallback with X-Form-Python-Fallback",
        "cases": [asdict(obs) for obs in observations],
        "passed_cases": passed,
        "total_cases": total,
        "confidence": round(confidence, 4),
        "min_confidence": min_confidence,
        "gate_pass": gate_pass,
        "production_revision_id_collision_probe": production_collision_checks,
        "production_revision_id_collision_probe_pass": collision_pass,
        "recommendation": (
            "verify_deployed_bounded_native_default"
            if gate_pass
            else "hold_public_gate"
        ),
        "native_http_persistence_proven": gate_pass,
        "public_gate_header_allowed": gate_pass,
        "ordinary_traffic_flip_allowed": True,
        "ordinary_traffic_flip_performed": True,
        "python_fallback_header": PYTHON_FALLBACK_HEADER,
        "next_evidence_needed": [
            "deployed bounded native default persists through mounted production config",
            "bounded public Traefik mutable method/path routes to kernel-router",
            "explicit X-Form-Python-Fallback refusal/control signal is counted separately",
        ],
    }


def run_observation(min_confidence: float) -> dict[str, Any]:
    if not BIN.exists():
        raise RuntimeError(f"build first: cargo build --release ({BIN} missing)")
    if not PRODUCTION_ROUTES.exists():
        raise RuntimeError(f"missing production routes: {PRODUCTION_ROUTES}")

    pg = provision_postgres()
    config_path = write_kernel_config(pg.dsn)
    upstream_port = free_port()
    router_port = free_port()
    upstream = http.server.ThreadingHTTPServer(
        ("127.0.0.1", upstream_port),
        MockMutationUpstream,
    )
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
                str(PRODUCTION_ROUTES),
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
                "kernel-router failed to start\n"
                f"stdout={out.decode(errors='replace')}\n"
                f"stderr={err.decode(errors='replace')}"
            )
        base_url = f"http://127.0.0.1:{router_port}"
        observations = []
        for case in CASES:
            default, default_db_checks = executing_http_request(
                base_url,
                case,
                headers={},
                dsn=pg.dsn,
            )
            preview = http_request(base_url, case, headers={PREVIEW_HEADER: "1"})
            public_gate, public_gate_db_checks = executing_http_request(
                base_url,
                case,
                headers={PUBLIC_GATE_HEADER: "1"},
                dsn=pg.dsn,
            )
            both_headers, both_headers_db_checks = executing_http_request(
                base_url,
                case,
                headers={PREVIEW_HEADER: "1", PUBLIC_GATE_HEADER: "1"},
                dsn=pg.dsn,
            )
            fallback = http_request(base_url, case, headers={PYTHON_FALLBACK_HEADER: "1"})
            observations.append(
                evaluate_case(
                    case,
                    default,
                    preview,
                    public_gate,
                    both_headers,
                    fallback,
                    default_db_checks=default_db_checks,
                    public_gate_db_checks=public_gate_db_checks,
                    both_headers_db_checks=both_headers_db_checks,
                )
            )
        production_collision_checks = {
            **repeated_create_collision_checks(
                base_url,
                pg.dsn,
                prefix="default",
                headers={},
            ),
            **repeated_create_collision_checks(
                base_url,
                pg.dsn,
                prefix="public_gate",
                headers={PUBLIC_GATE_HEADER: "1"},
            ),
        }
        return build_gate_report(
            observations,
            min_confidence=min_confidence,
            production_collision_checks=production_collision_checks,
        )
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


def render_human(report: dict[str, Any]) -> str:
    lines = [
        "# Native Mutation Public Gate",
        "",
        f"variant A: {report['variant_a']}",
        f"variant B: {report['variant_b']}",
        f"variant C: {report['variant_c']}",
        f"variant D: {report['variant_d']}",
        f"confidence: {report['confidence']:.4f} ({report['passed_cases']}/{report['total_cases']} cases)",
        f"gate_pass: {report['gate_pass']}",
        "production_revision_id_collision_probe_pass: "
        f"{report['production_revision_id_collision_probe_pass']}",
        f"recommendation: {report['recommendation']}",
        "ordinary_traffic_flip_performed: true",
        "",
        "cases:",
    ]
    for case in report["cases"]:
        lines.append(
            f"  - {case['name']}: {'pass' if case['passed'] else 'fail'} "
            f"A={case['default_router']}:{case['default_status']} "
            f"B={case['preview_router']}:{case['preview_status']} "
            f"C={case['public_gate_router']}:{case['public_gate_status']} "
            f"both={case['both_headers_router']}:{case['both_headers_status']} "
            f"D={case['fallback_router']}:{case['fallback_status']} "
            f"{case['operation']} {case['node_id']}"
        )
        failed = [name for name, ok in case["checks"].items() if not ok]
        if failed:
            lines.append(f"    failed_checks: {', '.join(failed)}")
    lines.append("")
    lines.append("next evidence needed:")
    for item in report["next_evidence_needed"]:
        lines.append(f"  - {item}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=1.0,
        help="required pass ratio; default 1.0 for mutation gates",
    )
    args = parser.parse_args(argv)

    try:
        report = run_observation(min_confidence=args.min_confidence)
    except Exception as exc:
        if str(exc).startswith("SKIP:"):
            report = {
                "gate": "native_mutation_public_gate",
                "gate_pass": False,
                "skipped": True,
                "skip_reason": str(exc),
            }
            if args.json:
                print(json.dumps(report, indent=2, sort_keys=True))
            else:
                print(str(exc))
            return 0
        print(f"mutation public gate failed: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_human(report))
    return 0 if report["gate_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
