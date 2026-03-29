"""Pydantic response models for fractal zoom navigation (Spec 182).

Every node at every depth has the same structure:
  id, name, node_type, coherence_score, lifecycle_state, view_hint,
  open_questions, children, edges
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class OpenQuestion(BaseModel):
    id: str
    question: str
    created_at: str
    resolved: bool
    resolved_at: str | None = None


class ZoomEdge(BaseModel):
    from_: str = Field(alias="from")
    to: str
    edge_type: str

    model_config = {"populate_by_name": True}


class ZoomNode(BaseModel):
    """A node in the fractal zoom response — same shape at every depth."""
    id: str
    name: str
    node_type: str
    coherence_score: float
    lifecycle_state: str
    view_hint: str  # "garden" or "graph"
    open_questions: list[OpenQuestion] = Field(default_factory=list)
    children: list["ZoomNode"] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)


ZoomNode.model_rebuild()


class ZoomResponse(BaseModel):
    node: ZoomNode
    depth_requested: int
    total_nodes_in_subtree: int


class PillarNode(BaseModel):
    id: str
    name: str
    node_type: str
    coherence_score: float
    child_count: int
    open_question_count: int
    lifecycle_state: str


class PillarListResponse(BaseModel):
    pillars: list[PillarNode]
    total: int


class AddQuestionRequest(BaseModel):
    question: str


class QuestionResponse(BaseModel):
    id: str
    question: str
    created_at: str
    resolved: bool
    resolved_at: str | None = None
    node_id: str


class PatchQuestionRequest(BaseModel):
    resolved: bool
