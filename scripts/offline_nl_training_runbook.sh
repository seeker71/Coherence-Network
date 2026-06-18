#!/usr/bin/env bash
# offline_nl_training_runbook.sh — the terminal teacher AND runner for training our
# own Form-native NL→NL model OFFLINE, with no Claude agent and no internet.
#
# Run it with no arguments to PRINT the full instructions to the terminal:
#     bash scripts/offline_nl_training_runbook.sh
# Run `check` to verify the offline prerequisites are present:
#     bash scripts/offline_nl_training_runbook.sh check
# Run `run` to execute the whole offline pipeline on a corpus already on disk:
#     bash scripts/offline_nl_training_runbook.sh run <corpus.jsonl> [options]
#
# OFFLINE GUARANTEE: every step computes through the LOCAL Form kernel binary
# (form/form-kernel-go/bin-go) over files already on your disk. No URL is fetched,
# no model is downloaded, no agent is called. If the kernel binary must be built,
# it is built from the local Go module cache with GOPROXY=off — the network is
# never touched. Companion reference (agent-facing):
# docs/coherence-substrate/offline-nl-translation-training.form
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GO="$ROOT/form/form-kernel-go/bin-go"
PART="$ROOT/scripts/corpus_partition_by_license.sh"
TRAIN="$ROOT/scripts/form_cli_transformer_train_wide.sh"

print_help() {
cat <<'TXT'
────────────────────────────────────────────────────────────────────────────
 OFFLINE NL→NL Form-native training — terminal runbook (no agent, no internet)
────────────────────────────────────────────────────────────────────────────

WHAT THIS DOES
  Trains our OWN Form-native NL→NL model from content you already have on disk.
  The model's compute is Form (proven on four kernels); only file reading/writing
  is a host carrier. Copyright-restricted material is held to TESTING only — it is
  never folded into the weight update.

THE RULE (enforced, not just intended)
  We CANNOT train on copyrighted material. A fail-closed Form gate decides what is
  lawful to train on by each corpus row's provenance:
    train-eligible  →  owned | public-domain | permissive | consented
    test-only       →  copyright, all-rights-reserved, AND anything UNKNOWN
  Uncertainty never trains. Copyright MAY be used to TEST (measure the model's loss
  on it), never to learn weights.

PREREQUISITES (all local, all offline)
  1. The local Form kernel binary: form/form-kernel-go/bin-go
       Present already?  ->  nothing to do.
       Missing?          ->  built once from the local Go module cache (GOPROXY=off,
                             no network). Needs a Go toolchain installed.
  2. python3 (standard library only — used for JSON file IO, no pip installs).
  3. Your corpus already on disk, as JSONL — one object per line with a "task"
     field (the NL input) and "steps" (the target signal). Optionally each row
     carries "license" or "provenance"; untagged rows take --default-license.

YOUR CORPUS, TAGGING PROVENANCE
  Add a "license" field to each row to declare what you may train on, e.g.:
     {"license":"owned","task":"...","steps":[{"tool":"Read"}]}
     {"license":"copyright","task":"...","steps":[{"tool":"Edit"}]}
  Rows with no field are treated as --default-license; with no default they are
  "unknown" and routed to TEST-only (fail-closed). A row's own copyright tag always
  wins over the default.

THE THREE STEPS (offline)
  1) PARTITION the corpus into lawful-to-train vs test-only:
       bash scripts/corpus_partition_by_license.sh <corpus.jsonl> --default-license owned
     → writes <stem>.train-eligible.jsonl and <stem>.eval-only.jsonl

  2) TRAIN on the lawful file ONLY; measure on the copyright (test-only) file:
       bash scripts/form_cli_transformer_train_wide.sh \
            <stem>.train-eligible.jsonl 60 200 <stem>.eval-only.jsonl
     → reports train loss, held-out loss (generalisation within lawful data), and
       a separate "copyright TEST" loss — measured, NEVER trained.

  3) (inference) Translate NL→NL by nearest meaning over the corpus faces:
       form/form-stdlib/translation-engine.fk  (te-translate), corpus passed as data.

  Or do steps 1–2 in one command:
       bash scripts/offline_nl_training_runbook.sh run <corpus.jsonl> \
            --default-license owned --epochs 60 --cap 200 [--eval <copyright.jsonl>]

READING THE OUTPUT
  train loss falling      → the model is learning the lawful signal
  held-out loss falling   → it generalises to unseen lawful turns (not memorising)
  copyright TEST loss      → how the lawfully-trained model does on copyright text,
                            measured without ever training on it

PROOF
  The lawful/test decision is form-stdlib/corpus-license-gate.fk, proven FOUR-WAY
  (Go=Rust=TS=fkwu → 31). Re-verify offline any time:
       cd form && ./validate.sh form-stdlib/core.fk \
            form-stdlib/corpus-license-gate.fk form-stdlib/tests/corpus-license-gate-band.fk
────────────────────────────────────────────────────────────────────────────
TXT
}

ensure_kernel() {
  if [[ ! -x "$GO" ]]; then
    echo "kernel binary missing — building offline from the local Go module cache (no network)..."
    ( cd "$ROOT/form/form-kernel-go" && GOPROXY=off go build -o bin-go . ) \
      || { echo "OFFLINE BUILD FAILED — the Go module cache is incomplete. Build once on a"
           echo "machine with the cache populated, or copy form/form-kernel-go/bin-go over."; return 1; }
  fi
  return 0
}

cmd_check() {
  local ok=0
  echo "── offline prerequisite check ──"
  if [[ -x "$GO" ]]; then echo "  [ok]   Form kernel binary: $GO"
  elif command -v go >/dev/null 2>&1; then echo "  [warn] kernel binary absent; Go toolchain present — will build offline on first run"
  else echo "  [MISS] no kernel binary and no Go toolchain — cannot run"; ok=1; fi
  if command -v python3 >/dev/null 2>&1; then echo "  [ok]   python3: $(command -v python3)"
  else echo "  [MISS] python3 not found"; ok=1; fi
  [[ -x "$PART" && -x "$TRAIN" ]] && echo "  [ok]   carriers present" || echo "  [warn] carrier scripts not executable (run: chmod +x scripts/*.sh)"
  echo "  [ok]   no network is used by any step"
  [[ $ok -eq 0 ]] && echo "→ ready to train offline." || echo "→ resolve the [MISS] items above."
  return $ok
}

cmd_run() {
  local corpus="${1:-}"; shift || true
  [[ -n "$corpus" && -f "$corpus" ]] || { echo "usage: offline_nl_training_runbook.sh run <corpus.jsonl> [--default-license tag] [--epochs N] [--cap N] [--eval <copyright.jsonl>]"; return 1; }
  local def="owned" epochs="60" cap="200" evalc=""
  while [[ $# -gt 0 ]]; do case "$1" in
    --default-license) def="$2"; shift 2 ;;
    --epochs) epochs="$2"; shift 2 ;;
    --cap) cap="$2"; shift 2 ;;
    --eval) evalc="$2"; shift 2 ;;
    *) echo "unknown option: $1"; return 2 ;;
  esac; done
  ensure_kernel || return 1

  echo "### step 1/2 — partition by provenance (lawful vs test-only) ###"
  bash "$PART" "$corpus" --default-license "$def" || return 1
  local stem; stem="$(dirname "$corpus")/$(basename "${corpus%.jsonl}")"
  local train_file="$stem.train-eligible.jsonl" eval_file="$stem.eval-only.jsonl"
  [[ -s "$train_file" ]] || { echo "no lawful (train-eligible) rows — nothing to train on. Tag rows with a lawful license or set --default-license."; return 1; }
  # the copyright test set: an explicit --eval corpus wins; else the copyright rows
  # the gate routed out of this corpus (if any).
  local test_file=""
  if [[ -n "$evalc" && -f "$evalc" ]]; then test_file="$evalc"
  elif [[ -s "$eval_file" ]]; then test_file="$eval_file"; fi

  echo; echo "### step 2/2 — train on lawful data, measure on copyright test set ###"
  bash "$TRAIN" "$train_file" "$epochs" "$cap" "$test_file"
}

case "${1:-help}" in
  help|-h|--help|"") print_help ;;
  check) cmd_check ;;
  run)   shift; cmd_run "$@" ;;
  *) echo "unknown command: $1"; echo "try: help | check | run"; exit 2 ;;
esac
