#!/usr/bin/env python3
"""A/B observation gate for native mutation preview/default routes.

This turns the mutation flip into measurement before movement. It starts a
local mock CPython upstream, starts the production kernel-router manifest in
front of it, and sends each mutation shape twice:

  A: no native mutation header       -> must accept native-default invitation
                                         and execute through throwaway Postgres.
  B: X-Form-Native-Preview present   -> must return native SQL preview.
  C: X-Form-Python-Fallback present  -> must fan out as explicit control.

No production database is touched. The harness self-provisions throwaway
Postgres and passes it through the kernel config carrier. The output is a
confidence report showing native default persistence, preview observation, and
explicit fallback as separate branches.
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
PYTHON_FALLBACK_HEADER = "X-Form-Python-Fallback"
IMPLICIT_NATIVE_PROTOCOL = "implicit-native-invitation"

if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from mutation_public_gate_harness import (  # noqa: E402
    cleanup_kernel_config,
    persistence_readback_checks,
    provision_postgres,
    reset_schema,
    seed_case,
    stop_postgres,
    write_kernel_config,
)


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
    default_status: int
    default_router: str
    treatment_status: int
    treatment_router: str
    fallback_status: int
    fallback_router: str
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


def http_request(
    base_url: str,
    case: ObservationCase,
    *,
    preview: bool = False,
    fallback: bool = False,
) -> HTTPObservation:
    data = case.body.encode("utf-8") if case.body else None
    headers = {"Content-Type": "application/json"}
    if preview:
        headers[PREVIEW_HEADER] = "1"
    if fallback:
        headers[PYTHON_FALLBACK_HEADER] = "1"
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


def default_http_request(base_url: str, case: ObservationCase, *, dsn: str) -> tuple[HTTPObservation, dict[str, bool]]:
    reset_schema(dsn)
    seed_case(dsn, case)
    observation = http_request(base_url, case)
    checks = persistence_readback_checks(dsn, case) if observation.status == 202 else {}
    return observation, checks


def evaluate_case(
    case: ObservationCase,
    default: HTTPObservation,
    treatment: HTTPObservation,
    fallback: HTTPObservation,
    *,
    default_db_checks: dict[str, bool] | None = None,
) -> CaseObservation:
    default_sql = str(default.parsed.get("sql") or "")
    sql = str(treatment.parsed.get("sql") or "")
    default_decision = default.parsed.get("decision_receipt")
    if not isinstance(default_decision, dict):
        default_decision = {}
    default_invitation = default.parsed.get("native_invitation")
    if not isinstance(default_invitation, dict):
        default_invitation = {}
    default_invitation_translated = default_invitation.get("translated")
    if not isinstance(default_invitation_translated, dict):
        default_invitation_translated = {}
    default_invitation_execution = default_invitation.get("execution")
    if not isinstance(default_invitation_execution, dict):
        default_invitation_execution = {}
    default_invitation_speak = default_invitation.get("speak_next_time")
    if not isinstance(default_invitation_speak, dict):
        default_invitation_speak = {}
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
        "default_native": default.router == "native-kernel",
        "default_status_ok": default.status == 202,
        "default_invitation_declared": default.parsed.get("native_default_invitation") is True,
        "default_required_header_absent": default.parsed.get("required_header") is None,
        "default_fallback_header_named": default.parsed.get("fallback_header") == PYTHON_FALLBACK_HEADER,
        "default_selected_path": default_decision.get("selected_path") == IMPLICIT_NATIVE_PROTOCOL,
        "default_native_invitation_receipt": (
            default_invitation.get("state") == "native-invitation-contract"
            and default_invitation.get("offer_to_know") is True
            and default_invitation.get("refusal_is_signal") is True
            and default_invitation_translated.get("language") == "Form-native mutation recipe"
            and default_invitation_translated.get("operation") == case.operation
            and default_invitation_execution.get("selected_path") == IMPLICIT_NATIVE_PROTOCOL
            and default_invitation_speak.get("fallback_header") == PYTHON_FALLBACK_HEADER
            and default_invitation.get("decline_signal") == "native_invitation_declined"
        ),
        "default_sql_shape": all(part in default_sql for part in case.sql_contains),
        "default_body_seen": default.parsed.get("request_body", "") == (case.body or "{}"),
        "default_executes_persistence": default.parsed.get("executes") is True,
        "default_db_execution": default.parsed.get("db_execution")
        == "performed-by-http-native-persistence",
        "fallback_fanned_out": fallback.router == "fanout-python",
        "fallback_status_ok": fallback.status == 200,
        "fallback_method_seen": fallback.parsed.get("method") == case.method,
        "fallback_path_seen": fallback.parsed.get("path") == case.path,
        "fallback_body_seen": fallback.parsed.get("body", "") == case.body,
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
            and trust_envelope.get("silence") == "not-knowing-is-native-invitation"
            and trust_envelope.get("protocol") == PREVIEW_HEADER
            and trust_envelope.get("fail") == "explicit-python-fallback"
            and trust_envelope.get("stop") == "native-default-observed"
            and trust_envelope.get("bma") == "native-mutation-trust-envelope"
        ),
        "treatment_side_effect_intents_carried": {
            "cache-invalidation",
            "parent-edge-repair",
            "contributor-key-audit",
            "idea-valuation-audit-ledger",
        }.issubset({str(item.get("name") or "") for item in side_effect_intents if isinstance(item, dict)}),
        "treatment_reversible_gate_held": (
            reversible_gate.get("default_route") == "native-kernel"
            and reversible_gate.get("default_protocol") == IMPLICIT_NATIVE_PROTOCOL
            and reversible_gate.get("native_route") == PREVIEW_HEADER
            and reversible_gate.get("fallback_route") == PYTHON_FALLBACK_HEADER
            and reversible_gate.get("ordinary_traffic_flip_allowed") is True
            and reversible_gate.get("ordinary_traffic_flip_performed") is True
        ),
        **{f"default_{name}": ok for name, ok in (default_db_checks or {}).items()},
    }
    return CaseObservation(
        name=case.name,
        passed=all(checks.values()),
        checks=checks,
        default_status=default.status,
        default_router=default.router,
        treatment_status=treatment.status,
        treatment_router=treatment.router,
        fallback_status=fallback.status,
        fallback_router=fallback.router,
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
        "variant_a": "native-kernel implicit invitation without native mutation headers",
        "variant_b": "native-kernel SQL preview with X-Form-Native-Preview",
        "variant_c": "fanout-python explicit fallback with X-Form-Python-Fallback",
        "cases": [asdict(obs) for obs in observations],
        "passed_cases": passed,
        "total_cases": total,
        "confidence": round(confidence, 4),
        "min_confidence": min_confidence,
        "gate_pass": gate_pass,
        "recommendation": (
            "preview_confidence_complete"
            if gate_pass
            else "hold_flip_collect_more_observations"
        ),
        "ordinary_traffic_flip_performed": gate_pass,
        "ordinary_traffic_flip_allowed": True,
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
            default, default_db_checks = default_http_request(base_url, case, dsn=pg.dsn)
            observations.append(
                evaluate_case(
                    case,
                    default,
                    http_request(base_url, case, preview=True),
                    http_request(base_url, case, fallback=True),
                    default_db_checks=default_db_checks,
                )
            )
        return build_gate_report(observations, min_confidence=min_confidence)
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
        "# Native Mutation A/B Observation Gate",
        "",
        f"variant A: {report['variant_a']}",
        f"variant B: {report['variant_b']}",
        f"variant C: {report['variant_c']}",
        f"confidence: {report['confidence']:.4f} ({report['passed_cases']}/{report['total_cases']} cases)",
        f"gate_pass: {report['gate_pass']}",
        f"recommendation: {report['recommendation']}",
        f"ordinary_traffic_flip_performed: {str(report['ordinary_traffic_flip_performed']).lower()}",
        "",
        "cases:",
    ]
    for case in report["cases"]:
        lines.append(
            f"  - {case['name']}: {'pass' if case['passed'] else 'fail'} "
            f"A={case['default_router']}:{case['default_status']} "
            f"B={case['treatment_router']}:{case['treatment_status']} "
            f"C={case['fallback_router']}:{case['fallback_status']} "
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
                "gate": "native_mutation_ab_observation",
                "gate_pass": False,
                "skipped": True,
                "skip_reason": str(exc),
            }
            if args.json:
                print(json.dumps(report, indent=2, sort_keys=True))
            else:
                print(str(exc))
            return 0
        print(f"mutation A/B observation failed: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_human(report))
    return 0 if report["gate_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
