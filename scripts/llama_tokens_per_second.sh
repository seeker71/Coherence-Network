#!/usr/bin/env bash
# llama_tokens_per_second.sh — a real HuggingFace model served by the recipe.
#
# The Llama-2 architecture lives as recipe data (transformer-kernel.fk
# tk-emit-llama); this instrument projects it to C through the kernel,
# compiles it, loads the real karpathy/tinyllamas stories15M checkpoint
# (60MB float32, HuggingFace) and llama2.c tokenizer, generates greedy
# tokens from BOS, and reports tokens/sec — scalar and native-vector.
#
# The correctness witness is legible: greedy decoding of real weights
# must produce the canonical "Once upon a time, there was a little girl
# named Lily" opening — random or broken weights cannot fake coherent
# English. tok/s is reported for the scalar build (the deterministic
# shape) and the -march=native -ffast-math build (the vector headroom).
#
# Run:  scripts/llama_tokens_per_second.sh [steps]
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMDIR="$ROOT/form"
GO_BIN="$FORMDIR/form-kernel-go/bin-go"
CLANG="${CLANG:-clang}"
STEPS="${1:-100}"
CACHE="${TK_MODEL_CACHE:-/tmp/hf}"

if [[ ! -x "$GO_BIN" ]]; then
    echo "  building go kernel..." >&2
    (cd "$FORMDIR/form-kernel-go" && go build -o bin-go .)
fi

mkdir -p "$CACHE"
if [[ ! -s "$CACHE/stories15M.bin" ]]; then
    echo "  fetching stories15M.bin from HuggingFace..." >&2
    curl -sL --max-time 300 -o "$CACHE/stories15M.bin" \
        https://huggingface.co/karpathy/tinyllamas/resolve/main/stories15M.bin || true
fi
if [[ ! -s "$CACHE/tokenizer.bin" ]]; then
    echo "  fetching tokenizer.bin..." >&2
    curl -sL --max-time 60 -o "$CACHE/tokenizer.bin" \
        https://github.com/karpathy/llama2.c/raw/master/tokenizer.bin || true
fi
if [[ ! -s "$CACHE/stories15M.bin" || ! -s "$CACHE/tokenizer.bin" ]]; then
    echo "SKIP  model or tokenizer unreachable (network) — nothing measured"; exit 0
fi

work="$(mktemp -d "${TMPDIR:-/tmp}/form-llama.XXXXXX")"
trap 'rm -rf "$work"' EXIT

cat > "$work/driver.fk" <<'EOF'
(do (print (tk-emit-llama)) 0)
EOF
(cd "$FORMDIR" && "$GO_BIN" form-stdlib/transformer-kernel.fk "$work/driver.fk" 2>/dev/null) \
    | sed '$d' > "$work/llama.c"
if ! grep -q 'rmsnorm' "$work/llama.c"; then
    echo "FAIL  projection: tk-emit-llama did not emit the engine"; exit 1
fi

fails=0
run_variant() {
    local label="$1"; shift
    if ! "$CLANG" "$@" -o "$work/llama-$label" "$work/llama.c" -lm 2>"$work/cc.err"; then
        echo "FAIL  $label build:"; head -3 "$work/cc.err"; fails=1; return
    fi
    local out text perf
    out="$(cd "$CACHE" && "$work/llama-$label" stories15M.bin tokenizer.bin "$STEPS")"
    text="$(printf '%s\n' "$out" | head -1 | cut -c1-60)"
    perf="$(printf '%s\n' "$out" | tail -1)"
    if printf '%s' "$out" | grep -q "Once upon a time"; then
        echo "PASS  $label: real weights speak —$text..."
        echo "      $perf"
    else
        echo "FAIL  $label: greedy text is not the canonical opening:"; echo "      $text"; fails=1
    fi
}
echo "stories15M (HuggingFace, 15M params, f32) through the recipe-projected engine:"
run_variant scalar -O3
run_variant native -O3 -march=native -ffast-math

exit $fails
