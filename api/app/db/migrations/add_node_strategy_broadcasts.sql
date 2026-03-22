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

-- Effectiveness tracking for acted-on broadcasts. This feeds back into
-- strategy computation so low-effectiveness broadcasts can be down-weighted.
CREATE TABLE IF NOT EXISTS node_strategy_effectiveness (
    id                    SERIAL PRIMARY KEY,
    strategy_broadcast_id INTEGER NOT NULL,
    strategy_type         VARCHAR NOT NULL CHECK (
      strategy_type IN (
        'provider_recommendation',
        'prompt_variant_winner',
        'provider_warning'
      )
    ),
    strategy_target       VARCHAR NOT NULL,
    node_id               VARCHAR NOT NULL,
    was_applied           BOOLEAN NOT NULL DEFAULT TRUE,
    baseline_value_score  DOUBLE PRECISION NOT NULL,
    outcome_value_score   DOUBLE PRECISION NOT NULL,
    improvement_score     DOUBLE PRECISION NOT NULL,
    observed_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    context_json          TEXT NOT NULL DEFAULT '{}',
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_nse_strategy_broadcast_id
  ON node_strategy_effectiveness (strategy_broadcast_id);
CREATE INDEX IF NOT EXISTS idx_nse_strategy_type_target
  ON node_strategy_effectiveness (strategy_type, strategy_target);
CREATE INDEX IF NOT EXISTS idx_nse_created_at
  ON node_strategy_effectiveness (created_at DESC);
