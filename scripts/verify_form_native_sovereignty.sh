#!/usr/bin/env bash
# verify_form_native_sovereignty.sh — standard-receipt validation on c-bootstrap fkwu
# form-cli with native JIT. The RECEIPT phase runs with no go/rust/clang on PATH.
#
# Uses committed bootstrap C (no Go emit) + warmed binaries. Clang only when
# SOVEREIGNTY_ALLOW_BOOTSTRAP=1 compiles a missing cache entry.
#
# Usage:
#   ./scripts/verify_form_native_sovereignty.sh
#   SOVEREIGNTY_ALLOW_BOOTSTRAP=1 ./scripts/verify_form_native_sovereignty.sh  # first warm
#
# Exit 0 = receipt observed on this host. Exit 1 = failure with stderr detail.
set -euo pipefail
ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"
CLI="$FORM/form-cli"
fail() { echo "FAIL: $1" >&2; exit 1; }
note() { echo "  $1" >&2; }

# Receipt PATH: keep system utilities; hide rented toolchains from subprocesses.
receipt_path() {
  local p="/usr/bin:/bin:/usr/sbin:/sbin"
  command -v dirname >/dev/null 2>&1 && p="$(dirname "$CLI"):$p"
  printf '%s' "$p"
}

run_cli() {
  env PATH="$(receipt_path)" "$CLI" <<< "$1" 2>/dev/null | head -1 | tr -d '\r'
}

# ── Phase A: use warmed c-bootstrap form-cli (build only when missing) ────────
if [[ ! -x "$CLI" ]]; then
  note "bootstrap: form-cli absent — install from platform bootstrap (no clang)..."
  (cd "$FORM" && FORM_STANDARD_LANE=1 ./build-form-cli.sh) || {
    if [[ "${SOVEREIGNTY_ALLOW_BOOTSTRAP:-0}" == 1 ]]; then
      note "fallback: clang link from bootstrap C..."
      command -v clang >/dev/null 2>&1 || fail "clang required when platform bootstrap missing"
      (cd "$FORM" && ./build-form-cli.sh)
    else
      fail "form-cli missing — run ensure_form_cli_native.sh or add bootstrap/form-cli-<platform>"
    fi
  }
fi

[[ -x "$CLI" ]] || fail "form-cli missing at $CLI"

# ── Phase B: receipt — toolchain-free runtime ────────────────────────────
note "receipt: validating form-cli + fkwu (no go/rust/clang on PATH)..."

for bin in go rustc rust clang clang++ cargo; do
  if command -v "$bin" >/dev/null 2>&1; then
    note "hiding $bin from receipt PATH ($(command -v "$bin"))"
  fi
done

ping_out="$(run_cli ping)"
[[ "$ping_out" == "pong" ]] || fail "form-cli ping expected pong, got: $ping_out"

verify_out="$(run_cli verify)"
[[ "$verify_out" == *coherent* ]] || fail "form-cli verify not coherent: $verify_out"

fnri_out="$(run_cli fnri)"
[[ "$fnri_out" == *runtime=fkwu* ]] || fail "fnri runtime: $fnri_out"
[[ "$fnri_out" == *no-go=1* ]] || fail "fnri no-go flag: $fnri_out"

know_out="$(run_cli "fnri standard-receipt")"
[[ "$know_out" == *standard-receipt* ]] || fail "fnri knowledge: $know_out"
[[ "$know_out" == *docs/coherence-substrate/standard-receipt.form* ]] || fail "fnri path: $know_out"

resolve_out="$(run_cli "fnri resolve macos-arm64 host:process")"
[[ "$resolve_out" == "HostProcess" ]] || fail "fnri resolve: $resolve_out"

diag_out="$(run_cli diagnose)"
[[ "$diag_out" == *fkwu* ]] || fail "diagnose missing fkwu stats: $diag_out"

# fkwu band witness via selfhost flatten table (cached universal walker — same
# engine as form-cli, table entry instead of baked REPL program).
cd "$FORM"
# shellcheck source=scripts/fourth-arm.sh
source scripts/fourth-arm.sh

# Prefer the content-stamped cache; only invoke go+clang build when absent.
stamp="$(fourth_fkwu_cache_stamp)"
cached_fkwu="$FOURTH_DIR/fkwu-$stamp"
if [[ -x "$cached_fkwu" ]]; then
  FKWU="$cached_fkwu"
else
  note "bootstrap: fkwu cache miss — install from platform bootstrap..."
  FORM_STANDARD_LANE=1 build_fourth
  if ! fourth_available; then
    if [[ "${SOVEREIGNTY_ALLOW_BOOTSTRAP:-0}" == 1 ]]; then
      note "fallback: clang link from bootstrap uni.c..."
      FORM_STANDARD_LANE=0 build_fourth
    else
      fail "fkwu cache missing — add bootstrap/fkwu-<platform> or SOVEREIGNTY_ALLOW_BOOTSTRAP=1"
    fi
  fi
fi
fourth_available || fail "fkwu binary did not build"
fourth_selfhost || fail "T_flat selfhost unavailable — need fkc-table-serialize + fourth-flatten-table.txt"

stem="form-native-resource-interfaces"
exp="$(awk -v b="$stem" '$1==b{print $3; exit}' fourth-arm-bands.txt)"
[[ -n "$exp" ]] || fail "$stem not in fourth-arm-bands.txt"

rm -f "$FOURTH_DIR/t-${stem}-"*.txt 2>/dev/null || true
table="$(fourth_table "$stem")"
[[ -s "$table" ]] || fail "empty flatten table for $stem"

witness="$(env PATH="$(receipt_path)" "$FKWU" "$table" 0 2>/dev/null | head -1 | tr -d '[:space:]')"
[[ "$witness" == "$exp" ]] || fail "fkwu $stem witness $witness != expected $exp"

# fs-list sanity (selfhost flatten smoke — host-io on fkwu)
rm -f "$FOURTH_DIR/t-fs-list-"*.txt 2>/dev/null || true
fs_table="$(fourth_table fs-list)"
fs_exp="$(awk '$1=="fs-list"{print $3; exit}' fourth-arm-bands.txt)"
fs_wit="$(env PATH="$(receipt_path)" "$FKWU" "$fs_table" 0 2>/dev/null | head -1 | tr -d '[:space:]')"
[[ "$fs_wit" == "$fs_exp" ]] || fail "fkwu fs-list witness $fs_wit != $fs_exp"

printf '{"status":"pass","receipt":"toolchain-free","form_cli":"%s","fkwu":"%s","witnesses":{"%s":%s,"fs-list":%s}}\n' \
  "$CLI" "$FKWU" "$stem" "$witness" "$fs_wit"
note "PASS: c-bootstrap form-cli + fkwu selfhost flatten — receipt observed (no go/rust/clang in loop)"
