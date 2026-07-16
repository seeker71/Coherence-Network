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
    RANGE_FROM="ORIG_HEAD"
    RANGE_TO="HEAD"
else
    RANGE_FROM="HEAD~1"
    RANGE_TO="HEAD"
fi
RANGE="${RANGE_FROM}..${RANGE_TO}"

# Git updates the superproject gitlink before it updates the submodule working
# tree. A real post-merge invocation therefore arrives with `form/` at the
# previous pin (or absent on the tracked-tree -> gitlink migration). Hydrate the
# reviewed snapshot before any Blueprint, training, RAG, or ingest read.
sync_pinned_submodules() {
    python3 scripts/prepare_form_submodule.py --repo-root .
    git submodule sync --recursive
    git submodule update --init --recursive
    python3 scripts/prepare_form_submodule.py --repo-root . --verify-clean
}

sync_pinned_submodules

# Preserve the superproject paths while expanding a `form` gitlink bump into
# the changed paths inside coherence-kernel. The initialized submodule's object
# store normally retains both pins. A shallow/missing old pin falls back to the
# complete new snapshot; an unavailable new pin emits a sentinel that routes
# every dependent surface through its conservative full-refresh behavior.
changed_paths_between() {
    local from="$1" to="$2"
    local changed nested old_entry new_entry old_mode new_mode old_oid new_oid

    if ! changed="$(git diff --name-only "$from".."$to" 2>/dev/null)"; then
        return 1
    fi
    printf '%s\n' "$changed" | sed '/^$/d'
    if ! grep -Fxq 'form' <<< "$changed"; then
        return 0
    fi

    old_entry="$(git ls-tree "$from" -- form 2>/dev/null || true)"
    new_entry="$(git ls-tree "$to" -- form 2>/dev/null || true)"
    read -r old_mode _ old_oid _ <<< "$old_entry"
    read -r new_mode _ new_oid _ <<< "$new_entry"

    if [[ "$old_mode" == "160000" && "$new_mode" == "160000" ]] \
      && git -C form cat-file -e "${old_oid}^{commit}" 2>/dev/null \
      && git -C form cat-file -e "${new_oid}^{commit}" 2>/dev/null; then
        if nested="$(git -C form diff --name-only "$old_oid".."$new_oid" 2>/dev/null)"; then
            printf '%s\n' "$nested" | sed '/^$/d; s#^#form/#'
            return 0
        fi
    fi

    if [[ "$new_mode" == "160000" ]] \
      && git -C form cat-file -e "${new_oid}^{commit}" 2>/dev/null; then
        if nested="$(git -C form ls-tree -r --name-only "$new_oid" 2>/dev/null)"; then
            printf '%s\n' "$nested" | sed '/^$/d; s#^#form/#'
            return 0
        fi
    fi

    printf '%s\n' 'form/.gitlink-diff-unavailable'
}

changed_path_routes() {
    local changed="$1"
    if grep -Eq '^(form/form-stdlib/form-ontology\.json|form/form-stdlib/blueprint-registry\.json)$' <<< "$changed"; then
        printf '%s\n' blueprint
    fi
    if grep -Fxq 'api/app/services/substrate/category.py' <<< "$changed"; then
        printf '%s\n' vocabulary
    fi
    if grep -E '\.(fk|form)$' <<< "$changed" | grep -Ev '^form/' >/dev/null; then
        printf '%s\n' training
    fi
    if grep -Eq '^(form/form-stdlib/.*\.fk|specs/.*\.md|docs/vision-kb/concepts/.*\.md|docs/coherence-substrate/.*\.form|docs/shared/.*\.md)$' <<< "$changed"; then
        printf '%s\n' rag
    fi
    if grep -Fxq 'form/.gitlink-diff-unavailable' <<< "$changed"; then
        printf '%s\n' blueprint rag full-form-refresh
    fi
}

if ! ALL_CHANGED="$(changed_paths_between "$RANGE_FROM" "$RANGE_TO")"; then
    ALL_CHANGED='form/.gitlink-diff-unavailable'
fi
CHANGED_ROUTES="$(changed_path_routes "$ALL_CHANGED")"

CHANGED_MD=$(printf '%s\n' "$ALL_CHANGED" | while IFS= read -r path; do
    [[ "$path" == *.md && -f "$path" ]] && printf '%s\n' "$path"
done || true)

# Source files the substrate carries as ARTIFACT cells. Web/API surfaces
# /api/substrate/page resolves against (page.tsx, layouts, components/lib,
# routers, services), plus substrate-native shape-files (.form) and
# stdlib/kernel sources (.fk) so the substrate sees its own teaching tissue.
CHANGED_CODE=$(printf '%s\n' "$ALL_CHANGED" \
    | grep -E '^(web/app/(.*/)?(page|layout)\.tsx|web/components/.*\.tsx|web/lib/.*\.ts|api/app/routers/[^/]*\.py|api/app/services/[^/]*\.py|docs/coherence-substrate/[^/]*\.form|docs/shared/[^/]*\.md|form/form-stdlib/.*\.fk)$' \
    | while IFS= read -r path; do
        [[ -f "$path" ]] && printf '%s\n' "$path"
      done \
    || true)

# Form Blueprint registry → substrate NamedCells. The offline kernels read the
# JSON files; the substrate needs the names projected in so it can answer
# "what is 1.2.99.10 called". Runs whenever either authored file changed —
# independent of the markdown/code ingestion below.
if grep -Fxq blueprint <<< "$CHANGED_ROUTES"; then
    echo "[substrate] Blueprint registry changed — projecting names into NamedCells:"
    python3 scripts/sync_blueprints_to_substrate.py
    # Kernel bp tables are canonical coherence-kernel source. Their generator
    # runs in that repository's publish gate; this consumer only projects the
    # reviewed snapshot and never rewrites the submodule working tree.
fi

# Substrate vocabulary (category.py enums) → substrate NamedCells. When the
# type/domain/recipe alphabet shifts, re-project so the DB stays self-describing
# ("what is type 12" → RBasic.MATH). Code-sourced — no external files needed.
if grep -Fxq vocabulary <<< "$CHANGED_ROUTES"; then
    echo "[substrate] category vocabulary changed — projecting enum names into NamedCells:"
    python3 scripts/sync_substrate_vocabulary.py
fi

# Superproject-owned .fk/.form changes feed the form-cli training catalog's
# commit-to-diff lane. Kernel-internal pairs are captured in coherence-kernel;
# this consumer range contains only its gitlink and cannot truthfully reproduce
# those commits. Never fail the merge over catalog capture.
if grep -Fxq training <<< "$CHANGED_ROUTES"; then
    echo "[catalog] feeding git (message->diff) pairs from $RANGE:"
    python3 scripts/training_corpus.py --source git --range "$RANGE" || true
fi

CHANGED=$(printf "%s\n%s" "$CHANGED_MD" "$CHANGED_CODE" | sed '/^$/d')

if grep -Fxq full-form-refresh <<< "$CHANGED_ROUTES"; then
    echo "[substrate] form gitlink commits unavailable — bootstrapping the complete grounded body:"
    python3 scripts/coh_substrate.py bootstrap
fi

if [ -z "$CHANGED" ]; then
    if grep -Fxq rag <<< "$CHANGED_ROUTES"; then
        echo "[rag] corpus changed outside the ingest set — refusing a path-only index refresh" >&2
        exit 1
    fi
    echo "[substrate] no tracked changes in $RANGE — substrate stays current"
    exit 0
fi

echo "[substrate] re-ingesting changed files:"
echo "$CHANGED" | python3 scripts/coh_substrate.py ingest-paths --from-stdin

# Materialize only after the substrate mutation commits. The index id is the
# source cell's CTOR NodeID, so healing before ingest would bind new bytes to an
# old identity. The Python file is the retiring host projection; ranking and the
# serving gate remain Form-native.
if grep -Fxq rag <<< "$CHANGED_ROUTES"; then
    echo "[rag] healing the NodeID-backed form-cli index for $RANGE:"
    bash scripts/ensure_form_cli_native.sh >/dev/null
    python3 scripts/form_cli_rag.py heal
fi
