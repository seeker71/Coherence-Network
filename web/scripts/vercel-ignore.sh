#!/usr/bin/env bash
set -euo pipefail

# Vercel ignoreCommand contract:
# - Exit 0 => skip deployment
# - Exit 1 => continue deployment
#
# Strategy:
# - Always deploy production branch commits.
# - For preview branches, deploy only when web-relevant files changed.

branch="${VERCEL_GIT_COMMIT_REF:-}"
if [ "$branch" = "main" ]; then
  echo "Production branch; do not skip."
  exit 1
fi

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$repo_root"

if ! git rev-parse --verify HEAD^ >/dev/null 2>&1; then
  echo "No parent commit available; do not skip."
  exit 1
fi

changed_files="$(git diff --name-only HEAD^ HEAD || true)"
if [ -z "$changed_files" ]; then
  echo "No changed files detected; skip deployment."
  exit 0
fi

web_changed=0
while IFS= read -r path; do
  [ -z "$path" ] && continue
  case "$path" in
    web/*|package.json|package-lock.json|pnpm-lock.yaml|yarn.lock)
      web_changed=1
      break
      ;;
  esac
done <<EOF
$changed_files
EOF

if [ "$web_changed" -eq 1 ]; then
  echo "Web-relevant changes detected; do not skip."
  exit 1
fi

echo "No web-relevant changes on preview branch; skip deployment."
exit 0
