"""Transmuted /api/utils NodeID + coherence-weight endpoints (bodies run as Form recipes).

Bodies live as Form recipes; the route prefers the native kernel via
``serve_via_kernel`` and falls back to the value-identical Python ``_py``
function. Routes decorate the shared ``/utils`` router from
``app.routers.kernel_shared`` so every path stays ``/api/utils/...``.
"""
from __future__ import annotations

from app.routers.kernel_shared import (
    Annotated,
    BaseModel,
    ConfigDict,
    Field,
    HTTPException,
    Query,
    _parse_values,
    router,
    serve_via_kernel,
)

# ---------------------------------------------------------------------------
# Endpoint: /api/utils/coherence_weight
#
# Pure computation: given a list of integer values and a threshold,
# compute a weighted coherence score. Above-threshold values contribute
# with position-based decay (100×, 50×, 25×, then 10×) and add a 100×
# bonus per above-threshold count.
#
# This Python function is the *fallback*; the *primary* runtime is the
# Form recipe compiled from
# form/form-kernel-ts/seedbank/python-adapter/examples/
# endpoint_coherence_weight_demo.py. The parity_suite guarantees they
# return the same integer for the same inputs.
# ---------------------------------------------------------------------------


def _weighted_score_py(value: int, position: int) -> int:
    if position == 0:
        return value * 100
    if position == 1:
        return value * 50
    if position == 2:
        return value * 25
    return value * 10


def _coherence_score_py(values: list[int], threshold: int) -> int:
    total = 0
    position = 0
    for v in values:
        if v >= threshold:
            total = total + _weighted_score_py(v, position)
            position = position + 1
    return total


def _count_above_py(values: list[int], threshold: int) -> int:
    return sum(1 for v in values if v >= threshold)


def coherence_weight_py(values: list[int], threshold: int) -> int:
    """Python fallback — semantically identical to the Form recipe."""
    above = _count_above_py(values, threshold)
    coherence = _coherence_score_py(values, threshold)
    return above * 100 + coherence


class CoherenceWeightResponse(BaseModel):
    """GET /api/utils/coherence_weight response."""

    model_config = ConfigDict(extra="forbid")
    weight: Annotated[int, Field(description="Computed weighted coherence score")]
    values: Annotated[list[int], Field(description="Input values, echoed back")]
    threshold: Annotated[int, Field(description="Input threshold, echoed back")]
    runtime: Annotated[
        str,
        Field(description="Which runtime computed the answer — 'inline', 'subprocess', or 'python-fallback'"),
    ]


@router.get(
    "/coherence_weight",
    response_model=CoherenceWeightResponse,
    summary="Compute weighted coherence score (body runs as Form recipe)",
    description=(
        "First transmutation gesture: the body of this endpoint is a Form "
        "recipe compiled from "
        "form/form-kernel-ts/seedbank/python-adapter/examples/"
        "endpoint_coherence_weight_demo.py. When form-kernel-rust is "
        "available the request shells into the native binary; otherwise "
        "the semantically-identical Python fallback runs. Three-way "
        "parity (CPython, TS, Rust) is the regression gate."
    ),
)
async def coherence_weight(
    values: Annotated[
        str,
        Query(description="Comma-separated integers — e.g. '72,38,91,55,28'"),
    ] = "72,38,91,55,28,67,84,45,95,12",
    threshold: Annotated[int, Query(description="Cutoff — only values >= this contribute")] = 50,
) -> CoherenceWeightResponse:
    parsed = _parse_values(values)
    weight, runtime = serve_via_kernel(
        "endpoint_coherence_weight_demo.fk",
        bindings={"values": parsed, "threshold": threshold},
        fallback=lambda: coherence_weight_py(parsed, threshold),
        parse=int,
    )
    return CoherenceWeightResponse(
        weight=weight,
        values=parsed,
        threshold=threshold,
        runtime=runtime,
    )


# ---------------------------------------------------------------------------
# Endpoint: /api/utils/nodeid_distance
#
# Pure computation: Manhattan distance between two NodeIDs in the lattice.
# The substrate locates every cell at NodeID(package, level, type, instance);
# distance over those four coordinates is the cheapest structural-proximity
# signal — useful for "what's near this cell?" without a graph traversal.
# ---------------------------------------------------------------------------


def nodeid_distance_py(
    a_pkg: int, a_lvl: int, a_type: int, a_inst: int,
    b_pkg: int, b_lvl: int, b_type: int, b_inst: int,
) -> int:
    """Python fallback — semantically identical to the Form recipe."""
    return (
        abs(a_pkg - b_pkg)
        + abs(a_lvl - b_lvl)
        + abs(a_type - b_type)
        + abs(a_inst - b_inst)
    )


class NodeIdDistanceResponse(BaseModel):
    """GET /api/utils/nodeid_distance response."""

    model_config = ConfigDict(extra="forbid")
    distance: Annotated[int, Field(description="Manhattan distance between the two NodeIDs")]
    a: Annotated[list[int], Field(description="NodeID a as [package, level, type, instance]")]
    b: Annotated[list[int], Field(description="NodeID b as [package, level, type, instance]")]
    runtime: Annotated[
        str,
        Field(description="Which runtime computed the answer — 'inline', 'subprocess', or 'python-fallback'"),
    ]


@router.get(
    "/nodeid_distance",
    response_model=NodeIdDistanceResponse,
    summary="Manhattan distance between two substrate NodeIDs (body runs as Form recipe)",
    description=(
        "Pure-computation endpoint, body transmuted to a Form recipe. "
        "Returns sum of absolute differences across the four NodeID "
        "coordinates (package, level, type, instance). Same shape as "
        "coherence_weight — kernel-or-fallback served by serve_via_kernel."
    ),
)
async def nodeid_distance(
    a_pkg: Annotated[int, Query(description="NodeID a — package")] = 1,
    a_lvl: Annotated[int, Query(description="NodeID a — level")] = 5,
    a_type: Annotated[int, Query(description="NodeID a — type_")] = 4,
    a_inst: Annotated[int, Query(description="NodeID a — instance")] = 1,
    b_pkg: Annotated[int, Query(description="NodeID b — package")] = 1,
    b_lvl: Annotated[int, Query(description="NodeID b — level")] = 4,
    b_type: Annotated[int, Query(description="NodeID b — type_")] = 4,
    b_inst: Annotated[int, Query(description="NodeID b — instance")] = 7,
) -> NodeIdDistanceResponse:
    distance, runtime = serve_via_kernel(
        "endpoint_nodeid_distance_demo.fk",
        bindings={
            "a_pkg": a_pkg, "a_lvl": a_lvl, "a_type": a_type, "a_inst": a_inst,
            "b_pkg": b_pkg, "b_lvl": b_lvl, "b_type": b_type, "b_inst": b_inst,
        },
        fallback=lambda: nodeid_distance_py(
            a_pkg, a_lvl, a_type, a_inst, b_pkg, b_lvl, b_type, b_inst,
        ),
        parse=int,
    )
    return NodeIdDistanceResponse(
        distance=distance,
        a=[a_pkg, a_lvl, a_type, a_inst],
        b=[b_pkg, b_lvl, b_type, b_inst],
        runtime=runtime,
    )


# ---------------------------------------------------------------------------
# Endpoint: /api/utils/nodeid_compatibility
#
# Pure computation: graded structural compatibility between two NodeIDs, 0..4
# by how many of the four coordinates (package, level, type, instance) match.
# Sibling of nodeid_distance — that measures L1 distance, this measures
# coordinate agreement. It is the kernel of the substrate's view-through-
# blueprint compatibility check: two NodeIDs sharing more coordinates are more
# structurally interchangeable. Body transmuted to a Form recipe.
# ---------------------------------------------------------------------------


def nodeid_compatibility_py(
    a_pkg: int, a_lvl: int, a_type: int, a_inst: int,
    b_pkg: int, b_lvl: int, b_type: int, b_inst: int,
) -> int:
    """Python fallback — semantically identical to the Form recipe."""
    return (
        int(a_pkg == b_pkg)
        + int(a_lvl == b_lvl)
        + int(a_type == b_type)
        + int(a_inst == b_inst)
    )


class NodeIdCompatibilityResponse(BaseModel):
    """GET /api/utils/nodeid_compatibility response."""

    model_config = ConfigDict(extra="forbid")
    compatibility: Annotated[
        int, Field(description="Coordinate-agreement score 0..4 between the two NodeIDs")
    ]
    a: Annotated[list[int], Field(description="NodeID a as [package, level, type, instance]")]
    b: Annotated[list[int], Field(description="NodeID b as [package, level, type, instance]")]
    runtime: Annotated[
        str,
        Field(description="Which runtime computed the answer — 'inline', 'subprocess', or 'python-fallback'"),
    ]


@router.get(
    "/nodeid_compatibility",
    response_model=NodeIdCompatibilityResponse,
    summary="Structural compatibility (0..4 coordinate agreement) between two NodeIDs (body runs as Form recipe)",
    description=(
        "Pure-computation endpoint, body transmuted to a Form recipe. "
        "Returns how many of the four NodeID coordinates (package, level, "
        "type, instance) two cells share — the cheapest structural-"
        "interchangeability signal. Kernel-or-fallback via serve_via_kernel; "
        "three-way parity (CPython, TS, Rust) is the gate."
    ),
)
async def nodeid_compatibility(
    a_pkg: Annotated[int, Query(description="NodeID a — package")] = 1,
    a_lvl: Annotated[int, Query(description="NodeID a — level")] = 5,
    a_type: Annotated[int, Query(description="NodeID a — type_")] = 4,
    a_inst: Annotated[int, Query(description="NodeID a — instance")] = 1,
    b_pkg: Annotated[int, Query(description="NodeID b — package")] = 1,
    b_lvl: Annotated[int, Query(description="NodeID b — level")] = 4,
    b_type: Annotated[int, Query(description="NodeID b — type_")] = 4,
    b_inst: Annotated[int, Query(description="NodeID b — instance")] = 7,
) -> NodeIdCompatibilityResponse:
    compatibility, runtime = serve_via_kernel(
        "endpoint_nodeid_compatibility_demo.fk",
        bindings={
            "a_pkg": a_pkg, "a_lvl": a_lvl, "a_type": a_type, "a_inst": a_inst,
            "b_pkg": b_pkg, "b_lvl": b_lvl, "b_type": b_type, "b_inst": b_inst,
        },
        fallback=lambda: nodeid_compatibility_py(
            a_pkg, a_lvl, a_type, a_inst, b_pkg, b_lvl, b_type, b_inst,
        ),
        parse=int,
    )
    return NodeIdCompatibilityResponse(
        compatibility=compatibility,
        a=[a_pkg, a_lvl, a_type, a_inst],
        b=[b_pkg, b_lvl, b_type, b_inst],
        runtime=runtime,
    )
