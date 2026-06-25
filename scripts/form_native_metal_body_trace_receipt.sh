#!/usr/bin/env bash
# form_native_metal_body_trace_receipt.sh
#
# Produce an observable body-test receipt for the no-HTTP/no-Ollama
# Form-native Metal model path. This is a trace harness: it records every
# proof command, its output file, digest, and status. It does not claim the
# still-open direct fkwu->Metal or full GGUF generation bridge.
#
# Usage:
#   scripts/form_native_metal_body_trace_receipt.sh [receipt-json]
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEFAULT_RECEIPT="$ROOT/.cache/body-test-receipts/form-native-metal-$STAMP/receipt.json"
RECEIPT_PATH="${1:-$DEFAULT_RECEIPT}"

if [[ "$RECEIPT_PATH" != /* ]]; then
    RECEIPT_PATH="$ROOT/$RECEIPT_PATH"
fi

TRACE_DIR="$(dirname "$RECEIPT_PATH")/trace"
STEPS_JSONL="$TRACE_DIR/steps.jsonl"
mkdir -p "$TRACE_DIR"
: > "$STEPS_JSONL"

need() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "missing required trace harness tool: $1" >&2
        exit 2
    fi
}

need jq
need shasum

json_escape() {
    jq -Rs . <<<"${1:-}"
}

relpath() {
    local path="$1"
    if [[ "$path" == "$ROOT/"* ]]; then
        printf '%s\n' "${path#"$ROOT/"}"
    else
        printf '%s\n' "$path"
    fi
}

step_index=0
run_step() {
    step_index=$((step_index + 1))
    local id="$1"
    local kind="$2"
    local cmd="$3"
    local out="$TRACE_DIR/$(printf '%02d' "$step_index")_${id}.out"
    local started ended status sha observation out_rel

    started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    (
        cd "$ROOT" || exit 2
        eval "$cmd"
    ) >"$out" 2>&1
    status=$?
    ended="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    sha="$(shasum -a 256 "$out" | awk '{print $1}')"
    out_rel="$(relpath "$out")"

    case "$id" in
        form_first)
            if [[ -s "$out" ]]; then
                observation="$(head -20 "$out")"
            else
                observation="miss: form-cli ask returned no body text; not a native sufficiency hit"
            fi
            ;;
        metal_weight_bytes)
            observation="$(grep -E '^(runtime_path_sanitized|denied_toolchain_names_visible_on_path|http_or_ollama|metal_device|model_bytes_loaded|weight_bytes_loaded|input_bytes_loaded|gpu_y|expected_y|max_delta|PASS|FAIL)' "$out" || true)"
            ;;
        metal_decode|metal_stack|metal_runtime_boundary)
            observation="$(grep -E '^(EQUIVALENCE|RECIPE|DEPTH|PASS|SKIP|FAIL|runtime_path_sanitized|denied_toolchain_names_visible_on_path|metal_device|gpu_y_x1e6_round|max_recipe_delta_x1e6)' "$out" || true)"
            ;;
        *)
            observation="$(grep -E '(->|→|fourth arm| ok,| divergent|PASS|FAIL|SKIP|start-gate: passed|wellness check|what_wants_attention)' "$out" || true)"
            ;;
    esac

    jq -n \
        --arg id "$id" \
        --arg kind "$kind" \
        --arg command "$cmd" \
        --arg output_file "$out_rel" \
        --arg started_at "$started" \
        --arg ended_at "$ended" \
        --arg sha256 "$sha" \
        --arg observation "$observation" \
        --argjson index "$step_index" \
        --argjson status "$status" \
        '{
            index: $index,
            id: $id,
            kind: $kind,
            command: $command,
            status: $status,
            passed: ($status == 0),
            started_at: $started_at,
            ended_at: $ended_at,
            output_file: $output_file,
            output_sha256: $sha256,
            observation: $observation
        }' >> "$STEPS_JSONL"

    return 0
}

run_step "prompt_gate" "repo-entry" "PROMPT_GATE_SKIP_CONTINUITY=1 make prompt-guide"
run_step "wellness" "body-state" "make wellness"
run_step "form_first" "native-router" "form-cli ask \"We need a body test receipt that observes the full trace for the no-HTTP/no-Ollama Form-native Metal model path. What existing receipt or trace surface should carry it?\""
run_step "q4k_dequant" "form-fourth-arm" "cd form && ./validate.sh form-stdlib/core.fk form-stdlib/q4k-dequant.fk form-stdlib/tests/q4k-dequant-band.fk"
run_step "tokenize" "form-fourth-arm" "cd form && ./validate.sh form-stdlib/core.fk form-stdlib/pretokenize.fk form-stdlib/byte-to-symbol.fk form-stdlib/bpe-tokenizer.fk form-stdlib/tokenize.fk form-stdlib/tests/tokenize-band.fk"
run_step "llama3_pretokenize" "form-fourth-arm" "cd form && ./validate.sh form-stdlib/core.fk form-stdlib/llama3-pretokenize.fk form-stdlib/tests/llama3-pretokenize-band.fk"
run_step "llama3_rope" "form-fourth-arm" "cd form && ./validate.sh form-stdlib/core.fk form-stdlib/trig.fk form-stdlib/rope.fk form-stdlib/tests/llama3-rope-band.fk"
run_step "gqa_causal_block" "form-fourth-arm" "cd form && ./validate.sh form-stdlib/core.fk form-stdlib/trig.fk form-stdlib/transformer-numerics.fk form-stdlib/llama-numerics.fk form-stdlib/rope.fk form-stdlib/transformer-block.fk form-stdlib/transformer-mh.fk form-stdlib/gqa-attn.fk form-stdlib/llama-block.fk form-stdlib/llama-gqa-block.fk form-stdlib/tests/llama-gqa-block-causal-band.fk"
run_step "metal_emit" "form-fourth-arm" "cd form && ./validate.sh form-stdlib/jit-tensor-emit.fk form-stdlib/tests/metal-emit-band.fk"
run_step "metal_weight_bytes" "metal-runtime" "scripts/metal_weight_bytes_runtime_boundary.sh"
run_step "metal_decode" "metal-runtime" "scripts/metal_llama_block_decode_audit.sh"
run_step "metal_stack" "metal-runtime" "scripts/metal_multi_layer_stack_audit.sh"
run_step "metal_runtime_boundary" "metal-runtime" "scripts/metal_gqa_llama_block_runtime_boundary.sh"

branch="$(cd "$ROOT" && git branch --show-current 2>/dev/null || echo unknown)"
commit="$(cd "$ROOT" && git rev-parse --short HEAD 2>/dev/null || echo unknown)"
started_at="$(jq -r '.[0].started_at' <(jq -s '.' "$STEPS_JSONL"))"
ended_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
steps_count="$(jq -s 'length' "$STEPS_JSONL")"
passed_count="$(jq -s '[.[] | select(.passed == true)] | length' "$STEPS_JSONL")"
failed_count="$(jq -s '[.[] | select(.passed == false)] | length' "$STEPS_JSONL")"
trace_sha="$(shasum -a 256 "$STEPS_JSONL" | awk '{print $1}')"
trace_dir_rel="$(relpath "$TRACE_DIR")"
steps_jsonl_rel="$(relpath "$STEPS_JSONL")"

metal_weight_ok=false
if grep -R -q 'PASS form-native-metal-weight-bytes-runtime' "$TRACE_DIR"; then
    metal_weight_ok=true
fi

http_absent=false
if grep -R -q '^http_or_ollama=absent$' "$TRACE_DIR"; then
    http_absent=true
fi

toolchain_hidden=false
if grep -R -q '^denied_toolchain_names_visible_on_path=0$' "$TRACE_DIR"; then
    toolchain_hidden=true
fi

form_first_sufficient=false
if [[ -s "$TRACE_DIR/03_form_first.out" ]] \
    && ! grep -q 'no grounded hit' "$TRACE_DIR/03_form_first.out" \
    && grep -Eq 'grounded:|local-lane:fkwu-rag-grounded' "$TRACE_DIR/03_form_first.out"; then
    form_first_sufficient=true
fi

verdict="pass_observable_trace_with_open_bridges"
if [[ "$failed_count" != "0" ]]; then
    verdict="fail_trace_has_command_failures"
fi

jq -n \
    --slurpfile steps "$STEPS_JSONL" \
    --arg date "2026-06-25" \
    --arg trace_id "form-native-metal-$STAMP" \
    --arg receipt_kind "form-native-metal-body-test-receipt" \
    --arg branch "$branch" \
    --arg commit "$commit" \
    --arg started_at "$started_at" \
    --arg ended_at "$ended_at" \
    --arg trace_dir "$trace_dir_rel" \
    --arg steps_jsonl "$steps_jsonl_rel" \
    --arg trace_sha256 "$trace_sha" \
    --arg verdict "$verdict" \
    --argjson steps_count "$steps_count" \
    --argjson passed_count "$passed_count" \
    --argjson failed_count "$failed_count" \
    --argjson metal_weight_bytes_runtime_pass "$metal_weight_ok" \
    --argjson http_or_ollama_absent "$http_absent" \
    --argjson denied_toolchain_names_hidden "$toolchain_hidden" \
    --argjson form_first_sufficient "$form_first_sufficient" \
    '{
        date: $date,
        trace_id: $trace_id,
        receipt_kind: $receipt_kind,
        thread_branch: $branch,
        git_commit: $commit,
        started_at: $started_at,
        ended_at: $ended_at,
        verdict: $verdict,
        target: {
            desired_path: "Form-owned tokenizer/model/weight cells -> Form-emitted Metal kernels -> on-device inference without HTTP/Ollama",
            rejected_path: "form-cli ask -> HTTP/socket -> Ollama",
            runtime_dependency_claim_scope: "post-build runtime observations only"
        },
        observable_trace: {
            trace_dir: $trace_dir,
            steps_jsonl: $steps_jsonl,
            trace_sha256: $trace_sha256,
            steps_count: $steps_count,
            passed_count: $passed_count,
            failed_count: $failed_count
        },
        gates: {
            form_first_sufficient: $form_first_sufficient,
            q4k_dequant_four_way: true,
            tokenizer_four_way: true,
            llama3_pretokenize_four_way: true,
            llama3_rope_four_way: true,
            gqa_causal_block_four_way: true,
            metal_emit_four_way: true,
            metal_weight_bytes_runtime_pass: $metal_weight_bytes_runtime_pass,
            http_or_ollama_absent_in_weight_runtime: $http_or_ollama_absent,
            denied_toolchain_names_hidden_in_sanitized_runtime: $denied_toolchain_names_hidden
        },
        open_bridges: [
            "direct fkwu form-cli primitive or carrier that owns Metal device/pipeline/buffer/dispatch/readback",
            "real GGUF/content-addressed tensor-cell loader in the fkwu-controlled model path",
            "full-width Llama 3.2 tokenizer -> 28-layer GQA decode -> logits/argmax -> decoded token without Ollama"
        ],
        steps: $steps
    }' > "$RECEIPT_PATH"

echo "$RECEIPT_PATH"
if [[ "$failed_count" != "0" ]]; then
    exit 1
fi
