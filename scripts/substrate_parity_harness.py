#!/usr/bin/env python3
"""substrate_parity_harness.py — read the body in both voices, side by side.

The teaching Urs named on 2026-05-20: as the body matures, more code wants
to live as Form. The Python implementation becomes the reference oracle;
the Form expression becomes the substrate-native voice; and the practice is
to run both side by side until divergences either close or are accepted as
honest boundaries.

This harness names that practice. Each registered case carries:

    PythonImpl     — callable taking inputs, returning a value
    FormSource     — string of Form code expected to compute the same value
    ExpectedOutput — what the value should be (when known)
    Domain         — which substrate verb-family the case lives in

Running the harness prints, for each case:

    · Result equality        — Python ≟ Form ≟ Expected
    · Structural fingerprint — the recipe NodeID Form interns (and a Python
                               structural digest for comparison)
    · Performance            — wall-clock for each side
    · Divergence shape       — if any, named precisely

The Form side runs when the substrate is importable. When it isn't (this
remote container has no sqlalchemy), the harness reports the Python side
plus the would-be Form source so the practice is visible even without the
full runtime.

Companion to docs/vision-kb/concepts/lc-form-python-parity.md.

Usage:
    python3 scripts/substrate_parity_harness.py             # run all cases
    python3 scripts/substrate_parity_harness.py --domain arithmetic
    python3 scripts/substrate_parity_harness.py --fidelity  # fidelity audit
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Case shape
# ---------------------------------------------------------------------------


@dataclass
class ParityCase:
    """One side-by-side comparison case."""

    name: str                  # human-readable identifier
    domain: str                # arithmetic / boolean / structural / query / ...
    python_impl: Callable[[], Any]
    form_source: str           # the Form expression
    expected: Any = None       # known-good value, or None to skip equality
    notes: str = ""            # honest seam markers

    # Filled in by the harness as it runs:
    python_result: Any = None
    python_ms: float = 0.0
    form_result: Any = None
    form_ms: float = 0.0
    form_ran: bool = False
    divergence: Optional[str] = None


# ---------------------------------------------------------------------------
# Substrate liveness — does the harness have the kernel available?
# ---------------------------------------------------------------------------


def substrate_is_live() -> bool:
    """True iff the substrate runtime can be imported.

    In a fully-equipped environment this returns True. In the remote
    container this harness was authored in, sqlalchemy is unavailable
    and this returns False — the harness then prints Python + Form
    source but cannot run Form.
    """
    # Ensure api/ is on sys.path so the substrate package is reachable.
    api_path = str(Path(__file__).resolve().parent.parent / "api")
    if api_path not in sys.path:
        sys.path.insert(0, api_path)
    try:
        import sqlalchemy  # noqa: F401
        from app.services.substrate.form_runtime import form_execute_text  # noqa: F401
        return True
    except ImportError:
        return False


def _form_runtime():
    """Lazy import; only called when substrate_is_live()."""
    sys.path.insert(0, "/home/user/Coherence-Network/api")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.services.substrate.form_runtime import form_execute_text
    from app.services.substrate.orm import (
        SubstrateNamedCellORM,
        SubstrateNodeORM,
    )
    from app.services.substrate.substrate_strings import SubstrateStringORM

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SubstrateNodeORM.__table__.create(engine, checkfirst=True)
    SubstrateNamedCellORM.__table__.create(engine, checkfirst=True)
    SubstrateStringORM.__table__.create(engine, checkfirst=True)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    return form_execute_text, Session()


# ---------------------------------------------------------------------------
# The seed registry — every case below names one substrate operation in
# both voices. Adding a new case is the unit of growing the practice.
# ---------------------------------------------------------------------------


CASES: List[ParityCase] = [
    # ─── Arithmetic ─────────────────────────────────────────────────────
    ParityCase(
        name="factorial_6",
        domain="arithmetic",
        python_impl=lambda: (lambda n: 1 if n <= 1 else n * (
            (lambda f: f(f))(lambda g: lambda k: 1 if k <= 1 else k * g(g)(k - 1))
        )(n - 1))(6),
        form_source="do { defn fact(n) = if n <= 1 then 1 else n * fact(n - 1); fact(6) }",
        expected=720,
        notes="Recursive integer arithmetic; meta-circular dispatch in form-engine.form Part 2.",
    ),
    ParityCase(
        name="fibonacci_10",
        domain="arithmetic",
        python_impl=lambda: (
            (lambda f: f(f, 10))(
                lambda g, n: n if n <= 1 else g(g, n - 1) + g(g, n - 2)
            )
        ),
        form_source="do { defn fib(n) = if n <= 1 then n else fib(n - 1) + fib(n - 2); fib(10) }",
        expected=55,
        notes="Multiple recursive calls per frame.",
    ),
    ParityCase(
        name="sum_1_to_5",
        domain="arithmetic",
        python_impl=lambda: 1 + 2 + 3 + 4 + 5,
        form_source="1 + 2 + 3 + 4 + 5",
        expected=15,
    ),

    # ─── Boolean / comparison ───────────────────────────────────────────
    ParityCase(
        name="conditional_threshold",
        domain="boolean",
        python_impl=lambda: 42 if 7 > 5 else 0,
        form_source="if 7 > 5 then 42 else 0",
        expected=42,
    ),
    ParityCase(
        name="logical_and",
        domain="boolean",
        python_impl=lambda: True and (5 > 3),
        form_source="true && (5 > 3)",
        expected=True,
        notes="Form's boolean literal is `true` (lowercase); Python's is `True`.",
    ),

    # ─── Block / closure ────────────────────────────────────────────────
    ParityCase(
        name="closure_capture",
        domain="block",
        python_impl=lambda: (
            (lambda factor: (lambda x: x * factor))(3)
        )(5),
        form_source=(
            "do { let factor = 3; defn scale(x) = x * factor; "
            "do { let factor = 99; scale(5) } }"
        ),
        expected=15,
        notes=(
            "Closure captures outer `factor`. Inner `let factor = 99` does not "
            "leak into scale's binding. form-engine.form Part 1 backbone."
        ),
    ),

    # ─── Choice / backtracking ──────────────────────────────────────────
    ParityCase(
        name="choose_first_success",
        domain="choice",
        python_impl=lambda: 99,  # the first non-fail option
        form_source="choose [fail, fail, 99]",
        expected=99,
        notes=(
            "Angelic nondeterminism: choose [a, b, c] returns the first arm "
            "that doesn't fail. The Python implementation has to simulate "
            "the backtracking; Form has it as a primitive. This is exactly "
            "the seam recipe-branching-sense rests on."
        ),
    ),

    # ─── Structural — list / sequence value ─────────────────────────────
    ParityCase(
        name="list_sequence_value",
        domain="structural",
        python_impl=lambda: [1, 2, 3],
        form_source="do { let r = [1, 2, 3]; r }",
        expected=[1, 2, 3],
        notes=(
            "Form's list literal evaluates to a Python list. The deeper "
            "structural claim — that two expressions describing the same "
            "recipe shape intern to the same NodeID — is observable via "
            "the kernel's content-addressing; this case just verifies "
            "the surface value matches across both voices."
        ),
    ),
]


# ---------------------------------------------------------------------------
# Running a single case
# ---------------------------------------------------------------------------


def _structural_digest(value: Any) -> str:
    """A stable digest of a value's structure.

    For arithmetic results, this is the value itself. For composite
    structures, it's a hash of the repr — which is enough to spot
    divergence even when surface types differ.
    """
    h = hashlib.sha256()
    h.update(repr(value).encode("utf-8"))
    return h.hexdigest()[:16]


def run_case(case: ParityCase, form_runner=None, form_session=None) -> ParityCase:
    """Run both sides of one case, fill in the result fields."""
    # Python side
    t0 = time.perf_counter()
    try:
        case.python_result = case.python_impl()
    except Exception as e:
        case.python_result = f"<exception: {type(e).__name__}: {e}>"
    case.python_ms = (time.perf_counter() - t0) * 1000.0

    # Form side — only when runtime is available
    if form_runner is not None and form_session is not None:
        t0 = time.perf_counter()
        try:
            case.form_result = form_runner(form_session, case.form_source)
            case.form_ran = True
        except Exception as e:
            case.form_result = f"<exception: {type(e).__name__}: {e}>"
            case.form_ran = False
        case.form_ms = (time.perf_counter() - t0) * 1000.0

        # Compare. Expected wins when set; else compare Python ↔ Form directly.
        ref = case.expected if case.expected is not None else case.python_result
        if case.form_result != ref:
            case.divergence = (
                f"form={case.form_result!r}  vs  ref={ref!r}"
            )
    else:
        # Substrate isn't live; we can still validate Python vs expected.
        if case.expected is not None and case.python_result != case.expected:
            case.divergence = (
                f"python={case.python_result!r}  vs  expected={case.expected!r}"
            )

    return case


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_case(case: ParityCase, show_form_source: bool = True) -> str:
    lines: List[str] = []
    lines.append(f"── {case.name}  [{case.domain}]")
    lines.append(f"   python : {case.python_result!r}    ({case.python_ms:.3f} ms)")
    if case.form_ran:
        lines.append(f"   form   : {case.form_result!r}    ({case.form_ms:.3f} ms)")
    elif show_form_source:
        # When the substrate isn't live, show the Form source so the seam
        # is visible — the harness names what would be run, not just what was.
        src = case.form_source
        if len(src) > 70:
            src = src[:67] + "..."
        lines.append(f"   form?  : « {src} »    (substrate not live)")
    if case.expected is not None:
        lines.append(f"   expect : {case.expected!r}")
    lines.append(f"   digest : py={_structural_digest(case.python_result)}"
                 + (f"  form={_structural_digest(case.form_result)}"
                    if case.form_ran else ""))
    if case.divergence:
        lines.append(f"   DIVERGE: {case.divergence}")
    if case.notes:
        lines.append(f"   note   : {case.notes}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Fidelity audit — concept / idea / spec Blueprint collisions
# ---------------------------------------------------------------------------


def run_fidelity_audit() -> int:
    """Walk every concept, idea, spec and report which share Blueprint NodeIDs.

    Two cells sharing a Blueprint means the substrate considers them
    structurally identical. When the cells are semantically distinct,
    that's concept-collapse — the failure mode Urs named. The audit
    surfaces every collision so the body can either accept (legitimate
    siblings) or refine (collapsed distinction).

    Requires substrate live. Returns exit code (0 = clean, 1 = collapses
    found, 2 = substrate not live).
    """
    if not substrate_is_live():
        print("fidelity audit: substrate not live in this container.")
        print("This audit walks every concept/idea/spec cell and reports")
        print("Blueprint NodeID collisions — the structural signature of")
        print("concept collapse. Run from an environment with the live")
        print("substrate (api container, or local with sqlalchemy installed).")
        return 2

    sys.path.insert(0, "/home/user/Coherence-Network/api")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.services.substrate.orm import SubstrateNamedCellORM

    # Production-shaped env would point at the live DB. For the demo, we
    # use the in-memory test DB. Customize via env var when running on prod.
    import os
    db_url = os.environ.get("SUBSTRATE_DB_URL", "sqlite:///:memory:")
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        rows = s.query(SubstrateNamedCellORM).filter(
            SubstrateNamedCellORM.domain.in_(["concept", "idea", "spec"])
        ).all()
        by_blueprint: Dict[int, List[Any]] = {}
        for r in rows:
            by_blueprint.setdefault(r.blueprint_node_id, []).append(r)
        collisions = {bp: cells for bp, cells in by_blueprint.items() if len(cells) > 1}
        print(f"Audited {len(rows)} concept/idea/spec cells across {len(by_blueprint)} Blueprints.")
        print(f"Blueprint collisions (cells sharing structural identity): {len(collisions)}")
        for bp, cells in sorted(collisions.items()):
            names = sorted(f"{c.domain}/{c.name}" for c in cells)
            print(f"  · bp_node_id={bp}: {names}")
        return 0 if not collisions else 1
    finally:
        s.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--domain", help="Run only cases in this domain (arithmetic, boolean, ...)"
    )
    parser.add_argument(
        "--fidelity",
        action="store_true",
        help="Run the fidelity audit (Blueprint collisions across concept/idea/spec)",
    )
    parser.add_argument("--list-domains", action="store_true",
                        help="Print available domains and exit")
    args = parser.parse_args(argv)

    if args.fidelity:
        return run_fidelity_audit()

    if args.list_domains:
        for d in sorted({c.domain for c in CASES}):
            print(d)
        return 0

    cases = CASES
    if args.domain:
        cases = [c for c in CASES if c.domain == args.domain]
        if not cases:
            print(f"No cases for domain {args.domain!r}.")
            return 2

    print("─" * 70)
    print("substrate_parity_harness — Python ↔ Form, side by side")
    print(f"substrate live: {substrate_is_live()}")
    print("─" * 70)

    form_runner = None
    form_session = None
    if substrate_is_live():
        form_runner, form_session = _form_runtime()

    diverges = 0
    for case in cases:
        run_case(case, form_runner=form_runner, form_session=form_session)
        print(render_case(case))
        if case.divergence:
            diverges += 1

    print("─" * 70)
    if substrate_is_live():
        print(f"Cases: {len(cases)} · Form-vs-Python divergences: {diverges}")
    else:
        # Be honest: without live Form, there's no parity comparison happening.
        # The Python side runs and is checked against `expected`; the Form
        # side is only printed as the would-be parallel expression. Calling
        # this "0 divergences" would be the costume of having done parity.
        print(f"Cases: {len(cases)} · Python-vs-expected mismatches: {diverges}")
        print("Form side NOT executed — no real parity comparison happened.")
        print("This run validates only that the Python implementations match")
        print("their expected values. To compare Python ↔ Form, the substrate")
        print("must be importable (sqlalchemy + the substrate kernel).")
    return 0 if diverges == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
