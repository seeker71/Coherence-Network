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
invitation = obj.get("native_invitation") or {}
invitation_received = invitation.get("received") or {}
invitation_translated = invitation.get("translated") or {}
invitation_execution = invitation.get("execution") or {}
invitation_speak = invitation.get("speak_next_time") or {}
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
    "native_invitation_state": invitation.get("state") == "native-invitation-contract",
    "native_invitation_offer": invitation.get("offer_to_know") is True,
    "native_invitation_refusal_signal": invitation.get("refusal_is_signal") is True,
    "native_invitation_received": invitation_received.get("shape") == "ordinary-json-mutation",
    "native_invitation_translated": invitation_translated.get("language")
    == "Form-native mutation recipe"
    and invitation_translated.get("operation") == obj.get("operation")
    and invitation_translated.get("node_id") == obj.get("node_id"),
    "native_invitation_execution": invitation_execution.get("selected_path")
    == "X-Form-Native-Public-Gate"
    and invitation_execution.get("router") == "native-kernel",
    "native_invitation_next": invitation_speak.get("native_protocol")
    == "Form/BML mutation recipe"
    and invitation_speak.get("fallback_header") == "X-Form-Python-Fallback"
    and invitation.get("decline_signal") == "native_invitation_declined",
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

assert_native_default_body() {
  local body_file="$1"
  python3 - "$body_file" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as fh:
    obj = json.load(fh)

decision = obj.get("decision_receipt") or {}
invitation = obj.get("native_invitation") or {}
invitation_received = invitation.get("received") or {}
invitation_translated = invitation.get("translated") or {}
invitation_execution = invitation.get("execution") or {}
invitation_speak = invitation.get("speak_next_time") or {}
rollback = obj.get("route_local_rollback_receipt") or {}
trust = obj.get("trust_envelope") or {}
reversible = trust.get("reversible_gate") or {}
signature = decision.get("signature") or {}
persistence = obj.get("persistence") or {}

checks = {
    "native_default_invitation": obj.get("native_default_invitation") is True,
    "native_public_gate": obj.get("native_public_gate") is True,
    "native_preview_false": obj.get("native_preview") is False,
    "route_binding": obj.get("route_binding") == "kernel-http-native-default-invitation",
    "required_header_absent": obj.get("required_header") is None,
    "fallback_header": obj.get("fallback_header") == "X-Form-Python-Fallback",
    "public_gate_header": obj.get("public_gate_header") == "X-Form-Native-Public-Gate",
    "executes_true": obj.get("executes") is True,
    "db_execution_performed": obj.get("db_execution") == "performed-by-http-native-persistence",
    "persistence_carrier": persistence.get("carrier") == "config_database_url",
    "persistence_executed": persistence.get("executes") is True,
    "persistence_rows": isinstance(persistence.get("rows_affected"), int)
    and persistence.get("rows_affected") >= 0,
    "persistence_closed": persistence.get("close_code") == 0,
    "route_local_gate_executes": obj.get("route_local_gate_executes") is True,
    "decision_state": decision.get("state") == "native-mutation-gate-decision-receipt",
    "decision_selected": decision.get("selected_path") == "implicit-native-invitation",
    "decision_protocol": decision.get("protocol") == "implicit-native-invitation",
    "decision_reversible": decision.get("reversible") is True,
    "decision_contradicts": decision.get("can_contradict_intent") is True,
    "decision_native_default": decision.get("ordinary_traffic_flip_performed") is True,
    "native_invitation_state": invitation.get("state") == "native-invitation-contract",
    "native_invitation_offer": invitation.get("offer_to_know") is True,
    "native_invitation_refusal_signal": invitation.get("refusal_is_signal") is True,
    "native_invitation_received": invitation_received.get("shape") == "ordinary-json-mutation",
    "native_invitation_translated": invitation_translated.get("language")
    == "Form-native mutation recipe"
    and invitation_translated.get("operation") == obj.get("operation")
    and invitation_translated.get("node_id") == obj.get("node_id"),
    "native_invitation_execution": invitation_execution.get("selected_path")
    == "implicit-native-invitation"
    and invitation_execution.get("router") == "native-kernel",
    "native_invitation_next": invitation_speak.get("native_protocol")
    == "Form/BML mutation recipe"
    and invitation_speak.get("fallback_header") == "X-Form-Python-Fallback"
    and invitation.get("decline_signal") == "native_invitation_declined",
    "signature_compact": signature.get("category") == "native-mutation-gate"
    and signature.get("selected_path") == "implicit-native-invitation"
    and signature.get("outcome_code") == 1,
    "rollback_native_default": rollback.get("ordinary_traffic_flip_performed") is True,
    "trust_selected": trust.get("selected_path") == "implicit-native-invitation",
    "trust_native_default": reversible.get("ordinary_traffic_flip_performed") is True,
}
missing = [name for name, ok in checks.items() if not ok]
if missing:
    raise SystemExit("native default body failed checks: " + ", ".join(missing))

print(
    "default_decision={state} selected={selected} operation={operation} node_id={node_id}".format(
        state=decision.get("state"),
        selected=decision.get("selected_path"),
        operation=decision.get("operation"),
        node_id=decision.get("node_id"),
    )
)
PY
}

assert_kernel_runtime_body() {
  local body_file="$1"
  python3 - "$body_file" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as fh:
    obj = json.load(fh)

measurements = obj.get("measurements") or {}
matrix = obj.get("matrix")
candidate = obj.get("next_bml_candidate") or {}
int_keys = (
    "native_route_count",
    "observed_native_route_count",
    "observed_path_count",
    "total_requests",
    "native_requests",
    "fanout_requests",
    "choice_attempts",
    "choice_successes",
    "choice_failures",
)
checks = {
    "source": obj.get("source") == "kernel-router:live-metrics",
    "matrix_shape": isinstance(matrix, list)
    and len(matrix) == 2
    and all(isinstance(row, list) and len(row) == 2 for row in matrix),
    "candidate_path": isinstance(candidate.get("path"), str),
}
for key in int_keys:
    checks[key] = isinstance(measurements.get(key), int)

checks["native_routes_present"] = measurements.get("native_route_count", 0) > 0
checks["native_front_door_observed"] = measurements.get("native_requests", 0) > 0
checks["requests_observed"] = measurements.get("total_requests", 0) > 0

missing = [name for name, ok in checks.items() if not ok]
if missing:
    raise SystemExit("kernel runtime body failed checks: " + ", ".join(missing))

print(
    "native_route_count={native_route_count} total_requests={total_requests} "
    "native_requests={native_requests} fanout_requests={fanout_requests}".format(**measurements)
)
PY
}

echo "kernel-canary-public-gate: probing ${API_URL}/api/ideas"

for attempt in $(seq 1 "$ATTEMPTS"); do
  payload="$(printf '{"id":"idea-public-canary-%s-%s","name":"Public Canary","description":"header-gated public canary","potential_value":1,"estimated_cost":1,"manifestation_status":"partial"}' "$RUN_ID" "$attempt")"
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

for attempt in $(seq 1 "$ATTEMPTS"); do
  default_headers="$TMP_DIR/default.headers"
  default_body="$TMP_DIR/default.body"
  default_payload="$(printf '{"id":"idea-public-default-%s-%s","name":"Public Native Default","description":"no-header native default invitation","potential_value":1,"estimated_cost":1,"manifestation_status":"partial"}' "$RUN_ID" "$attempt")"
  default_status="$(
    curl -sS -D "$default_headers" -o "$default_body" -w "%{http_code}" \
      --max-time "$CURL_MAX_TIME" \
      --connect-timeout "$CURL_CONNECT_TIMEOUT" \
      -X POST "${API_URL}/api/ideas" \
      -H "Content-Type: application/json" \
      --data "$default_payload" \
      || true
  )"
  default_router="$(header_value "$default_headers" "x-form-router:")"

  if [[ "$default_status" == "202" && "$default_router" == "native-kernel" ]]; then
    if assert_native_default_body "$default_body"; then
      echo "PASS public Traefik no-header default entered native default route status=${default_status} router=${default_router}"
      break
    fi
  fi

  if [[ "$attempt" -ge "$ATTEMPTS" ]]; then
    echo "FAIL public Traefik no-header default did not enter native default route after ${ATTEMPTS} attempts"
    echo "last_status=${default_status:-none} last_router=${default_router:-none}"
    echo "body preview:"
    head -c 500 "$default_body" || true
    echo
    exit 1
  fi

  echo "WAIT no-header default attempt ${attempt}/${ATTEMPTS}: status=${default_status:-none} router=${default_router:-none}"
  sleep "$SLEEP_SECONDS"
done

echo "kernel-canary-public-gate: probing no-header native front door ${API_URL}/api/attention/kernel-runtime"

for attempt in $(seq 1 "$ATTEMPTS"); do
  runtime_headers="$TMP_DIR/kernel-runtime.headers"
  runtime_body="$TMP_DIR/kernel-runtime.body"
  runtime_status="$(
    curl -sS -D "$runtime_headers" -o "$runtime_body" -w "%{http_code}" \
      --max-time "$CURL_MAX_TIME" \
      --connect-timeout "$CURL_CONNECT_TIMEOUT" \
      "${API_URL}/api/attention/kernel-runtime" \
      -H "Accept: application/json" \
      || true
  )"
  runtime_router="$(header_value "$runtime_headers" "x-form-router:")"
  runtime_handler="$(header_value "$runtime_headers" "x-form-handler:")"

  if [[ "$runtime_status" == "200" && "$runtime_router" == "native-kernel" && "$runtime_handler" == "api_attention_kernel_runtime" ]]; then
    if assert_kernel_runtime_body "$runtime_body"; then
      echo "PASS ordinary API host enters stable native attention front door status=${runtime_status} router=${runtime_router} handler=${runtime_handler}"
      break
    fi
  fi

  if [[ "$attempt" -ge "$ATTEMPTS" ]]; then
    echo "FAIL ordinary API host did not reach native front door after ${ATTEMPTS} attempts"
    echo "last_status=${runtime_status:-none} last_router=${runtime_router:-none} last_handler=${runtime_handler:-none}"
    echo "body preview:"
    head -c 500 "$runtime_body" || true
    echo
    exit 1
  fi

  echo "WAIT native front-door attempt ${attempt}/${ATTEMPTS}: status=${runtime_status:-none} router=${runtime_router:-none} handler=${runtime_handler:-none}"
  sleep "$SLEEP_SECONDS"
done

fallback_headers="$TMP_DIR/fallback.headers"
fallback_body="$TMP_DIR/fallback.body"
fallback_status="$(
  curl -sS -D "$fallback_headers" -o "$fallback_body" -w "%{http_code}" \
    --max-time "$CURL_MAX_TIME" \
    --connect-timeout "$CURL_CONNECT_TIMEOUT" \
    -X POST "${API_URL}/api/ideas" \
    -H "Content-Type: application/json" \
    -H "X-Form-Python-Fallback: 1" \
    --data '{}' \
    || true
)"
fallback_router="$(header_value "$fallback_headers" "x-form-router:")"

if [[ "$fallback_router" != "fanout-python" ]]; then
  echo "FAIL public explicit fallback did not fan out through kernel-router: status=${fallback_status:-none} router=${fallback_router:-none}"
  head -c 500 "$fallback_body" || true
  echo
  exit 1
fi

echo "PASS public explicit fallback remains observable status=${fallback_status:-none} router=${fallback_router}"
echo "kernel-canary-public-gate: PASS"
