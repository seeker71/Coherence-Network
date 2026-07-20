"""Compatibility API module for utility routes implemented as Form recipes.

The endpoint families live in focused ``kernel_*`` modules and decorate the
one shared ``/utils`` router defined in ``app.routers.kernel_shared``.
Importing those modules registers every route on the shared router; this file
only gathers the route families and exposes kernel status for the bridge API.

The canonical computation bodies are Form recipes. Python helper functions
that still exist for parity checks live beside their owning route family,
not behind this module as a second import surface.
"""
from __future__ import annotations

from app.routers.kernel_shared import (
    active_runtime,
    kernel_available,
    kernel_bin_path,
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


@router.get(
    "/kernel_status",
    summary="Visibility into which Form-kernel surface is serving this container",
    description=(
        "Reports the c-bootstrapped fkwu execution carrier. ``active`` is "
        "``fkwu`` or ``unavailable``. Sibling-kernel availability is not an "
        "execution choice; those walkers exist only for differential proof."
    ),
)
async def kernel_status() -> dict[str, object]:
    bin_ok = kernel_available()
    return {
        "active": active_runtime(),
        "binary_available": bin_ok,
        "available": bin_ok,
        "binary_path": str(kernel_bin_path()),
    }
