#!/usr/bin/env bash
# Substrate auto-ingest hook.
#
# Drop this in `.git/hooks/post-merge` (or post-commit, post-checkout) to
# keep the substrate in sync with the body's tissue. After every merge,
# changed .md files in tracked domains (specs/, ideas/, vision-kb/concepts/,
# presences/, memory/) are re-ingested.
#
# Manual install:
#   ln -s ../../scripts/substrate_post_merge_hook.sh .git/hooks/post-merge
#   chmod +x .git/hooks/post-merge
#
# Or invoke directly:
#   bash scripts/substrate_post_merge_hook.sh
#
# In CI, call this from a workflow step after the merge commit lands.

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# Detect the merge range. For post-merge hook, ORIG_HEAD is the previous
# HEAD; current HEAD is the merge commit. For post-commit, use HEAD~1..HEAD.
if git rev-parse --verify ORIG_HEAD >/dev/null 2>&1; then
    RANGE="ORIG_HEAD..HEAD"
else
    RANGE="HEAD~1..HEAD"
fi

CHANGED=$(git diff --name-only --diff-filter=AM "$RANGE" -- '*.md' 2>/dev/null || true)

if [ -z "$CHANGED" ]; then
    echo "[substrate] no .md changes in $RANGE — substrate stays current"
    exit 0
fi

echo "[substrate] re-ingesting changed .md files:"
echo "$CHANGED" | python3 scripts/coh_substrate.py ingest-paths --from-stdin
