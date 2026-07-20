"""Form execution bridge — run recipes on the c-bootstrapped fkwu kernel.

The compatibility API still hosts HTTP, but every transmuted endpoint body is
a Form recipe executed directly by c-bootstrapped fkwu. Go,
Rust, and TypeScript are differential oracles for primitives and native
assumptions; none is selectable as a production execution carrier.

Shared kernel recipes remain beside their Python twins under
form/form-kernel-ts/seedbank/python-adapter/examples/ and are verified by
parity_suite.sh. Coherence Network-owned endpoint recipes live with the API
under api/app/form_recipes/. A bare recipe name resolves to the app home first,
then to the shared coherence-kernel seedbank.

The habit form. Three layers, each shorter to reach for than the last:

    run_recipe(fk_source)                 # raw fkwu execution
    run_kernel(fk_source, parse)          # fkwu execution + result coercion
    serve_via_kernel(                     # load .fk from disk, inject
        recipe_path,                      #   inputs as (let ...) bindings,
        bindings={"x": 5, "ys": [1,2]},   #   run through the kernel
        parse=int,
    )

A new transmuted endpoint should need ~5 lines: load recipe path, build
bindings dict, call serve_via_kernel, return the response model. Network-owned
endpoint recipes live under api/app/form_recipes/. Reusable recipes with a
cross-runtime Python twin belong upstream in coherence-kernel's seedbank, where
they remain differential-tested across the sibling reference walkers and fkwu.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any, Callable, Mapping

def preload_available() -> bool:
    """Compatibility readout: sibling-kernel preload is not an execution path."""
    return False


def inline_available() -> bool:
    """Compatibility readout: the retired Rust inline runtime is disabled."""
    return False


def active_runtime() -> str:
    """Name the kernel path that would serve the next transmuted endpoint.

    Reads as ``fkwu`` or ``unavailable``. Sibling walkers never appear here:
    they are cross-check witnesses, not runtime candidates.
    """
    if _kernel_binary_available_lazy():
        return "fkwu"
    return "unavailable"


def _kernel_binary_available_lazy() -> bool:
    """Same as ``kernel_available()`` but never raises — for health probes."""
    try:
        return kernel_available()
    except Exception:
        return False

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_IMAGE_ROOT = Path("/app")


def _wrapper_path() -> Path:
    """Resolve the host membrane that stages source for generic fkwu."""
    for candidate in (
        _REPO_ROOT / "bin" / "form-cli",
        _IMAGE_ROOT / "bin" / "form-cli",
    ):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    return _REPO_ROOT / "bin" / "form-cli"


def kernel_bin_path() -> Path:
    """Return the direct-source fkwu binary used by recipe execution."""
    image = _IMAGE_ROOT / "form" / "fkwu"
    if image.is_file() and os.access(image, os.X_OK):
        return image
    checkout = _REPO_ROOT / "form" / "fkwu"
    if checkout.is_file() and os.access(checkout, os.X_OK):
        return checkout
    cache = _REPO_ROOT / "form" / ".cache" / "fkwu-runtime"
    candidates = sorted(cache.glob("fkwu-*"), key=lambda path: path.stat().st_mtime)
    return candidates[-1] if candidates else cache / "fkwu-unbuilt"


def kernel_available() -> bool:
    """True when direct fkwu is executable or its pinned bootstrap can build."""
    p = kernel_bin_path()
    wrapper = _wrapper_path()
    source = _REPO_ROOT / "form" / "runtime" / "fkwu-uni.c"
    header = _REPO_ROOT / "form" / "runtime" / "fkwu-optable.h"
    return (
        wrapper.is_file()
        and os.access(wrapper, os.X_OK)
        and (
            (p.is_file() and os.access(p, os.X_OK))
            or (source.is_file() and header.is_file())
        )
    )


def run_recipe(fk_source: str, timeout: float = 10.0) -> str:
    """Run a Form recipe through c-bootstrapped fkwu, return its root value.

    fk_source is the textual .fk content — a top-level (do ...) form whose
    final expression's value is the kernel's printed result.

    Go, Rust, and TypeScript do not enter this path.
    """
    bin_path = kernel_bin_path()
    if not kernel_available():
        raise RuntimeError(f"c-bootstrapped fkwu binary not found at {bin_path}")

    proc = subprocess.run(
        [str(_wrapper_path()), "eval", fk_source],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    if proc.returncode != 0:
        raise RuntimeError(
            f"fkwu failed (exit {proc.returncode}): {proc.stderr.strip()}"
        )
    out = proc.stdout.rstrip("\n").splitlines()
    if not out:
        raise RuntimeError("fkwu produced no output")
    return out[0]


def run_inline(fk_source: str) -> Any:
    """The sibling Rust inline carrier is intentionally unavailable."""
    raise RuntimeError("sibling kernels are differential witnesses, not runtimes")


def run_kernel(
    fk_source: str,
    parse: Callable[[str], Any] = lambda s: s,
    timeout: float = 10.0,
) -> tuple[Any, str]:
    """Run source on the one production kernel and return ``(..., 'fkwu')``."""
    if kernel_available():
        raw = run_recipe(fk_source, timeout=timeout)
        return parse(raw), "fkwu"

    raise RuntimeError(
        f"c-bootstrapped fkwu runtime unavailable at {kernel_bin_path()}"
    )


# ---------------------------------------------------------------------------
# Higher-level helpers — make transmutation easy enough to be a habit.
#
# Shared recipe templates live as .fk files alongside their Python twins under
# form/form-kernel-ts/seedbank/python-adapter/examples/. Network-owned endpoint
# recipes live under api/app/form_recipes/. The shape is always a top-level
# (do ...) form whose trailing (let NAME ...) bindings carry the inputs,
# followed by the final expression that produces the result. We inject inputs
# by rewriting those trailing bindings — the recipe body itself never changes.
# ---------------------------------------------------------------------------


# Repo-root-relative path to the seedbank examples directory.
#
# In a source checkout, api/app/services/form_kernel_bridge.py sits four levels
# below the repo root, so four `.parent` hops land on the root and the seedbank
# tree resolves directly. In the deploy image, Dockerfile.api flattens `api/`
# onto /app (COPY api/ ./), so the bridge lives at /app/app/services/... and the
# same four hops reach `/` — a DIFFERENT place than the source layout. The image
# path is therefore an explicit file-backed candidate, not environment config.
_SEEDBANK_EXAMPLES_DEFAULT = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "form"
    / "form-kernel-ts"
    / "seedbank"
    / "python-adapter"
    / "examples"
)
_APP_RECIPES_DIR = Path(__file__).resolve().parent.parent / "form_recipes"


def seedbank_examples_dir() -> Path:
    """Return the absolute path to the python-adapter examples directory.

    Selects the baked-in image directory when present, otherwise the source
    checkout directory. Both are pinned files from the same submodule commit.
    """
    image = (
        _IMAGE_ROOT
        / "form"
        / "form-kernel-ts"
        / "seedbank"
        / "python-adapter"
        / "examples"
    )
    if image.is_dir():
        return image
    return _SEEDBANK_EXAMPLES_DEFAULT


def app_recipes_dir() -> Path:
    """Return the API-owned Form recipe directory."""
    return _APP_RECIPES_DIR


def resolve_recipe_path(recipe_path: str | Path) -> Path:
    """Resolve an absolute path or a bare recipe name through its two homes.

    Coherence Network-owned recipes take precedence under ``api/app``. A name
    not present there falls through to the shared coherence-kernel seedbank,
    preserving the same pinned source identity in checkout and deploy image.
    """
    p = Path(recipe_path)
    if p.is_absolute():
        return p
    app_path = app_recipes_dir() / p
    if app_path.is_file():
        return app_path
    return seedbank_examples_dir() / p


def load_recipe(recipe_path: str | Path) -> str:
    """Load a .fk recipe source.

    A bare filename resolves against the API-owned recipe directory first,
    then the shared python-adapter seedbank. Absolute paths are honored as-is.
    """
    p = resolve_recipe_path(recipe_path)
    return p.read_text(encoding="utf-8")


def _as_field_dict(value: Any) -> dict | None:
    """Normalize a model / object into a flat ``{field: value}`` dict, or None.

    The bridge's answer to the object-OR-dict polymorphism the blocked functions
    carry (``_safe_float(obj, f)`` reads ``obj.f`` from a model *or* ``obj[f]``
    from a dict). Rather than teach the kernel both access paths, we DISSOLVE the
    branch HERE: every structured value is normalized to one first-order fkwu
    dictionary value, so the recipe reads fields homogeneously through ``_get``.
    A dict passes through; a Pydantic model becomes ``model_dump()``;
    a plain object with ``__dict__`` becomes its instance attributes. Anything
    without a field view returns None (the caller treats it as a leaf value).
    """
    if isinstance(value, dict):
        return value
    # Pydantic v2 model — the canonical structured-input shape for API data.
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        try:
            d = dump()
        except Exception:
            d = None
        if isinstance(d, dict):
            return d
    # Pydantic v1 — .dict(); kept for any models still on the old base.
    legacy = getattr(value, "dict", None)
    if callable(legacy) and not isinstance(value, (list, tuple, str, bytes)):
        try:
            d = legacy()
        except Exception:
            d = None
        if isinstance(d, dict):
            return d
    # A plain object (dataclass instance, simple namespace) — its __dict__ is the
    # field view. Excludes builtins (int/str/list have no useful __dict__).
    obj_dict = getattr(value, "__dict__", None)
    if isinstance(obj_dict, dict) and obj_dict:
        return dict(obj_dict)
    return None


def _fk_literal(value: Any) -> str:
    """Render a Python value as an .fk literal.

    Supported: int, float, bool, str, list of supported, dict, and any model /
    object normalizable to a field dict — the structure-access marshalling. A
    dict OR a model (via ``model_dump()`` / ``__dict__``) becomes the
    first-order value ``(list "__dict__" "k" v ...)`` read through ``_get``;
    a list recurses element-wise, so a ``list[dict|model]`` becomes a list of
    those dictionary values — the list-of-records shape a
    reduction recipe folds over. Normalizing model→dict at this boundary is what
    dissolves the object-OR-dict polymorphism. Strings get Lisp-style
    double-quote escaping. Anything with no
    scalar/list/field view raises TypeError — the kernel's value model is small
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
    if isinstance(value, dict):
        # The marker selects keyed `_get`; alternating key/value cells keep
        # transport semantics in Form data, with no record parser special-case
        # added to the C seed.
        if not value:
            return '(list "__dict__")'
        parts = []
        for k, v in value.items():
            if not isinstance(k, str):
                raise TypeError(
                    f"_fk_literal: record field name must be a string, got "
                    f"{type(k).__name__}"
                )
            escaped_key = k.replace("\\", "\\\\").replace('"', '\\"')
            parts.append(f'"{escaped_key}" {_fk_literal(v)}')
        return '(list "__dict__" ' + " ".join(parts) + ")"
    if isinstance(value, (list, tuple)):
        if not value:
            return "(list)"
        return "(list " + " ".join(_fk_literal(v) for v in value) + ")"
    # Last: a structured object (Pydantic model / dataclass / namespace) that
    # isn't already a dict. Normalize to its first-order dictionary value —
    # the model→dict step that dissolves the object-OR-dict polymorphism
    # at the boundary, so a list[model] marshals identically to a list[dict].
    field_dict = _as_field_dict(value)
    if field_dict is not None:
        return _fk_literal(field_dict)
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
    parse: Callable[[str], Any] = lambda s: s,
    timeout: float = 10.0,
) -> tuple[Any, str]:
    """Load a recipe, inject inputs, and run it on the Form kernel.

    The end-state ergonomic API for transmuting an endpoint. A handler
    builds a `bindings` dict from its parsed inputs, names the .fk file, and
    gets `(value, runtime)` back. The runtime string is the response-model
    field that lets clients see which kernel carrier actually served them.

    Example:

        weight, runtime = serve_via_kernel(
            "endpoint_coherence_weight_demo.fk",
            bindings={"values": parsed, "threshold": threshold},
            parse=int,
        )

    Missing or failing fkwu remains a hard failure so Python or a sibling
    walker never silently resumes ownership.
    """

    # The .fk recipe is a deploy-time-compiled artifact. Absence is now a hard
    # route-deploy failure, not a signal to execute the computation in Python.
    fk_source = load_recipe(recipe_path)
    if bindings:
        fk_source = inject_bindings(fk_source, bindings)
    return run_kernel(fk_source, parse=parse, timeout=timeout)
