#!/usr/bin/env bash

# Linux deployment carrier. The open descriptor carries ownership into children,
# including older cron/workflow callers that already hold this same flock.
coherence_deploy_lock() {
  local lock_path="$1" wait_seconds="${2:-600}" descriptor lock_fd candidate=""
  for descriptor in /proc/$BASHPID/fd/*; do
    if [[ "$descriptor" -ef "$lock_path" ]]; then
      lock_fd="${descriptor##*/}"
      if flock -E 75 -n "$lock_fd"; then
        return 0
      fi
      candidate="$lock_fd"
    fi
  done
  if [[ -n "$candidate" ]]; then
    lock_fd="$candidate"
  else
    exec {lock_fd}>"$lock_path"
  fi
  flock -E 75 -w "$wait_seconds" "$lock_fd"
}

# A detached service must close its copies, not unlock the shared open file
# description: rollout and verification still belong to the parent process.
coherence_deploy_close_descriptors() {
  local lock_path="$1" descriptor lock_fd
  for descriptor in /proc/$BASHPID/fd/*; do
    if [[ "$descriptor" -ef "$lock_path" ]]; then
      lock_fd="${descriptor##*/}"
      exec {lock_fd}>&-
    fi
  done
}
