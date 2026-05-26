#!/usr/bin/env bash
# sync-public-proof.sh — keep web/public/PROOF.md identical to repo-root PROOF.md.
#
# The proof file lives at repo root by design (anyone cloning sees it
# first). For it to be reachable at https://coherencycoin.com/PROOF.md
# the Next.js web/ surface needs a copy under web/public/.
#
# Run before any deploy that touches the web/ surface. CI can also
# call this with --check to verify the two are in sync without writing.
#
# Usage:
#   bash scripts/sync-public-proof.sh           # copy root → web/public
#   bash scripts/sync-public-proof.sh --check   # exit 1 if out of sync

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$REPO_ROOT/PROOF.md"
DST="$REPO_ROOT/web/public/PROOF.md"

if [[ ! -f "$SRC" ]]; then
    echo "ERROR: $SRC not found" >&2
    exit 2
fi

if [[ "${1:-}" == "--check" ]]; then
    if [[ ! -f "$DST" ]]; then
        echo "OUT OF SYNC: $DST does not exist" >&2
        exit 1
    fi
    if ! diff -q "$SRC" "$DST" > /dev/null; then
        echo "OUT OF SYNC: $SRC and $DST differ" >&2
        diff -u "$SRC" "$DST" >&2 || true
        exit 1
    fi
    echo "in sync"
    exit 0
fi

cp "$SRC" "$DST"
echo "synced PROOF.md → web/public/PROOF.md"
