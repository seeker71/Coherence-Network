-- Measurement deduplication: add dedup_key column and unique constraint.
-- dedup_key = SHA-256 of (node_id, decision_point, slot_id, period_start, period_end).
-- When a duplicate arrives, the hub keeps the summary with the higher sample_count.

ALTER TABLE node_measurement_summaries
    ADD COLUMN IF NOT EXISTS dedup_key VARCHAR(64);

-- Backfill existing rows (SHA-256 of concatenated natural key fields).
UPDATE node_measurement_summaries
SET dedup_key = encode(
    sha256(
        (node_id || '|' || decision_point || '|' || slot_id || '|' ||
         period_start::text || '|' || period_end::text)::bytea
    ),
    'hex'
)
WHERE dedup_key IS NULL;

-- Make dedup_key NOT NULL after backfill.
ALTER TABLE node_measurement_summaries
    ALTER COLUMN dedup_key SET NOT NULL;

-- Unique constraint ensures one row per natural key.
CREATE UNIQUE INDEX IF NOT EXISTS idx_nms_dedup_key
    ON node_measurement_summaries (dedup_key);
