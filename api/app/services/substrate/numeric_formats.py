"""Substrate-resident numeric format library — Python kernel.

A numeric value is composed of three pieces:

    Numeric value  =  (semantic-kind, format-recipe, encoded-value)

Format-recipes are substrate cells with `storage-hint` and `arithmetic-hint`
children. Adding a new format = a substrate write, not a kernel patch. The
recipe's NodeID is computed via content-addressing over the
(category, child-vector) shape; two recipes with identical structure share
NodeID via content-addressing.

Cross-kernel coordination lives in
``docs/coherence-substrate/numeric-formats.canonical.json``. Every kernel
(Python, TS, Go, Rust) reads that same contract and interns the formats
in the same order with the same child structure. The format-recipe NodeIDs
produced by this module match — by construction — the shape the TS kernel
produces (see ``form/form-kernel-ts/src/formats.ts``).

This file is read-time-driven by the canonical JSON: do not hardcode the
format list. Drift between contract and implementation is forbidden.

See ``docs/coherence-substrate/numeric-types-plan.md`` for the architecture.
"""
from __future__ import annotations

import functools
import json
import math
import struct
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple, Union

from sqlalchemy.orm import Session

from app.services.substrate.category import Level, RType
from app.services.substrate.kernel import DOMAIN_BLUEPRINT, NodeID, intern_node
from app.services.substrate.substrate_strings import intern_string_instance


# ---------------------------------------------------------------------------
# Enums — must match the canonical JSON exactly.
# ---------------------------------------------------------------------------


class SemanticKind(IntEnum):
    """What a number MEANS in the world. Small, stable vocabulary."""
    CARDINAL = 1
    INTEGER = 2
    RATIONAL = 3
    REAL = 4
    COMPLEX = 5
    BIT_PATTERN = 6
    LOG_VALUE = 7
    PROBABILITY = 8
    INTERVAL = 9
    ORDINAL = 10
    AMPLITUDE = 11
    PHASE = 12
    MEASURE = 13


class EncodingKind(IntEnum):
    """The encoding family. Each kind carries its own parameter shape."""
    TWOS_COMPLEMENT = 1
    SIGN_MAGNITUDE = 2
    UNSIGNED = 3
    IEEE_754 = 4
    POSIT = 5
    LOOKUP_TABLE = 6
    BLOCK_FP = 7
    LOG_SPACE = 8
    RATIONAL_PAIR = 9
    COMPLEX_PAIR = 10
    RAW_BITS = 11


class ArithHintCode(IntEnum):
    """Pre-projected arithmetic-hint integers for jump-table dispatch."""
    NATIVE_FP = 1
    NATIVE_INT = 2
    NATIVE_INT_NARROW = 3
    BIGINT = 4
    TABLE_LOOKUP_VIA_FP32 = 5
    DEQUANT_FP32_THEN_NATIVE = 6
    SOFTWARE_FP_VIA_FP32 = 7
    SOFTWARE_POSIT = 8
    XOR_POPCOUNT = 9
    LOGADDEXP_LOGSUBEXP = 10
    RATIONAL_BIGINT = 11


class ArithOpCode(IntEnum):
    """Pre-projected arithmetic operator integers."""
    ADD = 1
    SUB = 2
    MUL = 3
    DIV = 4
    MOD = 5


# String → code lookups (used during JSON ingest).
_ARITH_HINT_TO_CODE: Dict[str, int] = {
    "native-fp": ArithHintCode.NATIVE_FP,
    "native-int": ArithHintCode.NATIVE_INT,
    "native-int-narrow": ArithHintCode.NATIVE_INT_NARROW,
    "bigint": ArithHintCode.BIGINT,
    "table-lookup-via-fp32": ArithHintCode.TABLE_LOOKUP_VIA_FP32,
    "dequant-fp32-then-native": ArithHintCode.DEQUANT_FP32_THEN_NATIVE,
    "software-fp-via-fp32": ArithHintCode.SOFTWARE_FP_VIA_FP32,
    "software-posit": ArithHintCode.SOFTWARE_POSIT,
    "xor-popcount": ArithHintCode.XOR_POPCOUNT,
    "logaddexp-logsubexp": ArithHintCode.LOGADDEXP_LOGSUBEXP,
    "rational-bigint": ArithHintCode.RATIONAL_BIGINT,
}

_OP_TO_CODE: Dict[str, int] = {
    "add": ArithOpCode.ADD,
    "sub": ArithOpCode.SUB,
    "mul": ArithOpCode.MUL,
    "div": ArithOpCode.DIV,
    "mod": ArithOpCode.MOD,
}


# RBasic.FORMAT — new well-known basic category for format-recipes.
# Canonical category value matches the TS kernel (RBasicFormat = 50)
# and the JSON contract's ``format_category.rbasic_format``.
RBASIC_FORMAT = 50

# RBasic.NUMERIC — basic category for numeric leaves carrying format identity.
RBASIC_NUMERIC = 51

# Numberish — what flows through arithmetic. int and float for the in-process
# representation; int doubles as the "bigint" path since Python ints are
# arbitrary-precision natively.
Numberish = Union[int, float]
ArithOp = str  # "add" | "sub" | "mul" | "div" | "mod"


# ---------------------------------------------------------------------------
# FormatRecipe — substrate handle + structural parameters.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FormatRecipe:
    """A substrate-resident format identity.

    ``node_id`` is the content-addressed NodeID produced by interning the
    recipe's (category, children) shape. Two FormatRecipes with the same
    structural parameters intern to the same NodeID by construction.
    """
    node_id: NodeID
    name: str
    semantic_kind: int
    encoding: int
    bits: int
    storage_hint: str
    arithmetic_hint: str
    arith_hint_code: int
    # Encoding-specific extras
    mantissa_bits: Optional[int] = None
    exponent_bits: Optional[int] = None
    exponent_bias: Optional[int] = None
    posit_n: Optional[int] = None
    posit_es: Optional[int] = None
    lookup_values: Optional[Tuple[float, ...]] = None


FormatLibrary = Dict[str, FormatRecipe]


# ---------------------------------------------------------------------------
# Interning helpers — trivial children that compose into recipe children.
# ---------------------------------------------------------------------------


def _trivial_int_id(value: int) -> NodeID:
    """Encode an int as a Trivial RType.INTEGER NodeID.

    Mirrors form_builders._int_id — the existing Python convention for
    encoding integer trivials in the Python kernel. ``value + 1`` for
    non-negative values keeps the instance slot away from 0 (which means
    "undefined"); negative values currently route to instance 0 (matching
    the existing builder). For format-recipe children all values are
    non-negative (semantic kinds, encoding ints, bit widths), so the
    encoding is unambiguous.
    """
    return NodeID(1, Level.TRIVIAL, RType.INTEGER, value + 1 if value >= 0 else 0)


def _trivial_string_id(session: Session, value: str) -> NodeID:
    """Encode a string as a Trivial RType.STRING NodeID via the string-table.

    Cross-process stable — same string always maps to the same instance.
    """
    inst = intern_string_instance(session, value)
    return NodeID(1, Level.TRIVIAL, RType.STRING, inst)


def _float_to_two_i32(v: float) -> Tuple[int, int]:
    """Split an IEEE 754 double into (low-32-bits, high-32-bits), little-endian.

    Matches the canonical JSON's ``$lookup_values_encoding``:
        "Lookup values are floats. Each is encoded as two i32 children:
         the low 32 bits of the IEEE 754 double (little-endian), then
         the high 32 bits."
    """
    packed = struct.pack("<d", float(v))
    lo = int.from_bytes(packed[0:4], "little", signed=False)
    hi = int.from_bytes(packed[4:8], "little", signed=False)
    # Pass through as signed-i32-equivalent uint to match the TS encoding
    # (which does `new Uint32Array(buf)[0] | 0`).
    return lo, hi


# ---------------------------------------------------------------------------
# build_format_library — read canonical JSON, intern each recipe in order.
# ---------------------------------------------------------------------------


def _canonical_json_path() -> Path:
    """Resolve ``docs/coherence-substrate/numeric-formats.canonical.json``.

    Walks up from this file's location to the repo root, then down to the
    canonical contract. Works in worktrees and in the main repo.
    """
    here = Path(__file__).resolve()
    # api/app/services/substrate/numeric_formats.py — 5 parents up to repo root
    for parent in [here.parent] + list(here.parents):
        candidate = parent / "docs" / "coherence-substrate" / "numeric-formats.canonical.json"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "Could not locate numeric-formats.canonical.json; "
        "expected at docs/coherence-substrate/ relative to the repo root"
    )


def load_canonical_contract(path: Optional[Path] = None) -> Dict:
    """Load and parse the canonical JSON contract."""
    p = path or _canonical_json_path()
    with p.open("r") as f:
        return json.load(f)


def _intern_format_recipe(
    session: Session,
    *,
    name: str,
    semantic_kind: int,
    encoding: int,
    bits: int,
    storage_hint: str,
    arithmetic_hint: str,
    mantissa_bits: Optional[int] = None,
    exponent_bits: Optional[int] = None,
    exponent_bias: Optional[int] = None,
    posit_n: Optional[int] = None,
    posit_es: Optional[int] = None,
    lookup_values: Optional[List[float]] = None,
) -> FormatRecipe:
    """Intern one format-recipe under the canonical structural shape.

    Child order (must match the canonical contract exactly):
        [semantic_kind, encoding, bits, storage_hint, arithmetic_hint,
         mantissa_bits?, exponent_bits?, exponent_bias?,
         posit_n?, posit_es?,
         lookup_values_lo_0, lookup_values_hi_0,
         lookup_values_lo_1, lookup_values_hi_1, ...]
    """
    children: List[NodeID] = [
        _trivial_int_id(semantic_kind),
        _trivial_int_id(encoding),
        _trivial_int_id(bits),
        _trivial_string_id(session, storage_hint),
        _trivial_string_id(session, arithmetic_hint),
    ]
    if mantissa_bits is not None:
        children.append(_trivial_int_id(mantissa_bits))
    if exponent_bits is not None:
        children.append(_trivial_int_id(exponent_bits))
    if exponent_bias is not None:
        children.append(_trivial_int_id(exponent_bias))
    if posit_n is not None:
        children.append(_trivial_int_id(posit_n))
    if posit_es is not None:
        children.append(_trivial_int_id(posit_es))
    if lookup_values is not None:
        for v in lookup_values:
            lo, hi = _float_to_two_i32(float(v))
            children.append(_trivial_int_id(lo))
            children.append(_trivial_int_id(hi))

    # The format-recipe's category is RBasic.FORMAT with inst=encoding.
    # Content-addressing over (category, children) yields a stable NodeID
    # for the same recipe shape across kernels — by construction.
    category = NodeID(1, Level.BASIC, RBASIC_FORMAT, encoding)
    node_id = intern_node(session, DOMAIN_BLUEPRINT, category, children)

    return FormatRecipe(
        node_id=node_id,
        name=name,
        semantic_kind=semantic_kind,
        encoding=encoding,
        bits=bits,
        storage_hint=storage_hint,
        arithmetic_hint=arithmetic_hint,
        arith_hint_code=_ARITH_HINT_TO_CODE[arithmetic_hint],
        mantissa_bits=mantissa_bits,
        exponent_bits=exponent_bits,
        exponent_bias=exponent_bias,
        posit_n=posit_n,
        posit_es=posit_es,
        lookup_values=tuple(lookup_values) if lookup_values is not None else None,
    )


def build_format_library(
    session: Session, *, canonical_path: Optional[Path] = None
) -> FormatLibrary:
    """Intern every canonical format and return a name → FormatRecipe map.

    Order matters: the JSON's ``formats`` array is the intern order. Same
    structural shape → same NodeID (content-addressing); any drift between
    the contract and the kernel is mechanical — fix the JSON, the kernel
    follows.
    """
    contract = load_canonical_contract(canonical_path)
    sem_kinds = contract["semantic_kind"]
    encs = contract["encoding_kind"]

    lib: FormatLibrary = {}
    for entry in contract["formats"]:
        name = entry["name"]
        semantic_kind = sem_kinds[entry["semantic_kind"]]
        encoding = encs[entry["encoding"]]
        bits = entry["bits"]
        storage_hint = entry["storage_hint"]
        arithmetic_hint = entry["arithmetic_hint"]
        recipe = _intern_format_recipe(
            session,
            name=name,
            semantic_kind=semantic_kind,
            encoding=encoding,
            bits=bits,
            storage_hint=storage_hint,
            arithmetic_hint=arithmetic_hint,
            mantissa_bits=entry.get("mantissa_bits"),
            exponent_bits=entry.get("exponent_bits"),
            exponent_bias=entry.get("exponent_bias"),
            posit_n=entry.get("posit_n"),
            posit_es=entry.get("posit_es"),
            lookup_values=entry.get("lookup_values"),
        )
        lib[name] = recipe
    return lib


# ---------------------------------------------------------------------------
# Arithmetic — Pass 0 generic dispatcher.
# ---------------------------------------------------------------------------


def _narrow_int(v: int, bits: int) -> int:
    """Truncate an int to ``bits`` signed and sign-extend.

    Mirrors the TS ``narrowInt`` in semantics: produces a signed integer in
    the range ``[-2^(bits-1), 2^(bits-1) - 1]``.
    """
    if bits >= 64:
        # i64 wrap
        mask = (1 << 64) - 1
        u = v & mask
        sign_bit = 1 << 63
        return u - (1 << 64) if (u & sign_bit) else u
    if bits >= 32:
        v32 = v & 0xFFFFFFFF
        return v32 - (1 << 32) if (v32 & 0x80000000) else v32
    mask = (1 << bits) - 1
    sign_bit = 1 << (bits - 1)
    u = v & mask
    return u - (1 << bits) if (u & sign_bit) else u


def _narrow_uint(v: int, bits: int) -> int:
    """Truncate an int to ``bits`` unsigned."""
    if bits >= 64:
        return v & ((1 << 64) - 1)
    return v & ((1 << bits) - 1)


def _trunc_div(a: int, b: int) -> int:
    """C/JS-style truncated integer division (towards zero).

    Python's ``//`` floors; JS' ``(a / b) | 0`` truncates. The TS kernel
    uses the truncating form, so we mirror it.
    """
    q, r = divmod(a, b)
    if r != 0 and ((a < 0) ^ (b < 0)):
        q += 1
    return q


def apply_arith(
    fmt: FormatRecipe, op: ArithOp, a: Numberish, b: Numberish
) -> Numberish:
    """Generic dispatcher (Pass 0).

    Switches on ``arith_hint_code`` then on operator. Mirrors the logic in
    ``form/form-kernel-ts/src/formats.ts`` (``applyArithCode``)
    exactly, with Python's runtime model standing in for the V8 jump-table
    behaviour the TS comments describe.
    """
    opc = _OP_TO_CODE[op]
    hint = fmt.arith_hint_code

    if hint == ArithHintCode.NATIVE_FP:
        fa = float(a)
        fb = float(b)
        if opc == ArithOpCode.ADD:
            return fa + fb
        if opc == ArithOpCode.SUB:
            return fa - fb
        if opc == ArithOpCode.MUL:
            return fa * fb
        if opc == ArithOpCode.DIV:
            return fa / fb
        if opc == ArithOpCode.MOD:
            return fa - math.floor(fa / fb) * fb
        return 0.0

    if hint == ArithHintCode.NATIVE_INT:
        # Bitnet-158 (encoding LOOKUP_TABLE) shares this hint — operands
        # are already small ternary values, so wrap to fmt.bits=2 would
        # corrupt them. We branch on encoding to decide whether to wrap.
        if fmt.encoding == EncodingKind.LOOKUP_TABLE:
            # Pure integer arithmetic; the lookup table constrains inputs.
            ia, ib = int(a), int(b)
            if opc == ArithOpCode.ADD:
                return ia + ib
            if opc == ArithOpCode.SUB:
                return ia - ib
            if opc == ArithOpCode.MUL:
                return ia * ib
            if opc == ArithOpCode.DIV:
                return 0 if ib == 0 else _trunc_div(ia, ib)
            if opc == ArithOpCode.MOD:
                return 0 if ib == 0 else ia - _trunc_div(ia, ib) * ib
            return 0
        bits = fmt.bits if fmt.bits > 0 else 32
        narrow = min(bits, 32)
        is_signed = fmt.encoding == EncodingKind.TWOS_COMPLEMENT
        wrap = (lambda r: _narrow_int(r, narrow)) if is_signed else (lambda r: _narrow_uint(r, narrow))
        ia = wrap(int(a))
        ib = wrap(int(b))
        if opc == ArithOpCode.ADD:
            return wrap(ia + ib)
        if opc == ArithOpCode.SUB:
            return wrap(ia - ib)
        if opc == ArithOpCode.MUL:
            return wrap(ia * ib)
        if opc == ArithOpCode.DIV:
            return 0 if ib == 0 else wrap(_trunc_div(ia, ib))
        if opc == ArithOpCode.MOD:
            return 0 if ib == 0 else wrap(ia - _trunc_div(ia, ib) * ib)
        return 0

    if hint == ArithHintCode.NATIVE_INT_NARROW:
        bits = fmt.bits
        ia = _narrow_int(int(a), bits)
        ib = _narrow_int(int(b), bits)
        if opc == ArithOpCode.ADD:
            return _narrow_int(ia + ib, bits)
        if opc == ArithOpCode.SUB:
            return _narrow_int(ia - ib, bits)
        if opc == ArithOpCode.MUL:
            return _narrow_int(ia * ib, bits)
        if opc == ArithOpCode.DIV:
            return 0 if ib == 0 else _narrow_int(_trunc_div(ia, ib), bits)
        if opc == ArithOpCode.MOD:
            return 0 if ib == 0 else _narrow_int(ia - _trunc_div(ia, ib) * ib, bits)
        return 0

    if hint == ArithHintCode.BIGINT:
        # Python int is already arbitrary-precision. The format's bit width
        # tells us whether to wrap (i64/u64) for parity with kernels whose
        # native bigints don't auto-wrap on overflow either — we keep full
        # precision and let the consumer wrap if they need register-width
        # semantics. The conformance vector ``9223372036854775807n + 0n``
        # checks the value flows through unchanged.
        ia, ib = int(a), int(b)
        if opc == ArithOpCode.ADD:
            return ia + ib
        if opc == ArithOpCode.SUB:
            return ia - ib
        if opc == ArithOpCode.MUL:
            return ia * ib
        if opc == ArithOpCode.DIV:
            return 0 if ib == 0 else _trunc_div(ia, ib)
        if opc == ArithOpCode.MOD:
            return 0 if ib == 0 else ia - _trunc_div(ia, ib) * ib
        return 0

    if hint in (
        ArithHintCode.TABLE_LOOKUP_VIA_FP32,
        ArithHintCode.DEQUANT_FP32_THEN_NATIVE,
        ArithHintCode.SOFTWARE_FP_VIA_FP32,
    ):
        # Compute in fp32 — round each result through struct.pack to match
        # the TS ``Math.fround`` behavior.
        fa = float(a)
        fb = float(b)
        if opc == ArithOpCode.ADD:
            return _to_fp32(fa + fb)
        if opc == ArithOpCode.SUB:
            return _to_fp32(fa - fb)
        if opc == ArithOpCode.MUL:
            return _to_fp32(fa * fb)
        if opc == ArithOpCode.DIV:
            return _to_fp32(fa / fb)
        if opc == ArithOpCode.MOD:
            return _to_fp32(fa - math.floor(fa / fb) * fb)
        return 0.0

    if hint == ArithHintCode.LOGADDEXP_LOGSUBEXP:
        la = float(a)
        lb = float(b)
        if opc == ArithOpCode.ADD:
            m = max(la, lb)
            return m + math.log1p(math.exp(-abs(la - lb)))
        if opc == ArithOpCode.SUB:
            if lb >= la:
                return float("-inf")
            return la + math.log1p(-math.exp(lb - la))
        if opc == ArithOpCode.MUL:
            return la + lb
        if opc == ArithOpCode.DIV:
            return la - lb
        if opc == ArithOpCode.MOD:
            raise ValueError("log-prob: mod not defined")
        return 0.0

    if hint == ArithHintCode.XOR_POPCOUNT:
        ia = int(a) & 1
        ib = int(b) & 1
        if opc == ArithOpCode.ADD or opc == ArithOpCode.SUB:
            return (ia ^ ib) & 1
        if opc == ArithOpCode.MUL:
            return ia & ib & 1
        return 0

    if hint in (ArithHintCode.SOFTWARE_POSIT, ArithHintCode.RATIONAL_BIGINT):
        raise NotImplementedError(
            f"arithmetic-hint {fmt.arithmetic_hint}: not yet implemented"
        )

    raise ValueError(f"apply_arith: unknown arith_hint_code {hint}")


def _to_fp32(v: float) -> float:
    """Round a Python float to fp32 precision (analogue of Math.fround)."""
    return struct.unpack("<f", struct.pack("<f", v))[0]


# ---------------------------------------------------------------------------
# FormatTable — handle assignment + (format, op) handler cache (Pass 1).
# ---------------------------------------------------------------------------


def _compile_handler(
    fmt: FormatRecipe, op: ArithOp
) -> Callable[[Numberish, Numberish], Numberish]:
    """Build a specialized (a, b) -> result closure for one (format, op).

    For Python this is ``functools.partial`` over ``apply_arith`` — the
    runtime doesn't JIT like V8, but the cache reduces the dispatch path
    on the hot path to a single Map lookup + indirect call. Subsequent
    optimization (specializing per arith_hint_code via inlined closures)
    is a follow-on; the architectural piece is the cache itself.
    """
    hint = fmt.arith_hint_code
    opc = _OP_TO_CODE[op]

    # Specialize the most-hit hint codes with inline closures. Python's
    # local-variable bytecode is faster than the IntEnum-dispatch chain
    # above, so a per-hint closure outperforms the generic dispatcher
    # on the hot path even without a JIT.
    if hint == ArithHintCode.NATIVE_FP:
        if opc == ArithOpCode.ADD:
            return lambda a, b: float(a) + float(b)
        if opc == ArithOpCode.SUB:
            return lambda a, b: float(a) - float(b)
        if opc == ArithOpCode.MUL:
            return lambda a, b: float(a) * float(b)
        if opc == ArithOpCode.DIV:
            return lambda a, b: float(a) / float(b)
        if opc == ArithOpCode.MOD:
            return lambda a, b: float(a) - math.floor(float(a) / float(b)) * float(b)

    if hint == ArithHintCode.NATIVE_INT and fmt.encoding == EncodingKind.TWOS_COMPLEMENT:
        bits = min(fmt.bits, 32) if fmt.bits > 0 else 32
        if opc == ArithOpCode.ADD:
            return lambda a, b, _b=bits: _narrow_int(int(a) + int(b), _b)
        if opc == ArithOpCode.SUB:
            return lambda a, b, _b=bits: _narrow_int(int(a) - int(b), _b)
        if opc == ArithOpCode.MUL:
            return lambda a, b, _b=bits: _narrow_int(int(a) * int(b), _b)

    if hint == ArithHintCode.NATIVE_INT and fmt.encoding == EncodingKind.LOOKUP_TABLE:
        # Bitnet-158 — no wrap, just integer arithmetic on ternary values.
        if opc == ArithOpCode.ADD:
            return lambda a, b: int(a) + int(b)
        if opc == ArithOpCode.MUL:
            return lambda a, b: int(a) * int(b)
        if opc == ArithOpCode.SUB:
            return lambda a, b: int(a) - int(b)

    if hint == ArithHintCode.BIGINT:
        if opc == ArithOpCode.ADD:
            return lambda a, b: int(a) + int(b)
        if opc == ArithOpCode.SUB:
            return lambda a, b: int(a) - int(b)
        if opc == ArithOpCode.MUL:
            return lambda a, b: int(a) * int(b)

    if hint == ArithHintCode.XOR_POPCOUNT:
        if opc == ArithOpCode.ADD or opc == ArithOpCode.SUB:
            return lambda a, b: (int(a) ^ int(b)) & 1
        if opc == ArithOpCode.MUL:
            return lambda a, b: int(a) & int(b) & 1

    if hint == ArithHintCode.LOGADDEXP_LOGSUBEXP:
        if opc == ArithOpCode.MUL:
            return lambda a, b: float(a) + float(b)
        if opc == ArithOpCode.DIV:
            return lambda a, b: float(a) - float(b)

    # Fallback: bind through the generic dispatcher.
    return functools.partial(apply_arith, fmt, op)


class FormatTable:
    """Sequential format-handle assignment + per-(format, op) handler cache.

    Cross-kernel agreement requires the handle order to be deterministic
    per the canonical bootstrap library; ``register_library`` walks the
    library dict in insertion order (which Python preserves), so the same
    bootstrap reproduces the same handle assignment.
    """

    def __init__(self) -> None:
        self._by_handle: List[FormatRecipe] = []
        self._by_nodeid: Dict[str, int] = {}
        self._handlers: Dict[Tuple[int, str], Callable[[Numberish, Numberish], Numberish]] = {}

    def register(self, fmt: FormatRecipe) -> int:
        key = str(fmt.node_id)
        if key in self._by_nodeid:
            return self._by_nodeid[key]
        h = len(self._by_handle)
        self._by_handle.append(fmt)
        self._by_nodeid[key] = h
        return h

    def get(self, handle: int) -> Optional[FormatRecipe]:
        if 0 <= handle < len(self._by_handle):
            return self._by_handle[handle]
        return None

    def handler(
        self, handle: int, op: ArithOp
    ) -> Callable[[Numberish, Numberish], Numberish]:
        """Pass 1 monomorphization: cache a specialized closure per (format, op).

        Cold path: compile via ``_compile_handler``, store, return. Hot path:
        a dict lookup and an indirect call — no IntEnum dispatch.
        """
        key = (handle, op)
        cached = self._handlers.get(key)
        if cached is not None:
            return cached
        fmt = self._by_handle[handle]
        fn = _compile_handler(fmt, op)
        self._handlers[key] = fn
        return fn

    def register_library(self, lib: FormatLibrary) -> None:
        """Register every format in the library, assigning handles in order."""
        for fmt in lib.values():
            self.register(fmt)


# ---------------------------------------------------------------------------
# canonicalize — apply the format's canonical-form rules.
# ---------------------------------------------------------------------------


# Canonical quiet NaN bit pattern (IEEE 754 binary64). Different platforms
# emit different NaN payloads; ``float("nan")`` is the standard one and the
# canonical form is a single sentinel value.
_CANONICAL_NAN = float("nan")


def canonicalize(fmt: FormatRecipe, v: Numberish) -> Numberish:
    """Apply the format's canonical-form rules to a value.

    For floating formats: NaN -> canonical quiet NaN, -0.0 -> +0.0.
    For integer/exotic formats: pass through (no canonicalization needed
    beyond the encoding's own bit-pattern uniqueness).
    """
    if fmt.arithmetic_hint in (
        "native-fp",
        "table-lookup-via-fp32",
        "dequant-fp32-then-native",
        "software-fp-via-fp32",
        "logaddexp-logsubexp",
    ):
        f = float(v)
        if math.isnan(f):
            return _CANONICAL_NAN
        if f == 0.0:
            # collapses -0.0 -> +0.0
            return 0.0
        return f
    return v


# ---------------------------------------------------------------------------
# Convenience: bootstrap + register in one call.
# ---------------------------------------------------------------------------


def bootstrap(
    session: Session, *, canonical_path: Optional[Path] = None
) -> Tuple[FormatLibrary, FormatTable]:
    """Build the canonical library and register it into a fresh FormatTable."""
    lib = build_format_library(session, canonical_path=canonical_path)
    table = FormatTable()
    table.register_library(lib)
    return lib, table
