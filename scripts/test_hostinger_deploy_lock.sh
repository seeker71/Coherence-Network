#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/deploy/hostinger/deploy-lock.sh"

wait_for_file() {
  local path="$1" attempt
  for attempt in {1..100}; do
    [[ -f "$path" ]] && return 0
    sleep 0.05
  done
  echo "Timed out waiting for $path" >&2
  return 1
}

mode="${1:-proof}"
fixture="${2:-}"
case "$mode" in
  owner)
    coherence_deploy_lock "$fixture/lock" 2
    touch "$fixture/owner-entered"
    bash "$0" nested "$fixture"
    touch "$fixture/verifying"
    wait_for_file "$fixture/release"
    touch "$fixture/verified"
    ;;
  nested)
    coherence_deploy_lock "$fixture/lock" 2
    touch "$fixture/nested-entered"
    ;;
  contender)
    touch "$fixture/contender-started"
    coherence_deploy_lock "$fixture/lock" 5
    test -f "$fixture/verified"
    touch "$fixture/contender-entered"
    ;;
  timeout)
    coherence_deploy_lock "$fixture/lock" 0.05
    touch "$fixture/timeout-entered"
    ;;
  legacy)
    coherence_deploy_lock "$fixture/lock" 0.1
    touch "$fixture/legacy-entered"
    ;;
  unlocked)
    exec 9>"$fixture/lock"
    coherence_deploy_lock "$fixture/lock" 1
    if flock -n "$fixture/lock" true; then
      echo 'Inherited unlocked descriptor was not acquired' >&2
      exit 1
    fi
    ;;
  duplicate)
    exec 8>"$fixture/lock"
    exec 9>"$fixture/lock"
    flock -w 1 9
    coherence_deploy_lock "$fixture/lock" 0.1
    ;;
  detached-owner)
    coherence_deploy_lock "$fixture/lock" 1
    (
      coherence_deploy_close_descriptors "$fixture/lock"
      touch "$fixture/detached-started"
      wait_for_file "$fixture/detached-release"
      touch "$fixture/detached-done"
    ) &
    echo "$!" > "$fixture/detached-pid"
    wait_for_file "$fixture/detached-started"
    wait_for_file "$fixture/detached-parent-release"
    ;;
  proof)
    command -v flock >/dev/null
    test -d /proc/$$/fd
    fixture="$(mktemp -d)"
    trap 'rm -rf "$fixture"' EXIT
    bash "$0" owner "$fixture" & owner_pid=$!
    wait_for_file "$fixture/verifying"
    test -f "$fixture/nested-entered"
    bash "$0" contender "$fixture" & contender_pid=$!
    wait_for_file "$fixture/contender-started"
    if bash "$0" timeout "$fixture"; then
      echo 'A second owner entered the active verification window' >&2
      exit 1
    else
      test "$?" -eq 75
    fi
    test ! -f "$fixture/contender-entered"
    test ! -f "$fixture/timeout-entered"
    touch "$fixture/release"
    wait "$owner_pid"
    wait "$contender_pid"
    test -f "$fixture/contender-entered"
    flock -w 1 "$fixture/lock" bash "$0" legacy "$fixture"
    test -f "$fixture/legacy-entered"
    ln "$fixture/lock" "$fixture/lock-alias"
    flock -w 1 "$fixture/lock-alias" bash "$0" legacy "$fixture"
    bash "$0" unlocked "$fixture"
    bash "$0" duplicate "$fixture"
    bash "$0" detached-owner "$fixture" & detached_owner_pid=$!
    wait_for_file "$fixture/detached-started"
    if flock -n "$fixture/lock" true; then
      echo 'Detached child released its parent ownership' >&2
      exit 1
    fi
    touch "$fixture/detached-parent-release"
    wait "$detached_owner_pid"
    kill -0 "$(cat "$fixture/detached-pid")"
    flock -n "$fixture/lock" true
    touch "$fixture/detached-release"
    wait_for_file "$fixture/detached-done"
    echo 'deployment ownership: nested and legacy ownership reused; contenders excluded through verification; timeout, inode alias, duplicate/unlocked descriptors and detached-child release passed'
    ;;
  *) exit 64 ;;
esac
