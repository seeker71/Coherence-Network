#!/usr/bin/env bash
# Substrate auto-ingest hook.
#
# Drop this in `.git/hooks/post-merge` (or post-commit, post-checkout) to
# keep the substrate in sync with the body's tissue. After every merge,
# changed .md files in tracked domains (specs/, ideas/, vision-kb/concepts/,
# presences/, memory/) AND non-.md source files under web/app/, web/components/,
# web/lib/, api/app/routers/, api/app/services/ are re-ingested. Non-.md
# files land as ARTIFACT cells so /api/substrate/page can annotate any web
# route or API router.
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

CHANGED_MD=$(git diff --name-only --diff-filter=AM "$RANGE" -- '*.md' 2>/dev/null || true)

# Source files the substrate carries as ARTIFACT cells. Web/API surfaces
# /api/substrate/page resolves against (page.tsx, layouts, components/lib,
# routers, services), plus substrate-native shape-files (.form) and
# stdlib/kernel sources (.fk) so the substrate sees its own teaching tissue.
CHANGED_CODE=$(git diff --name-only --diff-filter=AM "$RANGE" -- \
    'web/app/**/page.tsx' \
    'web/app/**/layout.tsx' \
    'web/components/**/*.tsx' \
    'web/lib/**/*.ts' \
    'api/app/routers/*.py' \
    'api/app/services/*.py' \
    'docs/coherence-substrate/*.form' \
    'experiments/form-stdlib/**/*.fk' 2>/dev/null || true)

CHANGED=$(printf "%s\n%s" "$CHANGED_MD" "$CHANGED_CODE" | sed '/^$/d')

if [ -z "$CHANGED" ]; then
    echo "[substrate] no tracked changes in $RANGE — substrate stays current"
    exit 0
fi

echo "[substrate] re-ingesting changed files:"
echo "$CHANGED" | python3 scripts/coh_substrate.py ingest-paths --from-stdin
