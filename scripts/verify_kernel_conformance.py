"""Verify substrate kernel conformance vectors against executable runtimes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

REPO_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPO_ROOT / "api"
sys.path.insert(0, str(API_ROOT))

from app.services.agent_question_service import (  # noqa: E402
    answer_question,
    get_question_events,
    reset_agent_questions,
)
from app.services.substrate.form_runtime import (  # noqa: E402
    form_execute_text,
    reset_runtime_registries,
)
from app.services.substrate.orm import SubstrateNamedCellORM, SubstrateNodeORM  # noqa: E402
from app.services.substrate.substrate_strings import SubstrateStringORM  # noqa: E402

DEFAULT_VECTOR = (
    REPO_ROOT
    / "docs"
    / "coherence-substrate"
    / "kernel-conformance"
    / "agent-question-effects.json"
)


class ConformanceError(AssertionError):
    """Raised when a kernel result diverges from the conformance vector."""


def load_vector(path: Path = DEFAULT_VECTOR) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _make_session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SubstrateNodeORM.__table__.create(engine, checkfirst=True)
    SubstrateNamedCellORM.__table__.create(engine, checkfirst=True)
    SubstrateStringORM.__table__.create(engine, checkfirst=True)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _replace_placeholders(text: str, *, question_id: str | None) -> str:
    if question_id is None:
        return text
    return text.replace("${question_id}", question_id)


def _assert_subset(expected: Any, actual: Any, path: str = "$") -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            raise ConformanceError(
                f"{path}: expected object, got {type(actual).__name__}"
            )
        for key, value in expected.items():
            if key not in actual:
                raise ConformanceError(f"{path}: missing key {key!r}")
            _assert_subset(value, actual[key], f"{path}.{key}")
        return
    if isinstance(expected, list):
        if not isinstance(actual, list):
            raise ConformanceError(
                f"{path}: expected list, got {type(actual).__name__}"
            )
        if len(expected) != len(actual):
            raise ConformanceError(
                f"{path}: expected list length {len(expected)}, got {len(actual)}"
            )
        for index, (expected_item, actual_item) in enumerate(zip(expected, actual)):
            _assert_subset(expected_item, actual_item, f"{path}[{index}]")
        return
    if expected != actual:
        raise ConformanceError(f"{path}: expected {expected!r}, got {actual!r}")


def _run_python_case(session: Session, case: dict[str, Any]) -> dict[str, Any]:
    reset_runtime_registries()
    reset_agent_questions()
    question_id: str | None = None
    setup = case.get("setup") or {}

    try:
        if setup.get("open_question_form"):
            opened = form_execute_text(session, str(setup["open_question_form"]))
            question_id = opened["id"]
            if "answer" in setup:
                answer_question(
                    question_id=question_id,
                    answer=str(setup["answer"]),
                    answered_by=str(setup.get("answered_by", "conformance")),
                )

        form = _replace_placeholders(str(case["form"]), question_id=question_id)
        value = form_execute_text(session, form)
        if isinstance(value, dict) and question_id is None:
            question_id = str(value.get("id") or "")

        _assert_subset(case.get("expected_value"), value, "$.expected_value")

        events = get_question_events()
        expected_events = case.get("expected_events") or []
        if len(events) != len(expected_events):
            raise ConformanceError(
                f"events: expected {len(expected_events)}, got {len(events)}"
            )
        for index, expected_event in enumerate(expected_events):
            _assert_subset(expected_event, events[index], f"$.expected_events[{index}]")

        return {
            "name": case["name"],
            "status": "pass",
            "question_id": question_id,
            "events": [event["event_type"] for event in events],
        }
    finally:
        reset_runtime_registries()
        reset_agent_questions()


def run_python_kernel(vector: dict[str, Any]) -> dict[str, Any]:
    session = _make_session()
    try:
        cases = [_run_python_case(session, case) for case in vector.get("cases", [])]
    finally:
        session.close()
    return {"kernel": "python", "status": "pass", "cases": cases}


def run_kernel(
    vector: dict[str, Any],
    kernel_name: str,
    *,
    allow_targets: bool = False,
) -> dict[str, Any]:
    kernels = vector.get("kernels") or {}
    kernel = kernels.get(kernel_name)
    if kernel is None:
        raise ConformanceError(f"unknown kernel {kernel_name!r}")

    status = str(kernel.get("status") or "")
    if kernel_name == "python" and status == "implemented":
        return run_python_kernel(vector)

    if status == "conformance-target":
        result = {
            "kernel": kernel_name,
            "status": "skipped",
            "reason": "kernel is a conformance target with no executable runner",
        }
        if allow_targets:
            return result
        raise ConformanceError(
            f"{kernel_name} is target-only; add an executable runner before "
            "requiring it in conformance"
        )

    raise ConformanceError(f"{kernel_name} has unsupported status {status!r}")


def _selected_kernels(vector: dict[str, Any], requested: list[str]) -> list[str]:
    if requested:
        return requested
    kernels = vector.get("kernels") or {}
    return [
        name
        for name, data in kernels.items()
        if str((data or {}).get("status") or "") == "implemented"
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run substrate kernel conformance vectors."
    )
    parser.add_argument("--vector", type=Path, default=DEFAULT_VECTOR)
    parser.add_argument(
        "--kernel",
        action="append",
        default=[],
        help="Kernel to run. Defaults to implemented kernels only.",
    )
    parser.add_argument(
        "--allow-targets",
        action="store_true",
        help="Return skipped for target-only kernels instead of failing.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args(argv)

    try:
        vector = load_vector(args.vector)
        results = [
            run_kernel(vector, kernel, allow_targets=args.allow_targets)
            for kernel in _selected_kernels(vector, args.kernel)
        ]
    except (ConformanceError, OSError, json.JSONDecodeError) as exc:
        if args.json:
            print(json.dumps({"status": "fail", "error": str(exc)}, indent=2))
        else:
            print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    payload = {
        "status": "pass",
        "surface": vector.get("surface"),
        "kernels": results,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for result in results:
            print(f"{result['kernel']}: {result['status']}")
            for case in result.get("cases", []):
                print(f"  - {case['name']}: {case['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
