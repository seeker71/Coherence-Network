#!/usr/bin/env python3
"""Non-destructive migration to add new columns for Paperclip and Hermes features."""

import os
import sys
from sqlalchemy import create_engine, text

def migrate():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)

    print("Connecting to database...")
    engine = create_engine(database_url, pool_pre_ping=True)

    with engine.connect() as conn:
        print("Migrating federation_nodes...")
        # Add is_autonomous
        try:
            conn.execute(text("ALTER TABLE federation_nodes ADD COLUMN IF NOT EXISTS is_autonomous BOOLEAN DEFAULT FALSE NOT NULL;"))
            print("  - Added is_autonomous")
        except Exception as e:
            print(f"  - Skip/Error is_autonomous: {e}")

        # Add heartbeat_interval_ms
        try:
            conn.execute(text("ALTER TABLE federation_nodes ADD COLUMN IF NOT EXISTS heartbeat_interval_ms INTEGER DEFAULT 900000 NOT NULL;"))
            print("  - Added heartbeat_interval_ms")
        except Exception as e:
            print(f"  - Skip/Error heartbeat_interval_ms: {e}")

        print("Migrating contributors...")
        # Add daily_cc_budget
        try:
            conn.execute(text("ALTER TABLE contributors ADD COLUMN IF NOT EXISTS daily_cc_budget NUMERIC(20, 2);"))
            print("  - Added daily_cc_budget")
        except Exception as e:
            print(f"  - Skip/Error daily_cc_budget: {e}")

        # Add monthly_cc_budget
        try:
            conn.execute(text("ALTER TABLE contributors ADD COLUMN IF NOT EXISTS monthly_cc_budget NUMERIC(20, 2);"))
            print("  - Added monthly_cc_budget")
        except Exception as e:
            print(f"  - Skip/Error monthly_cc_budget: {e}")

        conn.commit()
    print("Done!")

if __name__ == "__main__":
    migrate()
