#!/usr/bin/env python3
"""Observation gate for the native mutation public-gate header.

This is the narrow movement after A/B preview confidence:

  A: no mutation gate header -> must fan out to upstream.
  B: X-Form-Native-Preview -> must remain a non-executing native SQL preview.
  C: X-Form-Native-Public-Gate -> must select the public-gate native route and
     carry a route-local rollback receipt.

No ordinary no-header traffic moves, no production database is touched, and the
HTTP route does not claim DB execution. The live Postgres receipt proof lives in
form/scripts/native-mutation-public-gate-test.sh.
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
PRODUCTION_ROUTES = HERE / "production-routes.fk"
STDLIB = REPO_ROOT / "form" / "form-stdlib"
PREVIEW_HEADER = "X-Form-Native-Preview"
PUBLIC_GATE_HEADER = "X-Form-Native-Public-Gate"


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
    control_status: int
    control_router: str
    preview_status: int
    preview_router: str
    public_gate_status: int
    public_gate_router: str
    both_headers_status: int
    both_headers_router: str
    operation: str
    node_id: str


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


def _gate_checks(case: PublicGateCase, observation: HTTPObservation) -> dict[str, bool]:
    parsed = observation.parsed
    sql = str(parsed.get("sql") or "")
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
    return {
        "public_gate_native": observation.router == "native-kernel",
        "public_gate_status": observation.status == 202,
        "public_gate_declared": parsed.get("native_public_gate") is True,
        "public_gate_not_preview": parsed.get("native_preview") is False,
        "public_gate_required_header": parsed.get("required_header") == PUBLIC_GATE_HEADER,
        "public_gate_route_binding": parsed.get("route_binding") == "kernel-http-public-rollback-gated",
        "public_gate_operation": parsed.get("operation") == case.operation,
        "public_gate_node_id": parsed.get("node_id") == case.node_id,
        "public_gate_keeps_db_execution_honest": parsed.get("executes") is False,
        "public_gate_executes_gate": parsed.get("route_local_gate_executes") is True,
        "public_gate_sql_shape": all(part in sql for part in case.sql_contains),
        "public_gate_body_seen": parsed.get("request_body", "") == (case.body or "{}"),
        "rollback_receipt_state": receipt.get("state") == "route-local-rollback-receipt",
        "rollback_receipt_node": receipt.get("node_id") == case.node_id,
        "rollback_receipt_rollback": "remove X-Form-Native-Public-Gate" in str(receipt.get("rollback") or ""),
        "decision_receipt_state": decision.get("state") == "native-mutation-gate-decision-receipt",
        "decision_receipt_gate": decision.get("gate") == "native_mutation_public_gate",
        "decision_receipt_protocol": decision.get("protocol") == PUBLIC_GATE_HEADER,
        "decision_receipt_operation": decision.get("operation") == case.operation,
        "decision_receipt_node": decision.get("node_id") == case.node_id,
        "decision_receipt_selected_path": decision.get("selected_path") == PUBLIC_GATE_HEADER,
        "decision_receipt_outcome": decision.get("outcome") == "success",
        "decision_receipt_choice": decision.get("choice") == 1,
        "decision_receipt_candidates": (
            len(decision_candidates) == 3
            and any(
                candidate.get("path") == "fanout-python"
                and candidate.get("outcome") == "silence"
                and candidate.get("selected") is False
                for candidate in decision_candidates
                if isinstance(candidate, dict)
            )
            and any(
                candidate.get("path") == PREVIEW_HEADER
                and candidate.get("outcome") == "stop"
                and candidate.get("selected") is False
                for candidate in decision_candidates
                if isinstance(candidate, dict)
            )
            and any(
                candidate.get("path") == PUBLIC_GATE_HEADER
                and candidate.get("outcome") == "success"
                and candidate.get("selected") is True
                for candidate in decision_candidates
                if isinstance(candidate, dict)
            )
        ),
        "decision_receipt_reversible": (
            decision.get("ordinary_traffic_flip_performed") is False
            and decision.get("reversible") is True
            and decision.get("can_contradict_intent") is True
            and decision.get("fail") == "rollback-to-fanout-by-removing-public-gate-header"
            and decision.get("stop") == "ordinary-traffic-unflipped"
            and decision.get("bma") == "native-mutation-public-gate"
        ),
        "decision_receipt_signature": (
            decision_signature.get("category") == "native-mutation-gate"
            and decision_signature.get("selected_path") == PUBLIC_GATE_HEADER
            and decision_signature.get("outcome_code") == 1
            and decision_signature.get("candidate_count") == 3
            and decision_signature.get("operation") == case.operation
            and decision_signature.get("node_id") == case.node_id
        ),
        "trust_protocol": trust.get("protocol") == PUBLIC_GATE_HEADER,
        "trust_choice_success": trust.get("choice_success") == 1,
        "trust_fail": trust.get("fail") == "rollback-to-fanout-by-removing-public-gate-header",
        "trust_stop": trust.get("stop") == "ordinary-traffic-unflipped",
        "trust_bma": trust.get("bma") == "native-mutation-public-gate",
        "trust_reversible_gate": (
            reversible_gate.get("default_route") == "fanout-python"
            and reversible_gate.get("preview_route") == PREVIEW_HEADER
            and reversible_gate.get("public_gate_route") == PUBLIC_GATE_HEADER
            and reversible_gate.get("public_gate_allowed") is True
            and reversible_gate.get("ordinary_traffic_flip_performed") is False
        ),
    }


def evaluate_case(
    case: PublicGateCase,
    control: HTTPObservation,
    preview: HTTPObservation,
    public_gate: HTTPObservation,
    both_headers: HTTPObservation,
) -> PublicGateObservation:
    preview_checks = {
        "preview_native": preview.router == "native-kernel",
        "preview_status": preview.status == 202,
        "preview_declared": preview.parsed.get("native_preview") is True,
        "preview_observes_only": preview.parsed.get("executes") is False,
        "preview_protocol": (preview.parsed.get("trust_envelope") or {}).get("protocol") == PREVIEW_HEADER,
    }
    checks = {
        "control_fanned_out": control.router == "fanout-python",
        "control_status_ok": control.status == 200,
        "control_method_seen": control.parsed.get("method") == case.method,
        "control_path_seen": control.parsed.get("path") == case.path,
        "control_body_seen": control.parsed.get("body", "") == case.body,
        **{f"preview_{name}": ok for name, ok in preview_checks.items()},
        **_gate_checks(case, public_gate),
        **{f"both_headers_{name}": ok for name, ok in _gate_checks(case, both_headers).items()},
    }
    return PublicGateObservation(
        name=case.name,
        passed=all(checks.values()),
        checks=checks,
        control_status=control.status,
        control_router=control.router,
        preview_status=preview.status,
        preview_router=preview.router,
        public_gate_status=public_gate.status,
        public_gate_router=public_gate.router,
        both_headers_status=both_headers.status,
        both_headers_router=both_headers.router,
        operation=str(public_gate.parsed.get("operation") or ""),
        node_id=str(public_gate.parsed.get("node_id") or ""),
    )


def build_gate_report(
    observations: list[PublicGateObservation],
    *,
    min_confidence: float,
) -> dict[str, Any]:
    total = len(observations)
    passed = sum(1 for obs in observations if obs.passed)
    confidence = (passed / total) if total else 0.0
    gate_pass = confidence >= min_confidence and passed == total
    return {
        "gate": "native_mutation_public_gate",
        "variant_a": "fanout-python without native mutation headers",
        "variant_b": "native-kernel SQL preview with X-Form-Native-Preview",
        "variant_c": "native-kernel public gate with X-Form-Native-Public-Gate",
        "cases": [asdict(obs) for obs in observations],
        "passed_cases": passed,
        "total_cases": total,
        "confidence": round(confidence, 4),
        "min_confidence": min_confidence,
        "gate_pass": gate_pass,
        "recommendation": (
            "verify_deployed_header_canary"
            if gate_pass
            else "hold_public_gate"
        ),
        "public_gate_header_allowed": gate_pass,
        "ordinary_traffic_flip_allowed": False,
        "ordinary_traffic_flip_performed": False,
        "next_evidence_needed": [
            "public-gate decision receipts in deployed canary traffic",
            "no-header public control remains outside native canary",
            "sustained X-Form-Native-Public-Gate canary evidence before any no-header flip",
        ],
    }


def run_observation(min_confidence: float) -> dict[str, Any]:
    if not BIN.exists():
        raise RuntimeError(f"build first: cargo build --release ({BIN} missing)")
    if not PRODUCTION_ROUTES.exists():
        raise RuntimeError(f"missing production routes: {PRODUCTION_ROUTES}")

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
        observations = [
            evaluate_case(
                case,
                http_request(base_url, case, headers={}),
                http_request(base_url, case, headers={PREVIEW_HEADER: "1"}),
                http_request(base_url, case, headers={PUBLIC_GATE_HEADER: "1"}),
                http_request(
                    base_url,
                    case,
                    headers={PREVIEW_HEADER: "1", PUBLIC_GATE_HEADER: "1"},
                ),
            )
            for case in CASES
        ]
        return build_gate_report(observations, min_confidence=min_confidence)
    finally:
        if router_proc is not None:
            router_proc.terminate()
            try:
                router_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                router_proc.kill()
        upstream.shutdown()


def render_human(report: dict[str, Any]) -> str:
    lines = [
        "# Native Mutation Public Gate",
        "",
        f"variant A: {report['variant_a']}",
        f"variant B: {report['variant_b']}",
        f"variant C: {report['variant_c']}",
        f"confidence: {report['confidence']:.4f} ({report['passed_cases']}/{report['total_cases']} cases)",
        f"gate_pass: {report['gate_pass']}",
        f"recommendation: {report['recommendation']}",
        "ordinary_traffic_flip_performed: false",
        "",
        "cases:",
    ]
    for case in report["cases"]:
        lines.append(
            f"  - {case['name']}: {'pass' if case['passed'] else 'fail'} "
            f"A={case['control_router']}:{case['control_status']} "
            f"B={case['preview_router']}:{case['preview_status']} "
            f"C={case['public_gate_router']}:{case['public_gate_status']} "
            f"both={case['both_headers_router']}:{case['both_headers_status']} "
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
        print(f"mutation public gate failed: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_human(report))
    return 0 if report["gate_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
