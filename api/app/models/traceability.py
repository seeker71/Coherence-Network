# spec: 181-full-code-traceability
# idea: full-traceability-chain
"""Pydantic models for the traceability system (Spec 181)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class LinkType(str, Enum):
    static_comment = "static_comment"
    decorator = "decorator"
    pr_reference = "pr_reference"
    manual = "manual"


class SpecLinkCreate(BaseModel):
    spec_id: str
    idea_id: str | None = None
    source_file: str
    function_name: str | None = None
    line_number: int | None = None
    link_type: LinkType = LinkType.static_comment
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    pr_number: int | None = None


class SpecLink(SpecLinkCreate):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class TraceabilityGap(BaseModel):
    type: str  # "spec_no_idea", "file_no_spec", "db_spec_no_idea"
    spec_file: str | None = None
    spec_id: str | None = None
    source_file: str | None = None
    severity: str  # "high", "medium", "low"


class TraceabilitySummary(BaseModel):
    spec_files_total: int
    spec_files_with_idea_id: int
    spec_files_coverage_pct: float
    db_specs_total: int
    db_specs_with_idea_id: int
    db_specs_coverage_pct: float
    source_files_total: int
    source_files_with_spec_ref: int
    source_files_coverage_pct: float
    functions_traced: int
    functions_total: int
    function_coverage_pct: float
    overall_traceability_pct: float


class TraceabilityReport(BaseModel):
    summary: TraceabilitySummary
    gaps: list[TraceabilityGap]
    links: list[dict[str, Any]]
    persisted_implementation_links: int = Field(
        default=0,
        description="Rows stored in traceability_implementation_links from last backfill scan.",
    )


class BackfillRequest(BaseModel):
    dry_run: bool = False


class BackfillResponse(BaseModel):
    job_id: str
    status: str
    dry_run: bool
    queued_at: datetime | None = None


class TracedFunction(BaseModel):
    module: str
    function: str
    spec_id: str | None
    idea_id: str | None
    file: str | None
    line: int | None
    description: str | None = None


class FunctionCoverage(BaseModel):
    traced: int
    total_public: int
    pct: float


class FunctionListResponse(BaseModel):
    functions: list[TracedFunction]
    coverage: FunctionCoverage


class LineageFile(BaseModel):
    path: str
    functions: list[str]


class LineageSpec(BaseModel):
    spec_id: str
    spec_title: str | None
    files: list[LineageFile]


class LineageResponse(BaseModel):
    idea_id: str
    idea_title: str | None
    specs: list[LineageSpec]
    inspiration: str | None = None


class SpecForwardTrace(BaseModel):
    spec_id: str
    spec_title: str | None
    idea_id: str | None
    files: list[str]
    functions: list[dict[str, Any]]
    prs: list[int]
