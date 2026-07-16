#!/usr/bin/env bash
# Exercise the complete deployed answer path after a WITNESS is recorded.
set -euo pipefail

ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SHA="${1:-}"
[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "usage: verify_observed_deployment_ask.sh <deployed-sha>" >&2
  exit 2
}

out="$(mktemp)"
err="$(mktemp)"
trap 'rm -f "$out" "$err"' EXIT

query="observed deployment witness $SHA native carrier commitment"
"$ROOT/bin/form-cli" ask "$query" >"$out" 2>"$err"

expected_trust='trust  path:native  grounded:yes  freq:yes  freq-source:certified-form  suffic:yes  observed:yes  -> OBSERVED  decision:accept  reason:ok'
if ! grep -Fqx "$expected_trust" "$err"; then
  echo "deployment ask did not reach native OBSERVED" >&2
  sed 's/^/  /' "$err" >&2
  exit 1
fi

python_bin=""
if [[ -x "$ROOT/api/.venv/bin/python" ]]; then
  python_bin="$ROOT/api/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  python_bin="$(command -v python3)"
fi
[[ -n "$python_bin" ]] || {
  echo "deployment ask answer verifier requires python3" >&2
  exit 3
}

"$python_bin" - "$out" "$SHA" <<'PY'
import json
import sys
from pathlib import Path

payload = Path(sys.argv[1]).read_text(encoding="utf-8")
sha = sys.argv[2]
marker = "\nanswer:"
if marker not in payload:
    raise SystemExit("deployment ask has no exact answer marker")
answer = json.loads(payload.split(marker, 1)[1])
if answer.get("schema") != "deployment-witness-v3-oidc":
    raise SystemExit("deployment ask selected a non-WITNESS answer")
if answer.get("observer") != "github-actions-oidc-public-loopback-and-direct-container-probes":
    raise SystemExit("deployment ask WITNESS has no attributable observer")
if answer.get("observer_authentication") != "github-actions-oidc-v1":
    raise SystemExit("deployment ask WITNESS lacks OIDC authentication")
if answer.get("expected_sha") != sha or answer.get("actual_sha") != sha:
    raise SystemExit("deployment ask answer is not bound to target SHA")
if answer.get("result") != "success":
    raise SystemExit("deployment ask WITNESS result is not success")
if answer.get("kernel_runtime") not in {"inline", "subprocess"}:
    raise SystemExit("deployment ask WITNESS has no live native kernel runtime")
for field in (
    "host_evidence_sha256",
    "recorder_evidence_sha256",
    "stable_health_sha256",
    "direct_probe_body_sha256",
    "commitment_sha256",
    "observer_policy_sha256",
    "reproduced_kernel_binary_sha256",
    "reproduced_form_cli_binary_sha256",
    "evidence_key",
):
    value = answer.get(field)
    if not isinstance(value, str) or len(value) != 64:
        raise SystemExit(f"deployment ask WITNESS has no bound {field}")
for field in ("container_id", "job_workflow_sha", "form_source_commit"):
    value = answer.get(field)
    if not isinstance(value, str) or len(value) not in {40, 64}:
        raise SystemExit(f"deployment ask WITNESS has no bound {field}")
PY

cat "$err"
cat "$out"
