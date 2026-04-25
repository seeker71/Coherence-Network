#!/usr/bin/env python3
"""Database migration script to drop and recreate tables with unified graph schema."""

import os
import sys
from sqlalchemy import create_engine, text


def migrate_database():
    """Drop old tables and recreate with unified graph schema."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)

    print("Connecting to database...")
    engine = create_engine(database_url, pool_pre_ping=True)

    # Drop existing tables (both old and new)
    print("Dropping old tables...")
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS graph_edges CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS graph_nodes CASCADE;"))
        # Legacy tables (safe to drop even if they don't exist)
        conn.execute(text("DROP TABLE IF EXISTS contributions CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS assets CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS contributors CASCADE;"))
        conn.commit()

    print("Creating new tables with unified graph schema...")
    from app.models.graph import Base
    Base.metadata.create_all(bind=engine)

    print("Done! Unified graph schema:")
    print("  - graph_nodes: universal entity store (contributors, assets, ideas, specs, etc.)")
    print("  - graph_edges: universal relationship store (contributions, dependencies, etc.)")


if __name__ == "__main__":
    migrate_database()
