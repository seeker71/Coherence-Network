-- Migration: add federation_nodes table (Spec 132)
-- Note: In practice the ORM model FederationNodeRecord and Base.metadata.create_all
-- handle table creation. This file documents the intended schema for reference.

CREATE TABLE IF NOT EXISTS federation_nodes (
    node_id           TEXT PRIMARY KEY,
    hostname          TEXT NOT NULL,
    os_type           TEXT NOT NULL,
    providers_json    TEXT NOT NULL DEFAULT '[]',
    capabilities_json TEXT NOT NULL DEFAULT '{}',
    registered_at     TEXT NOT NULL,
    last_seen_at      TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'online'
);

CREATE INDEX IF NOT EXISTS idx_federation_nodes_status ON federation_nodes (status);
CREATE INDEX IF NOT EXISTS idx_federation_nodes_last_seen_at ON federation_nodes (last_seen_at);
