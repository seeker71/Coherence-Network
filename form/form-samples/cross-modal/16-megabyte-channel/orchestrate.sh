#!/usr/bin/env bash
# orchestrate.sh — runs cell A then cell B as separate kernel processes
# in DIFFERENT kernel languages, then verifies the protocol.
#
# Cell A runs in the Go kernel.
# Cell B runs in the Rust kernel.
# (Cross-kernel sibling-parity demonstration: the channel works even
#  though A and B don't share a binary; they share the substrate and
#  the deterministic seeded_bytes native.)
#
# Total channel bytes: ~15. Payload: 1,000,000 bytes. Compression
# ratio: ~66,000:1 for this transfer.

set -euo pipefail

cd "$(dirname "$0")/../../.."  # form/

CHANNEL_DIR="form-samples/cross-modal/16-megabyte-channel/channel"
rm -f "$CHANNEL_DIR"/*.bin "$CHANNEL_DIR"/*.txt
mkdir -p "$CHANNEL_DIR"

echo "=== Megabyte private-channel protocol ==="
echo ""
echo "Cell A — Go kernel — sender"
time form-kernel-go/bin-go form-samples/cross-modal/16-megabyte-channel/cell-a.fk

echo ""
echo "Cell B — Rust kernel — receiver"
time form-kernel-rust/target/release/form-kernel-rust form-samples/cross-modal/16-megabyte-channel/cell-b.fk

echo ""
echo "=== Verification ==="

SUM_A=$(cat "$CHANNEL_DIR/cell-a-sum.txt")
SUM_B=$(cat "$CHANNEL_DIR/cell-b-sum.txt")

# Total bytes across all channel files (the message)
CHANNEL_BYTES=$(stat -c '%s' "$CHANNEL_DIR"/*.bin | awk '{sum+=$1} END {print sum}')
PAYLOAD_BYTES=1000000

echo "Cell A payload sum:   $SUM_A"
echo "Cell B payload sum:   $SUM_B"
echo "Channel bytes total:  $CHANNEL_BYTES"
echo "Payload bytes:        $PAYLOAD_BYTES"

if [[ "$SUM_A" == "$SUM_B" ]]; then
    RATIO=$(( PAYLOAD_BYTES / CHANNEL_BYTES ))
    echo ""
    echo "✓ PROOF: Cell A and Cell B converged on the same payload."
    echo "  Compression ratio: ${RATIO}:1 (payload transmitted via channel)."
    echo "  Different kernels (Go ↔ Rust), same payload, same sum."
    exit 0
else
    echo ""
    echo "✗ MISMATCH: cells diverged. Protocol broken."
    exit 1
fi
