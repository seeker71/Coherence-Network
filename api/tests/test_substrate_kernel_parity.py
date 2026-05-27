"""Substrate ↔ kernel parity — the kernel reaches the lattice and agrees.

Demonstrates that the form-kernel-rust binary can pull substrate data
(via http_get + _json_to_dict natives) and compute the same total that
the Python `lattice_stats(session)` caller would. The first closing
breath of the kernel-as-substrate-aware-compute arc.

Pattern proven here:
    1. Python builds the lattice and asks `lattice_stats(session)`.
    2. The same response is JSON-encoded and fed to the kernel.
    3. The kernel walks (_json_to_dict body) + (_get d "..."), sums.
    4. Kernel total == Python total → the transmute holds.

The HTTP wire-up itself (`http_get(url)` against a live FastAPI server)
is exercised indirectly: we hand the kernel the JSON body the endpoint
would return, so the substrate-and-server stay decoupled from the
parity assertion. The live-HTTP path runs the same natives — see
form/form-kernel-ts/seedbank/python-adapter/examples/endpoint_lattice_stats_live.fk.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.substrate import (
    ingest_memory_file,
    lattice_stats,
)
from app.services.substrate.orm import SubstrateNamedCellORM, SubstrateNodeORM
from app.services.substrate.substrate_strings import SubstrateStringORM


KERNEL_BIN = (
    Path(__file__).resolve().parents[2]
    / "form" / "form-kernel-rust" / "target" / "release" / "form-kernel-rust"
)


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SubstrateNodeORM.__table__.create(engine, checkfirst=True)
    SubstrateNamedCellORM.__table__.create(engine, checkfirst=True)
    SubstrateStringORM.__table__.create(engine, checkfirst=True)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        yield s
        s.commit()
    finally:
        s.close()


MEMORY_BODY = """---
name: {name}
type: memory
---

Body for {name}.
"""


@pytest.mark.skipif(
    not KERNEL_BIN.exists(),
    reason="form-kernel-rust binary not built (cargo build --release)",
)
def test_lattice_stats_kernel_parity(session, tmp_path):
    """Kernel-side total over /api/substrate/lattice/stats == Python-side."""
    # Build a small lattice so the counts aren't all zero — proves the
    # parity claim against real numbers, not against degenerate empty
    # state where every implementation trivially agrees.
    for name in ("alpha", "beta", "gamma"):
        p = tmp_path / f"{name}.md"
        p.write_text(MEMORY_BODY.format(name=name))
        ingest_memory_file(session, p)

    python_stats = lattice_stats(session)
    python_total = (
        python_stats["blueprints_total"]
        + python_stats["recipes_total"]
        + python_stats["cells_total"]
    )

    # Render the substrate's response exactly as the FastAPI endpoint
    # would; the kernel sees the wire bytes, not the Python object.
    response_json = json.dumps(python_stats)

    # The transmuted recipe: parse the JSON into a kernel dict, then
    # sum the three counts. This is what the live endpoint would do
    # given (http_get url) → body.
    expr = (
        '(do '
        f'(let body {json.dumps(response_json)}) '
        '(let stats (_json_to_dict body)) '
        '(_plus (_plus (_get stats "blueprints_total") '
        '(_get stats "recipes_total")) '
        '(_get stats "cells_total")))'
    )

    result = subprocess.run(
        [str(KERNEL_BIN), "--expr", expr],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, (
        f"kernel exited {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    kernel_total = int(result.stdout.strip().splitlines()[-1])
    assert kernel_total == python_total, (
        f"kernel total {kernel_total} != python total {python_total} "
        f"(stats: {python_stats})"
    )


@pytest.mark.skipif(
    not KERNEL_BIN.exists() or shutil.which("curl") is None,
    reason="form-kernel-rust binary or curl not available",
)
def test_http_get_native_returns_null_on_unreachable():
    """http_get returns null when the remote can't be reached.

    Documents the kernel's failure semantics so Form code that calls
    http_get can pattern-match against null without surprise.
    """
    expr = '(http_get "http://127.0.0.1:1/does-not-exist")'
    result = subprocess.run(
        [str(KERNEL_BIN), "--expr", expr],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert result.stdout.strip().splitlines()[-1] == "null"


def test_json_to_dict_round_trip():
    """_json_to_dict on the kernel matches Python's json.loads on flat objs.

    Uses subprocess so the assertion runs the same code path the live
    transmute would. Catches regressions where the native silently
    starts dropping keys or coercing ints to strings.
    """
    if not KERNEL_BIN.exists():
        pytest.skip("form-kernel-rust binary not built")

    sample = {"a": 1, "b": 2, "c": 7, "d": -5}
    body = json.dumps(sample)
    expected_total = sum(sample.values())

    expr = (
        '(do '
        f'(let body {json.dumps(body)}) '
        '(let d (_json_to_dict body)) '
        '(_plus (_plus (_plus (_get d "a") (_get d "b")) (_get d "c")) (_get d "d")))'
    )
    result = subprocess.run(
        [str(KERNEL_BIN), "--expr", expr],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert int(result.stdout.strip().splitlines()[-1]) == expected_total
