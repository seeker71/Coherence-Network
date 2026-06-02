"""Utility endpoints whose bodies live as Form recipes, not Python functions.

Transmutation as a habit toward the question Urs named: "can we replace
FastAPI with native Form kernel?" Each endpoint here carries the same
shape across three runtimes — CPython, TS evalPython, form-kernel-rust
— and at request-time prefers the native kernel.

FastAPI stays as the HTTP doorway. The body of the endpoint IS a
Recipe: same input → same output across runtimes, guarded by
form/form-kernel-ts/seedbank/python-adapter/scripts/parity_suite.sh.

The repeating gesture (every endpoint here uses it):
  1. Land a `.py` demo + compiled `.fk` under seedbank/python-adapter/examples/
  2. Add the demo path to PARITY_FILES in parity_suite.sh
  3. Call `serve_via_kernel(<fk>, bindings={...}, fallback=lambda: ...)`

The endpoint families now live in focused ``kernel_*`` modules so no single
module grows unbounded; they all decorate the one shared ``/utils`` router
defined in ``app.routers.kernel_shared``. Importing the family modules below
runs their ``@router.get`` decorators, registering every route on that shared
router. ``app.main`` includes ``utils.router`` once with prefix ``/api`` —
so every path stays exactly ``/api/utils/...``.
"""
from __future__ import annotations

from app.routers.kernel_shared import (
    active_runtime,
    inline_available,
    kernel_available,
    kernel_bin_path,
    logger,
    router,
)

# Importing the family modules registers their routes on the shared router.
from app.routers import (  # noqa: F401  (imported for decorator side effects)
    kernel_breath,
    kernel_grounded_cv,
    kernel_grounding,
    kernel_matching,
    kernel_nodeid,
    kernel_scoring,
)

# Re-export the Python fallbacks the route tests import from this module. The
# canonical definitions now live in the family modules; these aliases keep the
# historical ``from app.routers.utils import <name>_py`` import path stable.
from app.routers.kernel_nodeid import (  # noqa: F401
    coherence_weight_py,
    nodeid_compatibility_py,
    nodeid_distance_py,
)
from app.routers.kernel_scoring import (  # noqa: F401
    _marginal_from_idea_py,
    weighted_average_py,
)
from app.routers.kernel_grounding import (  # noqa: F401
    _grounded_cost_sum_py,
    _grounding_summary_py,
)
from app.routers.kernel_grounded_cv import (  # noqa: F401
    _grounded_cost_py,
    _grounded_value_py,
)


@router.get(
    "/kernel_status",
    summary="Visibility into which Form-kernel surface is serving this container",
    description=(
        "Reports the kernel paths available in this container. "
        "``active`` names the path the next transmuted endpoint will take: "
        "``inline`` (PyO3 extension), ``subprocess`` (form-kernel-rust "
        "binary), or ``python-fallback`` (no kernel reachable). "
        "``binary_available`` and ``inline_available`` are the underlying "
        "flags; they let an operator see whether a deploy lost one path "
        "while keeping another."
    ),
)
async def kernel_status() -> dict[str, object]:
    bin_ok = kernel_available()
    return {
        "active": active_runtime(),
        "inline_available": inline_available(),
        "binary_available": bin_ok,
        # ``available`` is the original (binary-only) flag — kept as an
        # alias so callers from before the inline path don't break.
        "available": bin_ok,
        "binary_path": str(kernel_bin_path()),
    }
