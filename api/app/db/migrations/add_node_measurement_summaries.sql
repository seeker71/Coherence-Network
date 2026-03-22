-- Spec 131: Federation Measurement Push
-- Creates the node_measurement_summaries table for storing aggregated
-- measurement summaries pushed by federation nodes.

CREATE TABLE IF NOT EXISTS node_measurement_summaries (
    id              SERIAL PRIMARY KEY,
    node_id         TEXT NOT NULL,
    decision_point  TEXT NOT NULL,
    slot_id         TEXT NOT NULL,
    period_start    TIMESTAMPTZ NOT NULL,
    period_end      TIMESTAMPTZ NOT NULL,
    sample_count    INTEGER NOT NULL CHECK (sample_count > 0),
    successes       INTEGER NOT NULL CHECK (successes >= 0),
    failures        INTEGER NOT NULL CHECK (failures >= 0),
    mean_duration_s DOUBLE PRECISION,
    mean_value_score DOUBLE PRECISION NOT NULL CHECK (mean_value_score >= 0.0 AND mean_value_score <= 1.0),
    error_classes_json JSONB NOT NULL DEFAULT '{}',
    pushed_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_sample_count CHECK (sample_count = successes + failures)
);

CREATE INDEX IF NOT EXISTS idx_nms_node_dp ON node_measurement_summaries (node_id, decision_point);
CREATE INDEX IF NOT EXISTS idx_nms_pushed_at ON node_measurement_summaries (pushed_at);
