-- Spec 134: Federation Strategy Propagation
-- Creates the node_strategy_broadcasts table for storing hub strategy
-- advisory broadcasts consumed by federation nodes.

CREATE TABLE IF NOT EXISTS node_strategy_broadcasts (
    id             SERIAL PRIMARY KEY,
    strategy_type  VARCHAR NOT NULL CHECK (
      strategy_type IN (
        'provider_recommendation',
        'prompt_variant_winner',
        'provider_warning'
      )
    ),
    payload_json   TEXT NOT NULL,
    source_node_id VARCHAR NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at     TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_nsb_strategy_type_created_at
  ON node_strategy_broadcasts (strategy_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_nsb_expires_at
  ON node_strategy_broadcasts (expires_at);
