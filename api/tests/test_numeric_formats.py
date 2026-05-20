"""Tests for the substrate-resident numeric format library (Python kernel).

Covers:
- Every format in the canonical JSON interns to a NodeID
- Content-addressing: the same recipe shape interns once (idempotent)
- All conformance vectors from the canonical JSON pass
- Canonicalization: NaN and -0 collapse to canonical forms
- Cross-kernel structural agreement: format NodeID children match the
  shape the TS kernel produces (same category, same child count, same
  child ordering — exercised by the JSON contract being the only source
  of truth)
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.substrate.numeric_formats import (
    ArithHintCode,
    ArithOpCode,
    EncodingKind,
    FormatRecipe,
    FormatTable,
    SemanticKind,
    apply_arith,
    bootstrap,
    build_format_library,
    canonicalize,
    load_canonical_contract,
)
from app.services.substrate.orm import SubstrateNamedCellORM, SubstrateNodeORM
from app.services.substrate.substrate_strings import SubstrateStringORM


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def session():
    """In-memory SQLite session with the substrate tables."""
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


@pytest.fixture
def contract():
    return load_canonical_contract()


# ---------------------------------------------------------------------------
# Format library — every format interns, has a stable NodeID.
# ---------------------------------------------------------------------------


def test_build_format_library_interns_every_format(session, contract):
    lib = build_format_library(session)
    expected_names = {f["name"] for f in contract["formats"]}
    assert set(lib.keys()) == expected_names
    for name, fmt in lib.items():
        assert isinstance(fmt, FormatRecipe)
        assert fmt.node_id is not None
        assert fmt.node_id.level >= 1
        assert fmt.name == name


def test_format_recipe_idempotent_intern(session):
    """Interning the canonical library twice yields the same NodeIDs.

    Content-addressing: identical (category, children) shape → identical
    NodeID. The second pass should find every recipe already present.
    """
    lib_a = build_format_library(session)
    lib_b = build_format_library(session)
    assert lib_a.keys() == lib_b.keys()
    for name in lib_a:
        assert lib_a[name].node_id == lib_b[name].node_id, (
            f"format {name} re-interned to a different NodeID — "
            f"content-addressing broken"
        )


def test_format_recipe_distinct_per_format(session):
    lib = build_format_library(session)
    node_ids = {fmt.node_id for fmt in lib.values()}
    assert len(node_ids) == len(lib), (
        "two distinct formats collapsed to the same NodeID — child shape collision"
    )


def test_arith_hint_codes_match_contract(session, contract):
    """Every format's arith_hint_code matches the JSON's arith_hint_code map."""
    lib = build_format_library(session)
    expected = contract["arith_hint_code"]
    for name, fmt in lib.items():
        assert fmt.arith_hint_code == expected[fmt.arithmetic_hint], (
            f"format {name}: arith_hint_code drift"
        )


# ---------------------------------------------------------------------------
# Conformance vectors — every vector from the canonical JSON passes.
# ---------------------------------------------------------------------------


def _parse_operand(v):
    """Parse an operand: BigInt strings like '1000n' become Python ints."""
    if isinstance(v, str) and v.endswith("n"):
        return int(v[:-1])
    return v


def _epsilon_for_format(name: str) -> float:
    if name in ("fp64", "log-prob"):
        return 1e-12
    if name == "fp32":
        return 1e-6
    if name in ("bf16", "fp8-e4m3", "fp8-e5m2", "fp4-uniform", "nf4"):
        return 1e-2
    return 0.0


@pytest.mark.parametrize("idx", range(15))
def test_conformance_vectors(session, contract, idx):
    vectors = contract["conformance_vectors"]["vectors"]
    if idx >= len(vectors):
        pytest.skip("vector index out of range")
    v = vectors[idx]
    lib = build_format_library(session)
    fmt = lib[v["format"]]
    a = _parse_operand(v["a"])
    b = _parse_operand(v["b"])
    expected = _parse_operand(v["expected"])
    actual = apply_arith(fmt, v["op"], a, b)
    if isinstance(expected, float) or isinstance(actual, float):
        eps = _epsilon_for_format(v["format"])
        assert abs(float(actual) - float(expected)) <= eps, (
            f"{v['format']} {v['op']}({a}, {b}) = {actual}, expected {expected}"
        )
    else:
        assert actual == expected, (
            f"{v['format']} {v['op']}({a}, {b}) = {actual}, expected {expected}"
        )


# ---------------------------------------------------------------------------
# Canonicalization
# ---------------------------------------------------------------------------


def test_canonicalize_nan_collapses(session):
    lib = build_format_library(session)
    fp64 = lib["fp64"]
    nan_a = float("nan")
    nan_b = float("nan")
    ca = canonicalize(fp64, nan_a)
    cb = canonicalize(fp64, nan_b)
    assert math.isnan(ca) and math.isnan(cb)
    # We can't compare NaN with == (NaN != NaN by IEEE), but both are NaN
    # and both come from the same canonical sentinel.
    import struct
    assert struct.pack("<d", ca) == struct.pack("<d", cb), (
        "canonical NaN representations differ"
    )


def test_canonicalize_negative_zero_collapses(session):
    lib = build_format_library(session)
    fp64 = lib["fp64"]
    pos = canonicalize(fp64, 0.0)
    neg = canonicalize(fp64, -0.0)
    assert pos == 0.0 and neg == 0.0
    import struct
    assert struct.pack("<d", pos) == struct.pack("<d", neg), (
        "+0.0 and -0.0 should canonicalize to the same bit pattern"
    )


def test_canonicalize_integer_passthrough(session):
    lib = build_format_library(session)
    i32 = lib["i32"]
    assert canonicalize(i32, 42) == 42


# ---------------------------------------------------------------------------
# FormatTable — handles + Pass 1 handler cache.
# ---------------------------------------------------------------------------


def test_format_table_handle_assignment(session):
    lib = build_format_library(session)
    table = FormatTable()
    table.register_library(lib)
    # Insertion order is canonical JSON order; the first registered should
    # be fp64.
    assert table.get(0).name == "fp64"
    # Registering again returns the same handle.
    handle = table.register(lib["fp64"])
    assert handle == 0


def test_format_table_handler_cache(session):
    lib = build_format_library(session)
    table = FormatTable()
    table.register_library(lib)
    h = table.register(lib["fp64"])
    h1 = table.handler(h, "add")
    h2 = table.handler(h, "add")
    assert h1 is h2, "handler cache not returning identity-stable closures"


def test_format_table_handler_correctness(session):
    """Cached handlers produce the same results as the generic dispatcher."""
    lib = build_format_library(session)
    table = FormatTable()
    table.register_library(lib)
    fp64 = lib["fp64"]
    i32 = lib["i32"]
    bitnet = lib["bitnet-158"]

    h_fp64 = table.handler(table.register(fp64), "mul")
    assert abs(h_fp64(0.1, 0.2) - apply_arith(fp64, "mul", 0.1, 0.2)) < 1e-15

    h_i32 = table.handler(table.register(i32), "mul")
    assert h_i32(65536, 65536) == apply_arith(i32, "mul", 65536, 65536) == 0

    h_bit = table.handler(table.register(bitnet), "mul")
    assert h_bit(-1, -1) == apply_arith(bitnet, "mul", -1, -1) == 1


# ---------------------------------------------------------------------------
# Cross-kernel structural agreement — same recipe shape across kernels.
# ---------------------------------------------------------------------------


def test_format_recipe_children_match_canonical_order(session, contract):
    """The intern call's child vector follows the canonical contract.

    Children are: [semantic_kind, encoding, bits, storage_hint,
    arithmetic_hint, ...extras]. The extras follow ``children_after_required``:
    mantissa_bits, exponent_bits, exponent_bias, posit_n, posit_es,
    lookup_values. Lookup values are 2 children each (low, high i32).

    We verify by counting the number of children in the persisted recipe
    matches the count the contract implies.
    """
    from app.services.substrate.kernel import lookup_node
    lib = build_format_library(session)
    for entry in contract["formats"]:
        name = entry["name"]
        fmt = lib[name]
        orm = lookup_node(session, fmt.node_id)
        assert orm is not None, f"recipe for {name} not persisted"
        # serialized format: "category+child1+child2+..."
        # 5 required children + optional extras
        n_extras = sum(
            1
            for k in ("mantissa_bits", "exponent_bits", "exponent_bias", "posit_n", "posit_es")
            if k in entry
        )
        if "lookup_values" in entry:
            n_extras += 2 * len(entry["lookup_values"])
        expected_children = 5 + n_extras
        actual_children = orm.serialized.count("+")
        assert actual_children == expected_children, (
            f"{name}: expected {expected_children} children in serialized "
            f"recipe, got {actual_children}: {orm.serialized}"
        )


def test_all_canonical_formats_have_distinct_signatures(session, contract):
    """No two formats in the canonical JSON should share a structural shape.

    Tested by interning and asserting all NodeIDs are distinct (already
    checked above), plus a structural-signature check on the JSON itself.
    """
    sigs = []
    for entry in contract["formats"]:
        sig = (
            entry["semantic_kind"],
            entry["encoding"],
            entry["bits"],
            entry["storage_hint"],
            entry["arithmetic_hint"],
            entry.get("mantissa_bits"),
            entry.get("exponent_bits"),
            entry.get("exponent_bias"),
            tuple(entry.get("lookup_values") or ()),
        )
        sigs.append((entry["name"], sig))
    sig_set = {s for _, s in sigs}
    assert len(sig_set) == len(sigs), (
        f"canonical JSON has structurally-identical formats: {sigs}"
    )


# ---------------------------------------------------------------------------
# Performance: Pass 0 (generic dispatch) vs Pass 1 (cached handler).
# ---------------------------------------------------------------------------


def _bench(fn, iters: int) -> float:
    """Return microseconds per op."""
    t0 = time.perf_counter()
    for _ in range(iters):
        fn()
    t1 = time.perf_counter()
    return (t1 - t0) * 1e6 / iters


def test_performance_pass0_vs_pass1(session, capsys):
    """Pass 1 (cached handler) should not be slower than Pass 0 (dispatch)."""
    lib = build_format_library(session)
    table = FormatTable()
    table.register_library(lib)

    fp64 = lib["fp64"]
    i32 = lib["i32"]
    bitnet = lib["bitnet-158"]

    ITERS = 20000

    # Pass 0 — direct apply_arith
    pass0_fp64 = _bench(lambda: apply_arith(fp64, "mul", 1.5, 2.25), ITERS)
    pass0_i32 = _bench(lambda: apply_arith(i32, "add", 1000, 2000), ITERS)
    pass0_bit = _bench(lambda: apply_arith(bitnet, "mul", 1, -1), ITERS)

    # Pass 1 — cached handler
    h_fp64 = table.handler(table.register(fp64), "mul")
    h_i32 = table.handler(table.register(i32), "add")
    h_bit = table.handler(table.register(bitnet), "mul")
    pass1_fp64 = _bench(lambda: h_fp64(1.5, 2.25), ITERS)
    pass1_i32 = _bench(lambda: h_i32(1000, 2000), ITERS)
    pass1_bit = _bench(lambda: h_bit(1, -1), ITERS)

    with capsys.disabled():
        print(
            "\n[numeric_formats perf]\n"
            f"  fp64    mul  Pass 0: {pass0_fp64:.3f} us/op   Pass 1: {pass1_fp64:.3f} us/op\n"
            f"  i32     add  Pass 0: {pass0_i32:.3f} us/op   Pass 1: {pass1_i32:.3f} us/op\n"
            f"  bitnet  mul  Pass 0: {pass0_bit:.3f} us/op   Pass 1: {pass1_bit:.3f} us/op\n"
        )

    # Sanity: Pass 1 should be at least as fast as Pass 0 (within noise).
    # Generous slack — 3x — because lambda invocation under perf_counter
    # is noisy at sub-microsecond scales.
    assert pass1_fp64 <= pass0_fp64 * 3.0
    assert pass1_i32 <= pass0_i32 * 3.0
    assert pass1_bit <= pass0_bit * 3.0


# ---------------------------------------------------------------------------
# Sanity: bootstrap convenience returns lib + table.
# ---------------------------------------------------------------------------


def test_bootstrap_returns_lib_and_table(session):
    lib, table = bootstrap(session)
    assert "fp64" in lib
    assert table.get(0) is not None
    # All formats from the library are registered in the table.
    for name, fmt in lib.items():
        h = table.register(fmt)
        assert table.get(h).name == name


# ---------------------------------------------------------------------------
# Enum agreement with the contract.
# ---------------------------------------------------------------------------


def test_enums_match_canonical_contract(contract):
    for name, val in contract["semantic_kind"].items():
        assert SemanticKind[name].value == val
    for name, val in contract["encoding_kind"].items():
        assert EncodingKind[name].value == val
    enum_name_map = {
        "native-fp": "NATIVE_FP",
        "native-int": "NATIVE_INT",
        "native-int-narrow": "NATIVE_INT_NARROW",
        "bigint": "BIGINT",
        "table-lookup-via-fp32": "TABLE_LOOKUP_VIA_FP32",
        "dequant-fp32-then-native": "DEQUANT_FP32_THEN_NATIVE",
        "software-fp-via-fp32": "SOFTWARE_FP_VIA_FP32",
        "software-posit": "SOFTWARE_POSIT",
        "xor-popcount": "XOR_POPCOUNT",
        "logaddexp-logsubexp": "LOGADDEXP_LOGSUBEXP",
        "rational-bigint": "RATIONAL_BIGINT",
    }
    for hint_str, val in contract["arith_hint_code"].items():
        assert ArithHintCode[enum_name_map[hint_str]].value == val
    op_name_map = {"add": "ADD", "sub": "SUB", "mul": "MUL", "div": "DIV", "mod": "MOD"}
    for op_str, val in contract["arith_op_code"].items():
        assert ArithOpCode[op_name_map[op_str]].value == val
