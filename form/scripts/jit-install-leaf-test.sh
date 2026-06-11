#!/usr/bin/env bash
#
# jit-install-leaf-test.sh - live witness that the Go kernel's JIT lane
# installs a compiled artifact as a NAMED callable at runtime
# (install-as-named-callable-leaf; protocol: form-stdlib/install-leaf.fk,
# proven three-way by tests/install-leaf-band.fk — this script witnesses
# the native carrier: recipe -> .so -> kernel's own native table -> call
# by name -> value parity vs the recipe walk).
#
# Requires the host Go toolchain (the JIT lane invokes
# `go build -buildmode=plugin`); exits SKIP when absent — the protocol
# band still proves the shape on all three kernels without it.
set -euo pipefail

FORMDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$FORMDIR"

if ! command -v go >/dev/null 2>&1; then
  echo "SKIP: host go toolchain not found - the JIT install carrier needs it." >&2
  exit 0
fi

GO_BIN="form-kernel-go/bin-go"
if [[ ! -x "$GO_BIN" ]] || find form-kernel-go -name '*.go' -newer "$GO_BIN" -print -quit | grep -q .; then
  echo "building go kernel..." >&2
  (cd form-kernel-go && go build -o bin-go .)
fi

DRIVER="$(mktemp "${TMPDIR:-/tmp}/jit-install-leaf.XXXXXX.fk")"
cleanup() { rm -f "$DRIVER"; }
trap cleanup EXIT

cat > "$DRIVER" <<'FK'
(do
    ;; a small pure capability — the recipe stays canonical truth
    (defn il-probe (a b) (add (mul a b) 7))
    (let walk-value (il-probe 6 7))

    ;; the install offer: jit the closure, bind the artifact under a NEW
    ;; name in the kernel's own native table — ack is the body NodeID
    (let ack (jit_install "il-probe" "il-probe-native" 2))
    (let c0 (if (str_eq (value_kind ack) "node_id") 1 0))
    (let c1 (if (eq (installed_leaf? "il-probe-native") 1) 1 0))

    ;; a call BY NAME reaches the artifact: no closure binding exists
    ;; under this name — only the installed leaf can answer it
    (let c2 (if (eq (il-probe-native 6 7) walk-value) 1 0))

    ;; the float lane of the same leaf agrees with the recipe walk
    (let c3 (if (eq (round (mul (il-probe-native 2.5 4.0) 10.0))
                    (round (mul (il-probe 2.5 4.0) 10.0)))
                1 0))

    ;; collision: the bound name refuses a rebind (first-bind-wins)
    (let c4 (if (eq (jit_install "il-probe" "il-probe-native" 2) 0) 1 0))

    ;; collision with a build-time native refuses the same way
    (let c5 (if (eq (jit_install "il-probe" "str_len" 2) 0) 1 0))

    ;; interface mismatch: arity 3 is not the closure's own — refused,
    ;; and nothing landed in the table
    (let c6 (if (eq (jit_install "il-probe" "il-probe-native-3" 3) 0) 1 0))
    (let c7 (if (eq (installed_leaf? "il-probe-native-3") 0) 1 0))

    ;; no cell to install acknowledges nothing
    (let c8 (if (str_eq (value_kind (jit_install "no-such-fn" "x-leaf" 1)) "null") 1 0))

    ;; a call outside the offered interface acknowledges nothing
    (let c9 (if (str_eq (value_kind (il-probe-native 1 2 3)) "null") 1 0))

    (add c0 (add c1 (add c2 (add c3 (add c4 (add c5 (add c6 (add c7 (add c8 c9))))))))))
FK

OUT="$("$GO_BIN" "$DRIVER" 2>&1 | tail -1)"
echo "verdict: $OUT"
if [[ "$OUT" == "10" ]]; then
  echo "jit install leaf: PASS - a jitted artifact installed as a named callable in the kernel's own table at runtime; call-by-name reached it with value parity (int + float lanes); collision, interface mismatch, and absent-cell offers refused honestly."
  exit 0
else
  echo "jit install leaf: FAIL - expected verdict 10." >&2
  exit 1
fi
