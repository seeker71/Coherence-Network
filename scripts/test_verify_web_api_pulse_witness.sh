#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

fixture_dir="$(mktemp -d)"
trap 'rm -rf "$fixture_dir"' EXIT

mkdir -p "$fixture_dir/pulse"

VERIFY_WEB_API_DEPLOY_SOURCE_ONLY=1 source "$ROOT_DIR/scripts/verify_web_api_deploy.sh" "http://api.example" "http://web.example"
source_tmp_dir="$TMP_DIR"
trap 'rm -rf "$fixture_dir" "$source_tmp_dir"' EXIT

cat >"$fixture_dir/pulse/now" <<'JSON'
{
  "overall": "strained",
  "checked_at": "2026-05-08T00:00:00Z",
  "witness_started_at": "2026-05-08T00:00:00Z",
  "organs": [
    {
      "name": "api",
      "label": "API",
      "description": "public API",
      "status": "strained",
      "latency_ms": 1234,
      "last_sample_at": "2026-05-08T00:00:00Z",
      "detail": "slow: /api/health took 1234ms"
    }
  ],
  "ongoing_silences": []
}
JSON

strained_output="$(
  PULSE_URL="file://$fixture_dir" PULSE_RECHECK_SECONDS=0 check_pulse_witness
)"

grep -F "Strained organs:" <<<"$strained_output" >/dev/null
grep -F -- "- api: strained; slow: /api/health took 1234ms; 1234ms; last_sample_at=2026-05-08T00:00:00Z" <<<"$strained_output" >/dev/null
grep -F "after_recheck overall=strained ongoing_silences=0" <<<"$strained_output" >/dev/null
grep -F "WARN: overall=strained with no ongoing silences after recheck" <<<"$strained_output" >/dev/null

cat >"$fixture_dir/pulse/now" <<'JSON'
{
  "overall": "silent",
  "checked_at": "2026-05-08T00:00:00Z",
  "witness_started_at": "2026-05-08T00:00:00Z",
  "organs": [
    {
      "name": "web",
      "label": "Web",
      "description": "public web",
      "status": "silent",
      "latency_ms": null,
      "last_sample_at": "2026-05-08T00:00:00Z",
      "detail": "5xx: / returned 503"
    }
  ],
  "ongoing_silences": [
    {
      "id": 17,
      "organ": "web",
      "started_at": "2026-05-08T00:00:00Z",
      "severity": "silent",
      "duration_seconds": 301
    }
  ]
}
JSON

set +e
silent_output="$(
  PULSE_URL="file://$fixture_dir" PULSE_RECHECK_SECONDS=0 check_pulse_witness
)"
silent_rc=$?
set -e

test "$silent_rc" -eq 1
grep -F "FAIL: pulse reports ongoing silences" <<<"$silent_output" >/dev/null
grep -F "Silent organs: web" <<<"$silent_output" >/dev/null

echo "PASS: pulse witness strain summary and recheck"
