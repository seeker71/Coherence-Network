#!/usr/bin/env python3
"""Database migration script to drop and recreate tables with new schema."""

import os
import sys
from sqlalchemy import create_engine, text


def migrate_database():
    """Drop old tables and recreate with new schema."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)

    print(f"Connecting to database...")
    engine = create_engine(database_url, pool_pre_ping=True)

    # Drop existing tables
    print("Dropping old tables...")
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS contributions CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS assets CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS contributors CASCADE;"))
        conn.commit()

    print("Creating new tables with updated schema...")
    # Import after dropping to ensure we use the new schema
    from app.adapters.postgres_store import Base
    Base.metadata.create_all(bind=engine)

    print("✓ Database migration complete!")
    print("  - contributors: added type, wallet_address, hourly_rate")
    print("  - assets: changed from name/asset_type to description/type")
    print("  - contributions: unchanged")


if __name__ == "__main__":
    migrate_database()
