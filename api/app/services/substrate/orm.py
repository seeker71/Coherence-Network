"""SQLAlchemy ORM models for the coherence-substrate.

Two tables form the kernel:

- substrate_nodes: the per-level interning store. Identity is content-addressed
  by (package, level, domain, serialized). The UNIQUE constraint on those
  four columns is the Make_SelfID atomicity gate — INSERT either succeeds with
  a fresh node_id or fails on conflict, at which point we read the existing
  row.

- substrate_named_cells: the registry of named instances. Each cell is
  (Recipe access, Base blueprint, Name, CTOR recipe).

Both tables work portably on SQLite and PostgreSQL (per CLAUDE.md schema
discipline). No JSONB, no SERIAL — everything is portable types.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from app.services.unified_db import Base


class SubstrateNodeORM(Base):
    """One interned shape (Blueprint or Recipe) in the lattice.

    The (package, level, domain, serialized) tuple uniquely identifies a
    structural shape. Two parses of the same shape collide on UNIQUE and
    re-use the existing node_id.
    """

    __tablename__ = "substrate_nodes"

    node_id = Column(Integer, primary_key=True, autoincrement=True)
    package = Column(Integer, nullable=False, default=1)
    level = Column(Integer, nullable=False, index=True)
    type_ = Column("type", Integer, nullable=False)
    instance = Column(Integer, nullable=False)
    serialized = Column(Text, nullable=False)
    domain = Column(String(16), nullable=False)  # 'blueprint' | 'recipe'
    count = Column(Integer, nullable=False, default=1)
    created_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint(
            "package", "level", "domain", "serialized",
            name="uq_substrate_serialized",
        ),
        Index("ix_substrate_lookup", "package", "level", "type", "instance"),
        Index("ix_substrate_count_desc", "count"),
    )


class SubstrateNamedCellORM(Base):
    """A named instance — Recipe access + Base blueprint + Name + CTOR recipe.

    Maps the cell pattern: every memory file, spec file, concept
    story, idea, presence, lineage edge, witness, or task in the body lives
    here as a cell.
    """

    __tablename__ = "substrate_named_cells"

    cell_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(512), nullable=False)
    domain = Column(String(32), nullable=False)  # 'memory' | 'spec' | 'concept' | ...
    base_node_id = Column(Integer, ForeignKey("substrate_nodes.node_id"), nullable=True)
    blueprint_node_id = Column(
        Integer, ForeignKey("substrate_nodes.node_id"), nullable=False
    )
    access_recipe_node_id = Column(
        Integer, ForeignKey("substrate_nodes.node_id"), nullable=True
    )
    ctor_recipe_node_id = Column(
        Integer, ForeignKey("substrate_nodes.node_id"), nullable=True
    )
    source_path = Column(String(1024), nullable=True)
    created_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint("domain", "name", name="uq_substrate_cell"),
        Index("ix_substrate_cell_blueprint", "blueprint_node_id"),
    )
