#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

fixture_dir="$(mktemp -d)"
trap 'rm -rf "$fixture_dir"' EXIT

VERIFY_WEB_API_DEPLOY_SOURCE_ONLY=1 source "$ROOT_DIR/scripts/verify_web_api_deploy.sh" "http://api.example" "http://web.example"
source_tmp_dir="$TMP_DIR"
trap 'rm -rf "$fixture_dir" "$source_tmp_dir"' EXIT

html_file="$fixture_dir/root.html"
cat >"$html_file" <<'HTML'
<!doctype html>
<html>
  <head>
    <link rel="stylesheet" href="/_next/static/css/legacy.css" />
    <link rel="stylesheet" href="/_next/static/chunks/next16-shell.css" data-precedence="next" />
    <link rel="stylesheet" href="/_next/static/chunks/next16-shell.css" data-precedence="next" />
  </head>
  <body></body>
</html>
HTML

css_paths=()
while IFS= read -r css_path; do
  css_paths+=("$css_path")
done < <(extract_next_css_paths "$html_file")

test "${#css_paths[@]}" -eq 2
test "${css_paths[0]}" = "/_next/static/css/legacy.css"
test "${css_paths[1]}" = "/_next/static/chunks/next16-shell.css"

echo "PASS: Next CSS asset extraction supports css and chunks paths"
