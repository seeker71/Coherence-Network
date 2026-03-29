# spec: 183-full-traceability-chain
# idea: full-traceability-chain
"""Pydantic models for the full traceability chain API (Spec 183)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TraceabilitySummary(BaseModel):
    spec_files_total: int = 0
    spec_files_with_idea_id: int = 0
    spec_files_coverage_pct: float = 0.0
    db_specs_total: int = 0
    db_specs_with_idea_id: int = 0
    db_specs_coverage_pct: float = 0.0
    source_files_total: int = 0
    source_files_with_spec_ref: int = 0
    source_files_coverage_pct: float = 0.0
    functions_traced: int = 0
    functions_total: int = 0
    function_coverage_pct: float = 0.0
    overall_traceability_pct: float = 0.0


class TraceabilityGap(BaseModel):
    type: str  # "spec_no_idea" | "file_no_spec" | "function_not_traced"
    spec_file: str | None = None
    spec_id: str | None = None
    file_path: str | None = None
    severity: str = "medium"  # "high" | "medium" | "low"
    message: str | None = None


class TraceabilityReport(BaseModel):
    summary: TraceabilitySummary
    gaps: list[TraceabilityGap] = Field(default_factory=list)
    links: list[dict[str, Any]] = Field(default_factory=list)


class TracedFunction(BaseModel):
    module: str
    function: str
    spec_id: str | None = None
    idea_id: str | None = None
    file: str | None = None
    line: int | None = None
    description: str | None = None


class FunctionCoverage(BaseModel):
    traced: int = 0
    total_public: int = 0
    pct: float = 0.0


class FunctionListResponse(BaseModel):
    functions: list[TracedFunction] = Field(default_factory=list)
    coverage: FunctionCoverage = Field(default_factory=FunctionCoverage)


class BackfillRequest(BaseModel):
    dry_run: bool = True


class BackfillResponse(BaseModel):
    job_id: str
    status: str
    dry_run: bool
    queued_at: datetime


class LineageFile(BaseModel):
    path: str
    functions: list[str] = Field(default_factory=list)


class LineageSpec(BaseModel):
    spec_id: str
    spec_title: str | None = None
    files: list[LineageFile] = Field(default_factory=list)


class LineageResponse(BaseModel):
    idea_id: str
    idea_title: str | None = None
    specs: list[LineageSpec] = Field(default_factory=list)


class SpecForwardTrace(BaseModel):
    spec_id: str
    spec_title: str | None = None
    idea_id: str | None = None
    files: list[str] = Field(default_factory=list)
    functions: list[dict[str, Any]] = Field(default_factory=list)
    prs: list[str] = Field(default_factory=list)
