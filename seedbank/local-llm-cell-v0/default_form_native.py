"""default_form_native.py — register Form-native implementations as the
runtime default for organ.py's host-intrinsic call sites.

Imported by organ.py at module load time. Registers form_native.cosine,
form_native.sigmoid, and form_native.strategy_score under the recipe
names that organ.py's @substrate_dispatch decorators bind. After this
module runs, every call to organ._cosine / _sigmoid / _strategy_score
routes through the Form-native implementation instead of the wrapped
Python body.

Parity has been verified end-to-end (see parity_check.py): 2400 test
inputs across 12 recipes, exact to 1e-9 on pure compositions, within
1e-6 on iterative approximations (Newton sqrt, Taylor exp, derived
tanh/sigmoid). The Form-native path produces the same numbers as the
Python intrinsics.

The Python intrinsics remain as the wrapped function bodies — if a
caller ever needs to fall back (or if a future implementation
registers under the same name), the path is reversible:

    from substrate_dispatch import unregister_recipe
    unregister_recipe("cosine")    # back to organ._cosine body

The registration is the default; the override is per-call discipline.
"""

from __future__ import annotations

import form_native
from substrate_dispatch import register_recipe


# Map recipe name → Form-native implementation. The names match the
# @substrate_dispatch("...") decorators in organ.py.
_FORM_NATIVE_BINDINGS = {
    "cosine":         form_native.cosine,
    "sigmoid":        form_native.sigmoid,
    "strategy_score": form_native.strategy_score,
}


def register_form_native_defaults() -> list[str]:
    """Register every form_native implementation as the runtime default.
    Returns the list of registered names. Idempotent — calling twice
    re-registers the same callables (no duplication).
    """
    for name, fn in _FORM_NATIVE_BINDINGS.items():
        register_recipe(name, fn)
    return sorted(_FORM_NATIVE_BINDINGS.keys())


# Auto-register on import. This is the line that flips Form-native to
# default. Comment it out to use the Python intrinsics as before;
# uncomment to route through Form.
_REGISTERED = register_form_native_defaults()
