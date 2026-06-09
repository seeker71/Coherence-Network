#!/usr/bin/env bash
set -euo pipefail

API_URL="${1:-${PUBLIC_API_BASE_URL:-https://api.coherencycoin.com}}"
API_URL="${API_URL%/}"
ATTEMPTS="${KERNEL_CANARY_VERIFY_ATTEMPTS:-12}"
SLEEP_SECONDS="${KERNEL_CANARY_VERIFY_SLEEP_SECONDS:-10}"
CURL_MAX_TIME="${CURL_MAX_TIME:-20}"
CURL_CONNECT_TIMEOUT="${CURL_CONNECT_TIMEOUT:-5}"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

RUN_ID="$(date +%s)-$$"

header_value() {
  local headers_file="$1"
  local key="$2"
  awk -v key="${key}" 'tolower($1)==tolower(key) { $1=""; sub(/^ /,""); print }' \
    "$headers_file" | tr -d '\r' | tail -1
}

assert_public_gate_body() {
  local body_file="$1"
  python3 - "$body_file" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as fh:
    obj = json.load(fh)

decision = obj.get("decision_receipt") or {}
rollback = obj.get("route_local_rollback_receipt") or {}
trust = obj.get("trust_envelope") or {}
reversible = trust.get("reversible_gate") or {}
signature = decision.get("signature") or {}
persistence = obj.get("persistence") or {}

checks = {
    "native_public_gate": obj.get("native_public_gate") is True,
    "native_preview_false": obj.get("native_preview") is False,
    "executes_true": obj.get("executes") is True,
    "db_execution_performed": obj.get("db_execution") == "performed-by-http-native-persistence",
    "persistence_carrier": persistence.get("carrier") == "config_database_url",
    "persistence_executed": persistence.get("executes") is True,
    "persistence_rows": isinstance(persistence.get("rows_affected"), int)
    and persistence.get("rows_affected") >= 0,
    "persistence_closed": persistence.get("close_code") == 0,
    "route_local_gate_executes": obj.get("route_local_gate_executes") is True,
    "decision_state": decision.get("state") == "native-mutation-gate-decision-receipt",
    "decision_selected": decision.get("selected_path") == "X-Form-Native-Public-Gate",
    "decision_reversible": decision.get("reversible") is True,
    "decision_contradicts": decision.get("can_contradict_intent") is True,
    "decision_native_default": decision.get("ordinary_traffic_flip_performed") is True,
    "signature_compact": signature.get("category") == "native-mutation-gate"
    and signature.get("outcome_code") == 1,
    "rollback_native_default": rollback.get("ordinary_traffic_flip_performed") is True,
    "trust_native_default": reversible.get("ordinary_traffic_flip_performed") is True,
}
missing = [name for name, ok in checks.items() if not ok]
if missing:
    raise SystemExit("public gate body failed checks: " + ", ".join(missing))

print(
    "decision_receipt={state} selected={selected} operation={operation} node_id={node_id}".format(
        state=decision.get("state"),
        selected=decision.get("selected_path"),
        operation=decision.get("operation"),
        node_id=decision.get("node_id"),
    )
)
PY
}

echo "kernel-canary-public-gate: probing ${API_URL}/api/ideas"

for attempt in $(seq 1 "$ATTEMPTS"); do
  payload="$(printf '{"id":"idea-public-canary-%s-%s","name":"Public Canary","description":"header-gated public canary","manifestation_status":"partial"}' "$RUN_ID" "$attempt")"
  headers_file="$TMP_DIR/public-gate.headers"
  body_file="$TMP_DIR/public-gate.body"
  status="$(
    curl -sS -D "$headers_file" -o "$body_file" -w "%{http_code}" \
      --max-time "$CURL_MAX_TIME" \
      --connect-timeout "$CURL_CONNECT_TIMEOUT" \
      -X POST "${API_URL}/api/ideas" \
      -H "Content-Type: application/json" \
      -H "X-Form-Native-Public-Gate: 1" \
      --data "$payload" \
      || true
  )"
  router="$(header_value "$headers_file" "x-form-router:")"

  if [[ "$status" == "202" && "$router" == "native-kernel" ]]; then
    if assert_public_gate_body "$body_file"; then
      echo "PASS public-gate treatment status=${status} router=${router}"
      break
    fi
  fi

  if [[ "$attempt" -ge "$ATTEMPTS" ]]; then
    echo "FAIL public-gate treatment did not reach native kernel after ${ATTEMPTS} attempts"
    echo "last_status=${status:-none} last_router=${router:-none}"
    echo "body preview:"
    head -c 500 "$body_file" || true
    echo
    exit 1
  fi

  echo "WAIT public-gate treatment attempt ${attempt}/${ATTEMPTS}: status=${status:-none} router=${router:-none}"
  sleep "$SLEEP_SECONDS"
done

control_headers="$TMP_DIR/control.headers"
control_body="$TMP_DIR/control.body"
control_payload="$(printf '{"id":"idea-public-control-%s","name":"Public Canary Control","description":"no-header public control","manifestation_status":"partial"}' "$RUN_ID")"
control_status="$(
  curl -sS -D "$control_headers" -o "$control_body" -w "%{http_code}" \
    --max-time "$CURL_MAX_TIME" \
    --connect-timeout "$CURL_CONNECT_TIMEOUT" \
    -X POST "${API_URL}/api/ideas" \
    -H "Content-Type: application/json" \
    --data "$control_payload" \
    || true
)"
control_router="$(header_value "$control_headers" "x-form-router:")"

if [[ "$control_status" == "202" || "$control_router" == "native-kernel" ]]; then
  echo "FAIL public Traefik no-header control entered native default route: status=${control_status:-none} router=${control_router:-none}"
  head -c 500 "$control_body" || true
  echo
  exit 1
fi

echo "PASS public Traefik no-header control remains outside native default route status=${control_status:-none} router=${control_router:-none}"
echo "kernel-canary-public-gate: PASS"
