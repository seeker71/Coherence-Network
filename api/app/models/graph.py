"""Universal Node + Edge data model.

Every entity in the Coherence Network is a node. Every relationship is an edge.
Type-specific fields live in `properties` (JSONB). The schema is:

    nodes: id, type, name, description, properties, phase, created_at, updated_at
    edges: id, from_id, to_id, type, properties, strength, created_by, created_at

Node types: idea, concept, contributor, spec, task, asset, news_item,
            federation_node, axis, frequency, message, measurement
            (plus canonical types from Spec 169: implementation, service, domain,
             pipeline-run, event, artifact)

Edge types: the 46 relationship types from Living Codex ontology,
            plus canonical 7 from Spec 169 (inspires, depends-on, implements,
            contradicts, extends, analogous-to, parent-of)
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy import JSON as _JSON

try:
    from sqlalchemy.dialects.postgresql import JSONB
except ImportError:
    JSONB = _JSON  # type: ignore[misc,assignment]

# Use JSONB on PostgreSQL (indexable), plain JSON on SQLite (tests)
import os as _os

_PortableJSON = JSONB if "postgresql" in _os.environ.get("DATABASE_URL", "") else _JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.services.unified_db import Base


class NodeType(str, Enum):
    """All entity types in the system (legacy + canonical)."""
    IDEA = "idea"
    CONCEPT = "concept"
    CONTRIBUTOR = "contributor"
    SPEC = "spec"
    TASK = "task"
    ASSET = "asset"
    NEWS_ITEM = "news_item"
    FEDERATION_NODE = "federation_node"
    AXIS = "axis"
    FREQUENCY = "frequency"
    MESSAGE = "message"
    MEASUREMENT = "measurement"
    # Spec 169 canonical additions
    IMPLEMENTATION = "implementation"
    SERVICE = "service"
    DOMAIN = "domain"
    PIPELINE_RUN = "pipeline-run"
    EVENT = "event"
    ARTIFACT = "artifact"


# Spec 169: canonical closed vocabulary for the semantic layer
class CanonicalNodeType(str, Enum):
    """10 canonical node types from Spec 169 — the typed semantic layer."""
    IDEA = "idea"
    CONCEPT = "concept"
    SPEC = "spec"
    IMPLEMENTATION = "implementation"
    SERVICE = "service"
    CONTRIBUTOR = "contributor"
    DOMAIN = "domain"
    PIPELINE_RUN = "pipeline-run"
    EVENT = "event"
    ARTIFACT = "artifact"


class CanonicalEdgeType(str, Enum):
    """9 canonical edge types from Spec 169 — minimal closed vocabulary."""
    INSPIRES = "inspires"
    DEPENDS_ON = "depends-on"
    IMPLEMENTS = "implements"
    CONTRADICTS = "contradicts"
    EXTENDS = "extends"
    ANALOGOUS_TO = "analogous-to"
    PARENT_OF = "parent-of"
    MANAGES = "manages"
    DELEGATES_TO = "delegates-to"


class LifecycleState(str, Enum):
    """Ice/Water/Gas lifecycle state for nodes (Spec 169)."""
    GAS = "gas"      # Ideation phase — unformed, pre-specification
    ICE = "ice"      # Specification phase — frozen potential, not yet implemented
    WATER = "water"  # Active phase — being implemented, run, or used


class NodePhase(str, Enum):
    """Ice/Water/Gas lifecycle state (legacy alias — use LifecycleState for new code)."""
    ICE = "ice"          # stable, archived, reference
    WATER = "water"      # active, flowing, changing
    GAS = "gas"          # speculative, volatile, experimental


# Lifecycle defaults per canonical node type (Spec 169 §Lifecycle States)
LIFECYCLE_DEFAULTS: dict[str, str] = {
    "idea": "gas",
    "concept": "gas",
    "spec": "ice",
    "implementation": "water",
    "service": "water",
    "contributor": "water",
    "domain": "ice",
    "pipeline-run": "water",
    "event": "water",
    "artifact": "water",
}

# Symmetric canonical edge types (Spec 169)
SYMMETRIC_EDGE_TYPES: frozenset[str] = frozenset({"contradicts", "analogous-to"})

# Canonical edge type set for O(1) lookup
CANONICAL_EDGE_TYPE_SET: frozenset[str] = frozenset(e.value for e in CanonicalEdgeType)

# Supported node type set for graph CRUD compatibility
NODE_TYPE_SET: frozenset[str] = frozenset(n.value for n in NodeType)

# Canonical node type set for O(1) lookup
CANONICAL_NODE_TYPE_SET: frozenset[str] = frozenset(n.value for n in CanonicalNodeType)


# ── Pydantic response models for registry endpoints ──────────────────────────


class NodeTypeEntry(BaseModel):
    """One entry in the node-type registry (GET /api/graph/node-types)."""
    type: str
    description: str
    lifecycle_default: str
    payload_schema: dict[str, Any]
    example_id: str


class EdgeTypeEntry(BaseModel):
    """One entry in the edge-type registry (GET /api/graph/edge-types)."""
    type: str
    description: str
    symmetric: bool
    direction_label: str
    example: str


class NodeTypeRegistry(BaseModel):
    node_types: list[NodeTypeEntry]


class EdgeTypeRegistry(BaseModel):
    edge_types: list[EdgeTypeEntry]


class GraphProof(BaseModel):
    """Aggregate proof that the graph is functioning as the fractal data layer."""
    total_nodes: int
    total_edges: int
    nodes_by_type: dict[str, int]
    edges_by_type: dict[str, int]
    lifecycle_distribution: dict[str, int]
    graph_density: float
    average_degree: float
    last_edge_created_at: str | None
    coverage_pct: dict[str, float]


class Node(Base):
    """Universal node — every entity in the system.

    Type-specific fields go in `properties` (JSONB).
    Common fields (name, description, phase) are first-class columns
    for fast filtering and indexing.
    """
    __tablename__ = "graph_nodes"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    properties: Mapped[dict] = mapped_column(_PortableJSON, nullable=False, default=dict)
    phase: Mapped[str] = mapped_column(
        String(20), nullable=False, default="water",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_graph_nodes_type", "type"),
        Index("ix_graph_nodes_type_phase", "type", "phase"),
        Index("ix_graph_nodes_properties", "properties", postgresql_using="gin"),
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict, merging properties into top level for API compat."""
        d = {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "description": self.description,
            "phase": self.phase,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        # Merge properties for API compatibility
        if self.properties:
            d.update(self.properties)
        return d


class Edge(Base):
    """Universal edge — every relationship between nodes.

    Edge types come from the Living Codex ontology (46 types)
    plus operational types for the CC network.
    """
    __tablename__ = "graph_edges"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    from_id: Mapped[str] = mapped_column(String(255), nullable=False)
    to_id: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    properties: Mapped[dict] = mapped_column(_PortableJSON, nullable=False, default=dict)
    strength: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index("ix_graph_edges_from", "from_id"),
        Index("ix_graph_edges_to", "to_id"),
        Index("ix_graph_edges_type", "type"),
        Index("ix_graph_edges_from_type", "from_id", "type"),
        Index("ix_graph_edges_to_type", "to_id", "type"),
        Index("ix_graph_edges_pair", "from_id", "to_id", "type", unique=True),
    )

    def to_dict(self) -> dict[str, Any]:
        d = {
            "id": self.id,
            "from_id": self.from_id,
            "to_id": self.to_id,
            "type": self.type,
            "strength": self.strength,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if self.properties:
            d.update({"properties": self.properties})
        return d
