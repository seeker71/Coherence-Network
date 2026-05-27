"""Form kernel bridge — shell into form-kernel-rust for endpoint bodies.

The transmutation gesture, made into a habit: a FastAPI endpoint's body
is a Form recipe compiled from Python. The route delegates to the kernel
binary instead of executing Python inline. FastAPI stays as the HTTP
doorway; the computation IS a Recipe.

Companion to form/form-kernel-ts/seedbank/python-adapter/examples/
endpoint_*_demo.py — every endpoint that transmutes its body lands a
.fk recipe next to a .py demo, both verified by parity_suite.sh.

If the kernel binary is unavailable (build missing in container), the
caller's fallback Python function runs. Same result either path —
parity_suite.sh is the regression gate.

The habit form. Three layers, each shorter to reach for than the last:

    run_recipe(fk_source)               # raw kernel call — testable
    run_with_fallback(fk, fb, parse)    # add Python fallback + parse
    serve_via_kernel(                   # load .fk from disk, inject
        recipe_path,                    #   inputs as (let ...) bindings,
        bindings={"x": 5, "ys": [1,2]}, #   shell to kernel or fall back
        fallback=lambda: my_py_fn(...),
        parse=int,
    )

A new transmuted endpoint should need ~5 lines: load recipe path, build
bindings dict, call serve_via_kernel, return the response model. The
recipe body itself lives next to its Python twin under
form-kernel-ts/seedbank/python-adapter/examples/ — single source of
truth, parity-tested across CPython / TS evalPython / form-kernel-rust.
"""
from __future__ import annotations

import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable, Mapping

logger = logging.getLogger(__name__)

_KERNEL_BIN_ENV = "FORM_KERNEL_RUST_BIN"
# Default path: repo-relative to api/app/services/, four levels up to repo
# root, then into form/form-kernel-rust/target/release/form-kernel-rust.
_DEFAULT_KERNEL_BIN = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "form"
    / "form-kernel-rust"
    / "target"
    / "release"
    / "form-kernel-rust"
)


def kernel_bin_path() -> Path:
    """Return the path to the form-kernel-rust binary."""
    override = os.environ.get(_KERNEL_BIN_ENV)
    if override:
        return Path(override)
    return _DEFAULT_KERNEL_BIN


def kernel_available() -> bool:
    """True when the kernel binary is on disk and executable."""
    p = kernel_bin_path()
    return p.is_file() and os.access(p, os.X_OK)


def run_recipe(fk_source: str, timeout: float = 10.0) -> str:
    """Run a Form recipe through form-kernel-rust, return stdout's last line.

    fk_source is the textual .fk content — a top-level (do ...) form whose
    final expression's value is the kernel's printed result.

    Raises RuntimeError if the kernel binary is missing or the run fails.
    """
    bin_path = kernel_bin_path()
    if not kernel_available():
        raise RuntimeError(f"form-kernel-rust binary not found at {bin_path}")

    with tempfile.NamedTemporaryFile("w", suffix=".fk", delete=False) as f:
        f.write(fk_source)
        fk_path = f.name

    try:
        proc = subprocess.run(
            [str(bin_path), fk_path],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    finally:
        try:
            os.unlink(fk_path)
        except OSError:
            pass

    if proc.returncode != 0:
        raise RuntimeError(
            f"form-kernel-rust failed (exit {proc.returncode}): {proc.stderr.strip()}"
        )
    out = proc.stdout.rstrip("\n").splitlines()
    if not out:
        raise RuntimeError("form-kernel-rust produced no output")
    return out[-1]


def run_with_fallback(
    fk_source: str,
    fallback: Callable[[], Any],
    parse: Callable[[str], Any] = lambda s: s,
    timeout: float = 10.0,
) -> tuple[Any, str]:
    """Run fk_source through the kernel; fall back to Python on missing binary.

    Returns (value, runtime) where runtime is "form-kernel-rust" or
    "python-fallback". Errors from the kernel beyond the binary-missing
    case propagate — the parity_suite guarantees the recipe matches
    Python; an actual kernel failure is a real problem worth surfacing.
    """
    if not kernel_available():
        logger.info(
            "form-kernel-rust binary missing at %s — falling back to Python",
            kernel_bin_path(),
        )
        return fallback(), "python-fallback"
    raw = run_recipe(fk_source, timeout=timeout)
    return parse(raw), "form-kernel-rust"


# ---------------------------------------------------------------------------
# Higher-level helpers — make transmutation easy enough to be a habit.
#
# Recipe templates live as .fk files alongside their Python twins under
# form/form-kernel-ts/seedbank/python-adapter/examples/. The shape is
# always a top-level (do ...) form whose trailing (let NAME ...) bindings
# carry the inputs, followed by the final expression that produces the
# result. We inject inputs by rewriting those trailing bindings — the
# recipe body itself never changes.
# ---------------------------------------------------------------------------


# Repo-root-relative path to the seedbank examples directory.
_SEEDBANK_EXAMPLES = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "form"
    / "form-kernel-ts"
    / "seedbank"
    / "python-adapter"
    / "examples"
)


def seedbank_examples_dir() -> Path:
    """Return the absolute path to the python-adapter examples directory."""
    return _SEEDBANK_EXAMPLES


def load_recipe(recipe_path: str | Path) -> str:
    """Load a .fk recipe source.

    A bare filename (e.g. "endpoint_coherence_weight_demo.fk") resolves
    against the python-adapter seedbank examples directory — the canonical
    home for transmuted-endpoint recipes. Absolute paths are honored as-is.
    """
    p = Path(recipe_path)
    if not p.is_absolute():
        p = _SEEDBANK_EXAMPLES / p
    return p.read_text(encoding="utf-8")


def _fk_literal(value: Any) -> str:
    """Render a Python value as an .fk literal.

    Supported: int, float, bool, str, list of supported. Strings get
    Lisp-style double-quote escaping. Lists become (list ...) forms.
    Anything else raises TypeError — the kernel's value model is small
    and deliberate.
    """
    if isinstance(value, bool):
        # bool before int — Python bool is an int subclass.
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        # Format matches the kernel's Python-flavored float printer:
        # always include a decimal point so the parser reads it as float.
        s = repr(value)
        if "." not in s and "e" not in s and "E" not in s and "nan" not in s and "inf" not in s:
            s = s + ".0"
        return s
    if isinstance(value, str):
        # Lisp string literal — escape backslash and double-quote.
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, (list, tuple)):
        if not value:
            return "(list)"
        return "(list " + " ".join(_fk_literal(v) for v in value) + ")"
    raise TypeError(f"_fk_literal: unsupported type {type(value).__name__}")


# Matches `(let NAME` at the head of a binding form. The value expression
# that follows is balanced by paren-counting (regexes can't balance), and
# the closing `)` of the `(let ...)` form is found by counting parens
# from the opening `(`.
_LET_HEAD = re.compile(r"\(let\s+([A-Za-z_][A-Za-z0-9_]*)\s")


def _scan_balanced(src: str, start: int) -> int:
    """Return the index just past the `)` that closes the `(` at start.

    Raises ValueError on unbalanced input — the recipe source is malformed.
    """
    depth = 0
    i = start
    n = len(src)
    while i < n:
        c = src[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ValueError(f"unbalanced parens starting at {start}")


def inject_bindings(recipe_source: str, bindings: Mapping[str, Any]) -> str:
    """Replace `(let NAME ...)` bindings with new literal values.

    Walks the recipe source looking for `(let NAME ...)` forms whose
    NAME matches a key in `bindings`, and rewrites the whole form to
    `(let NAME <fk-literal>)`. Paren-balanced replacement — the value
    expression can be arbitrarily nested. Recipes generated by the
    python-adapter end with input bindings followed by the result
    expression; this is the contract.

    Any binding key that doesn't appear in the recipe raises KeyError
    so the caller learns immediately their input doesn't match the
    recipe's shape (rather than the kernel running stale literals).
    """
    matched: set[str] = set()
    out_parts: list[str] = []
    cursor = 0
    for m in _LET_HEAD.finditer(recipe_source):
        name = m.group(1)
        if name not in bindings:
            continue
        # Find the closing `)` of this (let ...) form, starting from `(`.
        end = _scan_balanced(recipe_source, m.start())
        out_parts.append(recipe_source[cursor : m.start()])
        out_parts.append(f"(let {name} {_fk_literal(bindings[name])})")
        cursor = end
        matched.add(name)
    out_parts.append(recipe_source[cursor:])
    missing = set(bindings) - matched
    if missing:
        raise KeyError(
            f"inject_bindings: recipe has no (let ...) for: {sorted(missing)}"
        )
    return "".join(out_parts)


def serve_via_kernel(
    recipe_path: str | Path,
    bindings: Mapping[str, Any],
    fallback: Callable[[], Any],
    parse: Callable[[str], Any] = lambda s: s,
    timeout: float = 10.0,
) -> tuple[Any, str]:
    """Load a recipe, inject inputs, run on the kernel — or fall back.

    The end-state ergonomic API for transmuting an endpoint. A handler
    builds a `bindings` dict from its parsed inputs, names the .fk file,
    provides a Python fallback, and gets `(value, runtime)` back. The
    runtime string is the response-model field that lets clients see
    which path actually served them.

    Example:

        weight, runtime = serve_via_kernel(
            "endpoint_coherence_weight_demo.fk",
            bindings={"values": parsed, "threshold": threshold},
            fallback=lambda: coherence_weight_py(parsed, threshold),
            parse=int,
        )
    """
    fk_source = load_recipe(recipe_path)
    if bindings:
        fk_source = inject_bindings(fk_source, bindings)
    return run_with_fallback(fk_source, fallback=fallback, parse=parse, timeout=timeout)
