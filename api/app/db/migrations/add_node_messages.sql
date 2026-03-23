-- Migration: add node_messages table for persistent inter-node messaging
-- Replaces the in-memory _MESSAGE_STORE that was lost on API restart.
-- ORM model NodeMessageRecord handles creation via Base.metadata.create_all.

CREATE TABLE IF NOT EXISTS node_messages (
    id              TEXT PRIMARY KEY,
    from_node       TEXT NOT NULL,
    to_node         TEXT,               -- NULL = broadcast to all nodes
    type            TEXT NOT NULL DEFAULT 'text',
    text            TEXT NOT NULL DEFAULT '',
    payload_json    TEXT NOT NULL DEFAULT '{}',
    timestamp       TEXT NOT NULL,
    read_by_json    TEXT NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_nm_from_node ON node_messages (from_node);
CREATE INDEX IF NOT EXISTS idx_nm_to_node ON node_messages (to_node);
CREATE INDEX IF NOT EXISTS idx_nm_timestamp ON node_messages (timestamp);
