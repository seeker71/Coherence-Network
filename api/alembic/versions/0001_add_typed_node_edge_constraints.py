"""add_typed_node_edge_constraints

Revision ID: 0001_typed_node_edge
Revises:
Create Date: 2026-03-28

Adds spec-168 constraints to graph_nodes and graph_edges tables.

Strategy: NOT VALID first to avoid locking, then VALIDATE CONSTRAINT
in a separate transaction after any needed backfill.

Also creates:
  - node_type_registry table (10 canonical node types)
  - edge_type_registry table (7 canonical edge types)
  - Index on graph_nodes.phase for lifecycle_state filtering
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_typed_node_edge"
down_revision = None
branch_labels = None
depends_on = None

VALID_NODE_TYPES = (
    "idea", "concept", "spec", "implementation", "service",
    "contributor", "domain", "pipeline-run", "event", "artifact",
)

VALID_EDGE_TYPES = (
    "inspires", "depends-on", "implements", "contradicts",
    "extends", "analogous-to", "parent-of",
)


def upgrade() -> None:
    # ── graph_nodes: add CHECK constraint (NOT VALID to avoid table lock) ──
    node_type_list = "', '".join(VALID_NODE_TYPES)
    op.execute(
        f"""
        ALTER TABLE graph_nodes
          ADD CONSTRAINT IF NOT EXISTS chk_node_type
          CHECK (type IN ('{node_type_list}'))
          NOT VALID;
        """
    )

    # ── graph_edges: add CHECK constraint (NOT VALID) ──────────────────
    edge_type_list = "', '".join(VALID_EDGE_TYPES)
    op.execute(
        f"""
        ALTER TABLE graph_edges
          ADD CONSTRAINT IF NOT EXISTS chk_edge_type
          CHECK (type IN ('{edge_type_list}'))
          NOT VALID;
        """
    )

    # ── graph_edges: prevent self-loops ────────────────────────────────
    op.execute(
        """
        ALTER TABLE graph_edges
          ADD CONSTRAINT IF NOT EXISTS chk_no_self_loop
          CHECK (from_id != to_id)
          NOT VALID;
        """
    )

    # ── Index on phase for lifecycle_state filtering ────────────────────
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_graph_nodes_phase
          ON graph_nodes (phase);
        """
    )

    # ── node_type_registry table ────────────────────────────────────────
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS node_type_registry (
          type_name         VARCHAR(64) PRIMARY KEY,
          description       TEXT NOT NULL,
          lifecycle_default VARCHAR(16) NOT NULL DEFAULT 'gas',
          payload_schema    TEXT NOT NULL DEFAULT '{}',
          created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )

    # Seed node type registry
    node_types = [
        ("idea", "A tracked concept or proposal — the primary entry point for new work", "gas"),
        ("concept", "An abstract or theoretical construct that underpins multiple ideas", "gas"),
        ("spec", "A written specification document defining behaviour, contracts, or requirements", "ice"),
        ("implementation", "A code artifact, PR, or deployed feature that realises a spec", "water"),
        ("service", "A running software service or API that the network depends on", "water"),
        ("contributor", "A human or AI agent who contributes work to the network", "water"),
        ("domain", "A knowledge domain or bounded namespace that groups related nodes", "ice"),
        ("pipeline-run", "A single execution of a pipeline stage or workflow", "water"),
        ("event", "A system event or signal — task-completed, score-changed, etc.", "water"),
        ("artifact", "A produced output — test file, doc, report, or generated asset", "water"),
    ]
    for type_name, description, lifecycle_default in node_types:
        op.execute(
            f"""
            INSERT INTO node_type_registry (type_name, description, lifecycle_default)
            VALUES ('{type_name}', '{description}', '{lifecycle_default}')
            ON CONFLICT (type_name) DO NOTHING;
            """
        )

    # ── edge_type_registry table ────────────────────────────────────────
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS edge_type_registry (
          type_name    VARCHAR(64) PRIMARY KEY,
          description  TEXT NOT NULL,
          is_symmetric BOOLEAN NOT NULL DEFAULT FALSE,
          example_text TEXT,
          created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )

    # Seed edge type registry
    edge_types = [
        ("inspires", "A gave rise to or motivated B without directly implementing it", False),
        ("depends-on", "A requires B to function correctly or to be implemented first", False),
        ("implements", "A puts B into practice — code realizes a spec, a spec realizes an idea", False),
        ("contradicts", "A and B are in tension or mutually exclusive", True),
        ("extends", "A adds to or refines B, building on its foundation without replacing it", False),
        ("analogous-to", "A and B are structurally isomorphic or conceptually parallel", True),
        ("parent-of", "A hierarchically contains B — A is the container, B is the sub-unit", False),
    ]
    for type_name, description, is_symmetric in edge_types:
        is_sym_str = "TRUE" if is_symmetric else "FALSE"
        op.execute(
            f"""
            INSERT INTO edge_type_registry (type_name, description, is_symmetric)
            VALUES ('{type_name}', '{description}', {is_sym_str})
            ON CONFLICT (type_name) DO NOTHING;
            """
        )


def downgrade() -> None:
    op.execute("ALTER TABLE graph_nodes DROP CONSTRAINT IF EXISTS chk_node_type;")
    op.execute("ALTER TABLE graph_edges DROP CONSTRAINT IF EXISTS chk_edge_type;")
    op.execute("ALTER TABLE graph_edges DROP CONSTRAINT IF EXISTS chk_no_self_loop;")
    op.execute("DROP INDEX IF EXISTS idx_graph_nodes_phase;")
    op.execute("DROP TABLE IF EXISTS edge_type_registry;")
    op.execute("DROP TABLE IF EXISTS node_type_registry;")
