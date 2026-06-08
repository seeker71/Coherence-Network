#!/usr/bin/env python3
"""A/B observation gate for native mutation preview routes.

This turns the mutation flip into measurement before movement. It starts a
local mock CPython upstream, starts the production kernel-router manifest in
front of it, and sends each mutation shape twice:

  A: no X-Form-Native-Preview header -> must fan out to upstream.
  B: X-Form-Native-Preview present   -> must return native SQL preview.

No production routing changes, no database writes, no public traffic. The output
is a confidence report. A passing report recommends the next bounded step
(live-DB trial), not an ordinary-traffic flip.
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


@dataclass(frozen=True)
class ObservationCase:
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
class CaseObservation:
    name: str
    passed: bool
    checks: dict[str, bool]
    control_status: int
    control_router: str
    treatment_status: int
    treatment_router: str
    operation: str
    node_id: str


CASES: tuple[ObservationCase, ...] = (
    ObservationCase(
        name="idea-create",
        method="POST",
        path="/api/ideas",
        body='{"id":"idea-ab-native","name":"AB Native Idea","description":"observation","manifestation_status":"partial"}',
        operation="create-idea",
        node_id="idea-ab-native",
        sql_contains=(
            "INSERT INTO graph_nodes",
            "INSERT INTO graph_node_revisions",
            "__create__",
            "'idea-ab-native'",
            "'water'",
        ),
    ),
    ObservationCase(
        name="idea-update",
        method="PATCH",
        path="/api/ideas/idea-ab-native",
        body='{"name":"AB Native Idea Moved","description":"observed","manifestation_status":"validated"}',
        operation="update-idea",
        node_id="idea-ab-native",
        sql_contains=(
            "UPDATE graph_nodes SET",
            "properties = properties ||",
            "COALESCE(max(revision_number), 0) + 1",
            "'idea-ab-native'",
            "'ice'",
        ),
    ),
    ObservationCase(
        name="spec-create",
        method="POST",
        path="/api/spec-registry",
        body='{"spec_id":"ab-native-spec","title":"AB Native Spec","summary":"observation"}',
        operation="create-spec",
        node_id="spec-ab-native-spec",
        sql_contains=(
            "INSERT INTO graph_nodes",
            "INSERT INTO graph_node_revisions",
            "__create__",
            "'spec-ab-native-spec'",
            "'spec'",
        ),
    ),
    ObservationCase(
        name="spec-update",
        method="PATCH",
        path="/api/spec-registry/ab-native-spec",
        body='{"title":"AB Native Spec Updated","summary":"observed"}',
        operation="update-spec",
        node_id="spec-ab-native-spec",
        sql_contains=(
            "UPDATE graph_nodes SET",
            "properties = properties ||",
            "COALESCE(max(revision_number), 0) + 1",
            "'spec-ab-native-spec'",
        ),
    ),
    ObservationCase(
        name="spec-delete",
        method="DELETE",
        path="/api/spec-registry/ab-native-spec",
        body="",
        operation="delete-spec",
        node_id="spec-ab-native-spec",
        sql_contains=(
            "WITH deleted_edges AS",
            "DELETE FROM graph_edges",
            "DELETE FROM graph_nodes",
            "'spec-ab-native-spec'",
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


def http_request(base_url: str, case: ObservationCase, *, preview: bool) -> HTTPObservation:
    data = case.body.encode("utf-8") if case.body else None
    headers = {"Content-Type": "application/json"}
    if preview:
        headers[PREVIEW_HEADER] = "1"
    req = urllib.request.Request(
        base_url + case.path,
        data=data,
        method=case.method,
        headers=headers,
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


def evaluate_case(
    case: ObservationCase,
    control: HTTPObservation,
    treatment: HTTPObservation,
) -> CaseObservation:
    sql = str(treatment.parsed.get("sql") or "")
    trust_envelope = treatment.parsed.get("trust_envelope")
    if not isinstance(trust_envelope, dict):
        trust_envelope = {}
    reversible_gate = trust_envelope.get("reversible_gate")
    if not isinstance(reversible_gate, dict):
        reversible_gate = {}
    side_effect_intents = trust_envelope.get("side_effect_intents")
    if not isinstance(side_effect_intents, list):
        side_effect_intents = []
    checks = {
        "control_fanned_out": control.router == "fanout-python",
        "control_status_ok": control.status == 200,
        "control_method_seen": control.parsed.get("method") == case.method,
        "control_path_seen": control.parsed.get("path") == case.path,
        "control_body_seen": control.parsed.get("body", "") == case.body,
        "treatment_native": treatment.router == "native-kernel",
        "treatment_status_preview": treatment.status == 202,
        "treatment_declares_preview": treatment.parsed.get("native_preview") is True,
        "treatment_operation": treatment.parsed.get("operation") == case.operation,
        "treatment_node_id": treatment.parsed.get("node_id") == case.node_id,
        "treatment_observes_only": treatment.parsed.get("executes") is False,
        "treatment_body_seen": treatment.parsed.get("request_body", "") == (case.body or "{}"),
        "treatment_sql_shape": all(part in sql for part in case.sql_contains),
        "treatment_prediction_error_carried": trust_envelope.get("prediction_error") == "carried_as_residual",
        "treatment_choice_protocol_carried": (
            trust_envelope.get("choice_success") == 1
            and trust_envelope.get("silence") == "fanout-default"
            and trust_envelope.get("protocol") == PREVIEW_HEADER
            and trust_envelope.get("fail") == "rollback-to-fanout"
            and trust_envelope.get("stop") == "ordinary-traffic-unflipped"
            and trust_envelope.get("bma") == "native-mutation-trust-envelope"
        ),
        "treatment_side_effect_intents_carried": {
            "cache-invalidation",
            "parent-edge-repair",
            "contributor-key-audit",
        }.issubset({str(item.get("name") or "") for item in side_effect_intents if isinstance(item, dict)}),
        "treatment_reversible_gate_held": (
            reversible_gate.get("default_route") == "fanout-python"
            and reversible_gate.get("native_route") == PREVIEW_HEADER
            and reversible_gate.get("ordinary_traffic_flip_allowed") is False
            and reversible_gate.get("ordinary_traffic_flip_performed") is False
        ),
    }
    return CaseObservation(
        name=case.name,
        passed=all(checks.values()),
        checks=checks,
        control_status=control.status,
        control_router=control.router,
        treatment_status=treatment.status,
        treatment_router=treatment.router,
        operation=str(treatment.parsed.get("operation") or ""),
        node_id=str(treatment.parsed.get("node_id") or ""),
    )


def build_gate_report(
    observations: list[CaseObservation],
    *,
    min_confidence: float,
) -> dict[str, Any]:
    total = len(observations)
    passed = sum(1 for obs in observations if obs.passed)
    confidence = (passed / total) if total else 0.0
    gate_pass = confidence >= min_confidence and passed == total
    return {
        "gate": "native_mutation_ab_observation",
        "variant_a": "fanout-python without X-Form-Native-Preview",
        "variant_b": "native-kernel SQL preview with X-Form-Native-Preview",
        "cases": [asdict(obs) for obs in observations],
        "passed_cases": passed,
        "total_cases": total,
        "confidence": round(confidence, 4),
        "min_confidence": min_confidence,
        "gate_pass": gate_pass,
        "recommendation": (
            "promote_to_live_db_trial"
            if gate_pass
            else "hold_flip_collect_more_observations"
        ),
        "ordinary_traffic_flip_performed": False,
        "ordinary_traffic_flip_allowed": False,
        "next_evidence_needed": [
            "bind native side-effect execution carrier to mutation route runner",
            "narrow reversible public gate with rollback receipt",
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
                http_request(base_url, case, preview=False),
                http_request(base_url, case, preview=True),
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
        "# Native Mutation A/B Observation Gate",
        "",
        f"variant A: {report['variant_a']}",
        f"variant B: {report['variant_b']}",
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
            f"B={case['treatment_router']}:{case['treatment_status']} "
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
        print(f"mutation A/B observation failed: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_human(report))
    return 0 if report["gate_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
