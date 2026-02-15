"""Unified system inventory routes."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.models.idea import RoiEstimatorWeightsUpdate, RoiMeasurementCreate
from app.services import inventory_service
from app.services import page_lineage_service
from app.services import route_registry_service

router = APIRouter()


@router.get(
    "/inventory/system-lineage",
    summary="Get unified system inventory with runtime telemetry",
    description="""
**Purpose**: Unified machine-readable inventory of all core planning/execution artifacts (ideas, questions, specs, implementation usage) with real-time runtime telemetry for continuous cost/value measurement.

**Spec**: [049-system-lineage-inventory-and-runtime-telemetry.md](https://github.com/seeker71/Coherence-Network/blob/main/specs/049-system-lineage-inventory-and-runtime-telemetry.md)
**Idea**: `coherence-network-api-runtime` - API and runtime telemetry for inventory and validation
**Tests**: `api/tests/test_inventory_api.py::test_system_lineage_inventory_includes_core_sections`

**Inventory Sections**:
- **ideas**: Portfolio summary, unvalidated vs validated ideas
- **manifestations**: Implementation progress tracking
- **questions**: Open vs answered question inventory
- **question_ontology**: Question lineage and evolution
- **specs**: Discovered specs from `specs/` directory
- **implementation_usage**: Value-lineage links and usage events
- **assets**: System asset registry by type with coverage
- **contributors**: Contribution tracking by perspective
- **roi_insights**: ROI rankings and estimated returns
- **next_roi_work**: Highest ROI task recommendations
- **operating_console**: Estimated ROI queue
- **evidence_contract**: Evidence freshness tracking
- **tracking_mechanism**: Idea/spec/implementation mapping efficiency
- **availability_gaps**: API/web parity gaps
- **runtime**: Runtime telemetry summaries by idea

**Use Case**: Machines can query complete system state to understand priorities, track progress, identify gaps, and make autonomous decisions about what to work on next.

**Change Process**:
1. **Idea**: Update `/api/logs/idea_portfolio.json` (coherence-network-api-runtime idea)
2. **Spec**: Update `/specs/049-system-lineage-inventory-and-runtime-telemetry.md`
3. **Tests**: Update `/api/tests/test_inventory_api.py` (modify inventory tests)
4. **Implementation**: Update `/api/services/inventory_service.py` and `/api/app/routers/inventory.py`
5. **Validation**: Run `pytest api/tests/test_inventory_api.py -v`
    """,
    responses={
        200: {
            "description": "Complete system inventory with runtime telemetry",
            "content": {
                "application/json": {
                    "example": {
                        "ideas": {"summary": {"total_ideas": 15, "unvalidated_ideas": 10, "validated_ideas": 5}},
                        "manifestations": {"total": 12, "by_status": {"partial": 8, "validated": 4}},
                        "questions": {"total": 45, "unanswered": 32, "answered": 13},
                        "specs": {"count": 70, "coverage_pct": 92.3},
                        "implementation_usage": {"lineage_links_count": 28, "usage_events_count": 156},
                        "assets": {"total": 234, "by_type": {"spec": 70, "implementation": 89, "test": 75}},
                        "runtime": {"window_seconds": 3600, "total_events": 1520, "by_idea": {"portfolio-governance": {"event_count": 245}}}
                    }
                }
            }
        }
    },
    openapi_extra={
        "x-spec-file": "specs/049-system-lineage-inventory-and-runtime-telemetry.md",
        "x-idea-id": "coherence-network-api-runtime",
        "x-test-file": "api/tests/test_inventory_api.py",
        "x-implementation-file": "api/app/services/inventory_service.py"
    }
)
async def system_lineage_inventory(
    runtime_window_seconds: int = Query(3600, ge=60, le=2592000),
) -> dict:
    return inventory_service.build_system_lineage_inventory(runtime_window_seconds=runtime_window_seconds)


@router.get(
    "/inventory/routes/canonical",
    summary="Get canonical route registry with idea linkage",
    description="""
**Purpose**: Expose canonical API/web route set with milestone metadata and idea linkage for machine/human tooling and runtime attribution.

**Spec**: [050-canonical-route-registry-and-runtime-mapping.md](https://github.com/seeker71/Coherence-Network/blob/main/specs/050-canonical-route-registry-and-runtime-mapping.md)
**Idea**: `coherence-network-api-runtime` - API and runtime telemetry for inventory and validation
**Tests**: `api/tests/test_inventory_api.py::test_canonical_routes_inventory_endpoint_returns_registry`

**Registry Contents**:
- API endpoint definitions with methods, paths, idea linkage
- Web route definitions with page paths, component locations
- Milestone metadata for work tracking
- Runtime mapping defaults to avoid unmapped telemetry

**Use Case**: Machines can discover all available routes, understand their purpose via idea linkage, and ensure runtime telemetry maps correctly for attribution.

**Change Process**:
1. **Idea**: Update `/api/logs/idea_portfolio.json` (coherence-network-api-runtime idea)
2. **Spec**: Update `/specs/050-canonical-route-registry-and-runtime-mapping.md`
3. **Config**: Update `/config/canonical_routes.json` (route definitions)
4. **Tests**: Update `/api/tests/test_inventory_api.py` (modify registry tests)
5. **Implementation**: Update `/api/services/route_registry_service.py` and `/api/app/routers/inventory.py`
6. **Validation**: Run `pytest api/tests/test_inventory_api.py -v`
    """,
    responses={
        200: {
            "description": "Canonical route registry",
            "content": {
                "application/json": {
                    "example": {
                        "api_routes": [
                            {
                                "path": "/api/ideas",
                                "method": "GET",
                                "idea_id": "portfolio-governance",
                                "milestone": "m1-core-intelligence"
                            }
                        ],
                        "web_routes": [
                            {
                                "path": "/portfolio",
                                "component": "app/portfolio/page.tsx",
                                "idea_id": "portfolio-governance",
                                "milestone": "m1-core-intelligence"
                            }
                        ],
                        "coverage": {"api_mapped": 45, "web_mapped": 12, "unmapped": 0}
                    }
                }
            }
        }
    },
    openapi_extra={
        "x-spec-file": "specs/050-canonical-route-registry-and-runtime-mapping.md",
        "x-idea-id": "coherence-network-api-runtime",
        "x-test-file": "api/tests/test_inventory_api.py",
        "x-implementation-file": "api/app/services/route_registry_service.py",
        "x-config-file": "config/canonical_routes.json"
    }
)
async def canonical_routes() -> dict:
    return route_registry_service.get_canonical_routes()


@router.get(
    "/inventory/page-lineage",
    summary="Get page-idea ontology and traceability links",
    description="""
**Purpose**: Ensure every human UI page is explicitly traceable to originating idea, root idea, API contract, governing spec, process/pseudocode, and source files.

**Spec**: [066-page-idea-ontology-and-traceability-links.md](https://github.com/seeker71/Coherence-Network/blob/main/specs/066-page-idea-ontology-and-traceability-links.md)
**Idea**: `coherence-network-api-runtime` - API and runtime telemetry for inventory and validation
**Tests**: `api/tests/test_inventory_api.py::test_page_lineage_endpoint_covers_web_pages_and_returns_entry`

**Page Lineage Fields**:
- page_path: UI route path (e.g., "/portfolio")
- idea_id: Originating idea for the page
- root_idea: Root system idea
- api_contract: Related API endpoint(s)
- spec_id: Governing specification
- source_files: Component file locations
- endpoint_examples: Usage examples with curl commands

**Query Options**:
- No params: Returns all page lineage entries with coverage summary
- page_path="<path>": Returns specific page lineage details

**Use Case**: Machines can understand WHY each UI page exists, WHAT idea it serves, and HOW to modify it by following the traceability chain to spec/API/implementation.

**Change Process**:
1. **Idea**: Update `/api/logs/idea_portfolio.json` (coherence-network-api-runtime idea)
2. **Spec**: Update `/specs/066-page-idea-ontology-and-traceability-links.md`
3. **Config**: Update `/api/config/page_lineage.json` (page definitions)
4. **Tests**: Update `/api/tests/test_inventory_api.py` (modify page lineage tests)
5. **Implementation**: Update `/api/services/page_lineage_service.py` and `/api/app/routers/inventory.py`
6. **Validation**: Run `pytest api/tests/test_inventory_api.py -v`
    """,
    responses={
        200: {
            "description": "Page lineage registry with coverage",
            "content": {
                "application/json": {
                    "example": {
                        "pages": [
                            {
                                "page_path": "/portfolio",
                                "idea_id": "portfolio-governance",
                                "root_idea": "coherence-network-value-attribution",
                                "api_contract": ["/api/ideas"],
                                "spec_id": "053-ideas-prioritization",
                                "source_files": ["app/portfolio/page.tsx"],
                                "endpoint_examples": ["curl http://localhost:8000/api/ideas"]
                            }
                        ],
                        "coverage": {"total_pages": 12, "mapped_pages": 12, "missing_mappings": 0}
                    }
                }
            }
        }
    },
    openapi_extra={
        "x-spec-file": "specs/066-page-idea-ontology-and-traceability-links.md",
        "x-idea-id": "coherence-network-api-runtime",
        "x-test-file": "api/tests/test_inventory_api.py",
        "x-implementation-file": "api/app/services/page_lineage_service.py",
        "x-config-file": "api/config/page_lineage.json"
    }
)
async def page_lineage(page_path: str | None = Query(default=None)) -> dict:
    return page_lineage_service.get_page_lineage(page_path=page_path)


@router.post("/inventory/questions/next-highest-roi-task")
async def next_highest_roi_task(create_task: bool = Query(False)) -> dict:
    return inventory_service.next_highest_roi_task_from_answered_questions(create_task=create_task)


@router.post("/inventory/roi/next-task")
async def next_highest_estimated_roi_task(create_task: bool = Query(False)) -> dict:
    return inventory_service.next_highest_estimated_roi_task(create_task=create_task)


@router.post("/inventory/issues/scan")
async def scan_inventory_issues(create_tasks: bool = Query(False)) -> dict:
    return inventory_service.scan_inventory_issues(create_tasks=create_tasks)


@router.post("/inventory/availability/scan")
async def scan_api_web_availability_gaps(create_tasks: bool = Query(False)) -> dict:
    return inventory_service.scan_api_web_availability_gaps(create_tasks=create_tasks)


@router.get("/inventory/assets")
async def list_assets_inventory(
    asset_type: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=5000),
) -> dict:
    return inventory_service.list_assets_inventory(asset_type=asset_type, limit=limit)


@router.post("/inventory/evidence/scan")
async def scan_evidence_contract(create_tasks: bool = Query(False)) -> dict:
    return inventory_service.scan_evidence_contract(create_tasks=create_tasks)


@router.post("/inventory/questions/auto-answer")
async def auto_answer_high_roi_questions(
    limit: int = Query(3, ge=1, le=25),
    create_derived_ideas: bool = Query(False),
) -> dict:
    return inventory_service.auto_answer_high_roi_questions(
        limit=limit,
        create_derived_ideas=create_derived_ideas,
    )


@router.get("/inventory/roi/estimator")
async def get_roi_estimator(
    runtime_window_seconds: int = Query(86400, ge=60, le=2592000),
) -> dict:
    return inventory_service.get_roi_estimator(runtime_window_seconds=runtime_window_seconds)


@router.post("/inventory/roi/estimator/measurements")
async def create_roi_measurement(data: RoiMeasurementCreate) -> dict:
    return inventory_service.record_roi_measurement(
        subject_type=data.subject_type,
        subject_id=data.subject_id,
        idea_id=data.idea_id,
        estimated_roi=data.estimated_roi,
        actual_roi=data.actual_roi,
        actual_value=data.actual_value,
        actual_cost=data.actual_cost,
        measured_delta=data.measured_delta,
        estimated_cost=data.estimated_cost,
        source=data.source,
        measured_by=data.measured_by,
        evidence_refs=data.evidence_refs,
        notes=data.notes,
    )


@router.post("/inventory/roi/estimator/calibrate")
async def calibrate_roi_estimator(
    apply: bool = Query(True),
    min_samples: int = Query(3, ge=1, le=200),
    calibrated_by: str | None = Query(default=None),
) -> dict:
    return inventory_service.calibrate_roi_estimator(
        apply=apply,
        min_samples=min_samples,
        calibrated_by=calibrated_by,
    )


@router.patch("/inventory/roi/estimator/weights")
async def patch_roi_estimator_weights(data: RoiEstimatorWeightsUpdate) -> dict:
    return inventory_service.update_roi_estimator_weights(
        idea_multiplier=data.idea_multiplier,
        question_multiplier=data.question_multiplier,
        answer_multiplier=data.answer_multiplier,
        updated_by=data.updated_by,
    )
