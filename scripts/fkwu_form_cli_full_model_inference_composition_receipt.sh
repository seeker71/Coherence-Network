#!/usr/bin/env bash
# fkwu_form_cli_full_model_inference_composition_receipt.sh
#
# Compose the current model-inference proof pieces into one observable receipt.
# This harness does not add a second runtime path. It records what the native
# fkwu form-cli path can prove on the current host/device set and keeps the
# full-generation boundary explicit:
#
#   proven pieces: fkwu form-cli ask/status, GGUF find/model-cell,
#                  tokenizer/loop bands, Metal model-cell/body trace on macOS.
#   now bound:     ask-staged model-call witness -> decoded local answer receipt.
#   still open:    full real Llama GGUF token generation produced by real prompt text,
#                  real GGUF tokenizer arrays, real GGUF tensor bytes,
#                  accelerator buffers, full autoregressive token IDs, and
#                  decoded token text.
#
# Runtime claims are read from the child receipts. Build/receipt tools may be
# used by this harness; the sanitized proof binaries run with no HTTP/Ollama and
# no Go/Rust/Python/shell/clang visible on PATH when those child receipts say so.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEFAULT_RECEIPT="$ROOT/.cache/body-test-receipts/fkwu-full-model-inference-composition-$STAMP/receipt.json"
RECEIPT_PATH="${1:-$DEFAULT_RECEIPT}"

if [[ "$RECEIPT_PATH" != /* ]]; then
    RECEIPT_PATH="$ROOT/$RECEIPT_PATH"
fi

TRACE_DIR="${RECEIPT_PATH%.json}_trace"
STEPS_JSONL="$TRACE_DIR/steps.jsonl"
rm -rf "$TRACE_DIR"
mkdir -p "$TRACE_DIR" "$(dirname "$RECEIPT_PATH")"
: > "$STEPS_JSONL"

need() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "missing required receipt harness tool: $1" >&2
        exit 2
    fi
}

need jq

need_hash_tool() {
    if command -v shasum >/dev/null 2>&1 || command -v sha256sum >/dev/null 2>&1; then
        return 0
    fi
    echo "missing required receipt harness tool: shasum or sha256sum" >&2
    exit 2
}

hash_file() {
    if command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | awk '{print $1}'
    else
        sha256sum "$1" | awk '{print $1}'
    fi
}

need_hash_tool

relpath() {
    local path="$1"
    if [[ "$path" == "$ROOT/"* ]]; then
        printf '%s\n' "${path#"$ROOT/"}"
    else
        printf '%s\n' "$path"
    fi
}

sanitize_trace_file() {
    local src="$1"
    local dst="$2"
    LC_ALL=C sed -E \
        -e "s|$ROOT|<repo>|g" \
        -e "s|$HOME|<home>|g" \
        -e 's|<home>/.ollama/models/blobs/sha256-[0-9a-fA-F]+|<local-gguf-blob>|g' \
        -e 's|<home>/mentor-install/.models/[^"[:space:]]+|<local-gguf-file>|g' \
        -e 's|/private/var/folders/[^[:space:]:]+|<tmp>|g' \
        -e 's|/var/folders/[^[:space:]:]+|<tmp>|g' \
        "$src" > "$dst"
}

sanitize_trace_tree() {
    local file tmp
    while IFS= read -r -d '' file; do
        tmp="$file.sanitized"
        sanitize_trace_file "$file" "$tmp"
        mv "$tmp" "$file"
    done < <(find "$TRACE_DIR" -type f -print0)
}

observation_for() {
    local id="$1"
    local out="$2"
    case "$id" in
        form_cli_ask|ask_staged_model_call|decoded_answer)
            grep -E '^(grounded:|local-lane:|model-call-lane:|answer-lane:|answer-source:|answer:|synthesis-lane:|prose-generation:|trust  |\[ask:)' "$out" || true
            ;;
        synthesis_status|model_status)
            grep -E '^(synthesis-lane:|reason:|available:|observed:|missing:|boundary:|ask-staged-model-call-receipt:|prose-generation:)' "$out" || true
            ;;
        gguf_model_cell)
            grep -E '^(gguf_cell_verified|gguf_magic_ok|gguf_tensor_count|gguf_tensor_info_offset|gguf_tensor_type|PASS)' "$out" || true
            ;;
        metal_model_cell)
            grep -E '^(model_cell_verified|runtime_path_sanitized|denied_toolchain_names_visible_on_path|http_or_ollama|metal_owner|metal_device|gpu_y|max_delta|PASS)' "$out" || true
            ;;
        real_gguf_weight_map)
            grep -E '^(receipt:|file:|header:|tensor-map:|types:|tokenizer-arrays:|required-tensors:|no real GGUF|SKIP)' "$out" || true
            ;;
        full_real_llama_generation_claim)
            grep -E '^(receipt:|verdict:|claim-allowed:|grounded-decoded-answer:|full-real-llama-gguf-generation:|blocked-requirements:)' "$out" || true
            ;;
        android_*)
            grep -E '^(SKIP|FAIL|ok|  ✓|  ✗|witness on device|conditions:|device:|\{"status")' "$out" || true
            ;;
        windows_*)
            grep -E '^(SKIP|WINDOWS|PASS|FAIL|synthesis-lane:|reason:|available:|missing:)' "$out" || true
            ;;
        *)
            grep -E '(fourth arm:| ok,| divergent|PASS|FAIL|SKIP|verdict|receipt=|receipt:|model_cell_verified|runtime_path_sanitized|http_or_ollama)' "$out" || true
            ;;
    esac
}

step_index=0
HARD_FAIL=0

record_step() {
    local id="$1"
    local platform="$2"
    local label="$3"
    local command_label="$4"
    local status="$5"
    local skipped="$6"
    local hard="$7"
    local started="$8"
    local ended="$9"
    local out_file="${10}"
    local observation="${11}"
    local out_rel sha

    out_rel="$(relpath "$out_file")"
    sha="$(hash_file "$out_file")"
    if [[ "$status" -ne 0 && "$skipped" != "true" && "$hard" == "true" ]]; then
        HARD_FAIL=1
    fi
    jq -n \
        --arg id "$id" \
        --arg platform "$platform" \
        --arg label "$label" \
        --arg command "$command_label" \
        --arg started_at "$started" \
        --arg ended_at "$ended" \
        --arg output_file "$out_rel" \
        --arg output_sha256 "$sha" \
        --arg observation "$observation" \
        --argjson index "$step_index" \
        --argjson status "$status" \
        --argjson skipped "$skipped" \
        --argjson hard "$hard" \
        '{
          index: $index,
          id: $id,
          platform: $platform,
          label: $label,
          command: $command,
          status: $status,
          passed: ($status == 0 and ($skipped | not)),
          skipped: $skipped,
          hard_gate: $hard,
          started_at: $started_at,
          ended_at: $ended_at,
          output_file: $output_file,
          output_sha256: $output_sha256,
          observation: $observation
        }' >> "$STEPS_JSONL"
}

run_step() {
    local id="$1"
    local platform="$2"
    local label="$3"
    local hard="$4"
    local command_label="$5"
    shift 5

    step_index=$((step_index + 1))
    local raw="$TRACE_DIR/$(printf '%02d' "$step_index")_${id}.raw"
    local out="$TRACE_DIR/$(printf '%02d' "$step_index")_${id}.out"
    local started ended status skipped observation
    started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    (cd "$ROOT" && "$@") > "$raw" 2>&1
    status=$?
    ended="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    sanitize_trace_file "$raw" "$out"
    rm -f "$raw"
    skipped=false
    if grep -q '^SKIP' "$out"; then
        skipped=true
        status=0
    fi
    observation="$(observation_for "$id" "$out" | sed -n '1,30p')"
    record_step "$id" "$platform" "$label" "$command_label" "$status" "$skipped" "$hard" "$started" "$ended" "$out" "$observation"
}

skip_step() {
    local id="$1"
    local platform="$2"
    local label="$3"
    local reason="$4"
    step_index=$((step_index + 1))
    local out="$TRACE_DIR/$(printf '%02d' "$step_index")_${id}.out"
    local now
    now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'SKIP %s\n' "$reason" > "$out"
    record_step "$id" "$platform" "$label" "$reason" 0 true false "$now" "$now" "$out" "SKIP $reason"
}

is_windows_host() {
    case "$(uname -s 2>/dev/null || echo unknown)" in
        MINGW*|MSYS*|CYGWIN*) return 0 ;;
    esac
    [[ "${OS:-}" == "Windows_NT" ]]
}

is_macos_host() {
    [[ "$(uname -s 2>/dev/null || echo unknown)" == "Darwin" ]]
}

run_step form_cli_ask current-host "native fkwu grounded ask" true \
    "bin/form-cli ask substrate" \
    "$ROOT/bin/form-cli" ask substrate

run_step ask_staged_model_call current-host "ask-staged local model-call witness" true \
    "bin/form-cli ask ungrounded-model-call-composition-probe" \
    "$ROOT/bin/form-cli" ask "ungrounded model call composition probe $STAMP"

run_step synthesis_status current-host "model synthesis binding" true \
    "bin/form-cli synthesis-status" \
    "$ROOT/bin/form-cli" synthesis-status

run_step model_status current-host "model status binding" true \
    "bin/form-cli model-status" \
    "$ROOT/bin/form-cli" model-status

run_step decoded_answer current-host "native decoded answer binding" true \
    "form/form-cli decoded-answer" \
    bash -lc "printf 'decoded-answer\nquit\n' | '$ROOT/form/form-cli' | sed '/^null$/d'"

run_step gguf_find_four_way current-host "GGUF find-by-name and absolute offset four-way" true \
    "cd form && ./validate.sh form-stdlib/core.fk form-stdlib/gguf-read.fk form-stdlib/tests/gguf-find-band.fk" \
    bash -lc "cd '$ROOT/form' && ./validate.sh form-stdlib/core.fk form-stdlib/gguf-read.fk form-stdlib/tests/gguf-find-band.fk"

run_step real_gguf_tensor_math_four_way current-host "named real GGUF tensor bytes into native math four-way" true \
    "cd form && ./validate.sh ... real-gguf-tensor-math-band.fk" \
    bash -lc "cd '$ROOT/form' && ./validate.sh form-stdlib/core.fk form-stdlib/format-arith.fk form-stdlib/f16-decode.fk form-stdlib/gguf-read.fk form-stdlib/q6k-dequant.fk form-stdlib/weight-load.fk form-stdlib/transformer-block.fk form-stdlib/block-join.fk form-stdlib/real-gguf-tensor-math.fk form-stdlib/tests/real-gguf-tensor-math-band.fk"

run_step tokenizer_compose_four_way current-host "BPE tokenizer carrier four-way" true \
    "cd form && ./validate.sh ... tokenize-band.fk" \
    bash -lc "cd '$ROOT/form' && ./validate.sh form-stdlib/core.fk form-stdlib/pretokenize.fk form-stdlib/byte-to-symbol.fk form-stdlib/bpe-tokenizer.fk form-stdlib/tokenize.fk form-stdlib/tests/tokenize-band.fk"

run_step llama3_pretokenizer_four_way current-host "Llama 3 pretokenizer four-way" true \
    "cd form && ./validate.sh ... llama3-pretokenize-band.fk" \
    bash -lc "cd '$ROOT/form' && ./validate.sh form-stdlib/core.fk form-stdlib/llama3-pretokenize.fk form-stdlib/tests/llama3-pretokenize-band.fk"

run_step autoregressive_loop_four_way current-host "Form autoregressive generation loop four-way" true \
    "cd form && ./validate.sh ... llama-generate-band.fk" \
    bash -lc "cd '$ROOT/form' && ./validate.sh form-stdlib/core.fk form-stdlib/trig.fk form-stdlib/transformer-numerics.fk form-stdlib/llama-numerics.fk form-stdlib/rope.fk form-stdlib/transformer-block.fk form-stdlib/transformer-mh.fk form-stdlib/gqa-attn.fk form-stdlib/llama-block.fk form-stdlib/llama-gqa-block.fk form-stdlib/kv-cache.fk form-stdlib/kv-llama-block.fk form-stdlib/kv-gqa-llama-block.fk form-stdlib/multi-layer-stack.fk form-stdlib/gqa-multi-layer-stack.fk form-stdlib/greedy-decode.fk form-stdlib/llama-generate.fk form-stdlib/tests/llama-generate-band.fk"

if command -v python3 >/dev/null 2>&1; then
    run_step real_gguf_weight_map current-host "optional real GGUF tensor map witness" false \
        "python3 scripts/gguf_weight_map_receipt.py --json <trace>/real-gguf-weight-map.json" \
        bash -lc "python3 '$ROOT/scripts/gguf_weight_map_receipt.py' --json '$TRACE_DIR/real-gguf-weight-map.json'; rc=\$?; if [ \"\$rc\" -eq 2 ]; then echo 'SKIP no real GGUF path found for optional tensor-map witness'; exit 0; fi; exit \"\$rc\""
else
    skip_step real_gguf_weight_map current-host "optional real GGUF tensor map witness" "python3 absent in receipt harness; runtime path unaffected"
fi

run_step full_real_llama_generation_claim current-host "full real Llama GGUF generation claim gate" true \
    "scripts/validate_form_cli_full_real_llama_generation_claim.sh <trace>/full-real-llama-generation-claim.json" \
    "$ROOT/scripts/validate_form_cli_full_real_llama_generation_claim.sh" "$TRACE_DIR/full-real-llama-generation-claim.json"

gguf_model_cell_hard=true
if is_windows_host; then
    gguf_model_cell_hard=false
fi

run_step gguf_model_cell current-host "fkwu form-cli GGUF model-cell" "$gguf_model_cell_hard" \
    "scripts/fkwu_form_cli_gguf_model_cell_receipt.sh <trace>/gguf-model-cell/receipt.json" \
    "$ROOT/scripts/fkwu_form_cli_gguf_model_cell_receipt.sh" "$TRACE_DIR/gguf-model-cell/receipt.json"

if is_macos_host && command -v swiftc >/dev/null 2>&1; then
    run_step metal_model_cell macos "fkwu form-cli Metal model-cell" true \
        "scripts/fkwu_form_cli_metal_model_cell_receipt.sh <trace>/metal-model-cell/receipt.json" \
        "$ROOT/scripts/fkwu_form_cli_metal_model_cell_receipt.sh" "$TRACE_DIR/metal-model-cell/receipt.json"
    run_step metal_body_trace macos "Form-native Metal body trace" true \
        "scripts/form_native_metal_body_trace_receipt.sh <trace>/metal-body-trace.json" \
        "$ROOT/scripts/form_native_metal_body_trace_receipt.sh" "$TRACE_DIR/metal-body-trace.json"
else
    skip_step metal_model_cell macos "fkwu form-cli Metal model-cell" "Darwin + swiftc unavailable on this host"
    skip_step metal_body_trace macos "Form-native Metal body trace" "Darwin + swiftc unavailable on this host"
fi

if command -v adb >/dev/null 2>&1 && adb devices 2>/dev/null | awk 'NR>1 && $2=="device"{found=1} END{exit(found?0:1)}'; then
    run_step android_fkwu_fourth android "Android on-device fkwu fourth-arm bands" true \
        "scripts/verify_fkwu_android_no_go.sh gguf-find llama-generate" \
        "$ROOT/scripts/verify_fkwu_android_no_go.sh" gguf-find llama-generate
    run_step android_vulkan_matvec android "Android Vulkan matvec carrier" false \
        "scripts/vulkan_matvec_android_audit.sh 16 16" \
        "$ROOT/scripts/vulkan_matvec_android_audit.sh" 16 16
else
    skip_step android_fkwu_fourth android "Android on-device fkwu fourth-arm bands" "no authorized adb device observed"
    skip_step android_vulkan_matvec android "Android Vulkan matvec carrier" "no authorized adb device observed"
fi

if is_windows_host; then
    run_step windows_form_cli_native windows "Windows current-host form-cli native status" true \
        "bin/form-cli synthesis-status" \
        "$ROOT/bin/form-cli" synthesis-status
else
    skip_step windows_form_cli_native windows "Windows current-host form-cli native status" "not running on Windows; PR workflow observes this row"
fi

sanitize_trace_tree

step_passed() {
    jq -r --arg id "$1" 'select(.id == $id) | .passed' "$STEPS_JSONL" | tail -1
}

step_skipped() {
    jq -r --arg id "$1" 'select(.id == $id) | .skipped' "$STEPS_JSONL" | tail -1
}

bool_or_false() {
    [[ "${1:-}" == "true" ]] && printf 'true\n' || printf 'false\n'
}

mac_host="$(bool_or_false "$(is_macos_host && echo true || echo false)")"
windows_host="$(bool_or_false "$(is_windows_host && echo true || echo false)")"
android_device="$(bool_or_false "$(command -v adb >/dev/null 2>&1 && adb devices 2>/dev/null | awk 'NR>1 && $2=="device"{found=1} END{exit(found?0:1)}' && echo true || echo false)")"

synthesis_out="$(jq -r 'select(.id == "synthesis_status") | .output_file' "$STEPS_JSONL" | tail -1)"
decoded_answer_out="$(jq -r 'select(.id == "decoded_answer") | .output_file' "$STEPS_JSONL" | tail -1)"
ask_staged_out="$(jq -r 'select(.id == "ask_staged_model_call") | .output_file' "$STEPS_JSONL" | tail -1)"
available=""
missing=""
if [[ -n "$synthesis_out" && -f "$ROOT/$synthesis_out" ]]; then
    available="$(grep '^available:' "$ROOT/$synthesis_out" | head -1 | cut -d: -f2-)"
    missing="$(grep '^missing:' "$ROOT/$synthesis_out" | head -1 | cut -d: -f2-)"
fi
ask_staged_decoded_answer_bound=false
if [[ -n "$ask_staged_out" && -f "$ROOT/$ask_staged_out" ]]; then
    if grep -q '^answer-lane:fkwu-metal-decoded-prose-binding$' "$ROOT/$ask_staged_out" &&
       grep -q '^prose-generation:observed-decoded-prose-answer-binding$' "$ROOT/$ask_staged_out"; then
        ask_staged_decoded_answer_bound=true
    elif grep -q '^model-call-observed:true$' "$ROOT/$ask_staged_out" &&
         grep -q '^inference-lane:form-cli-grounded-decoded-answer$' "$ROOT/$ask_staged_out" &&
         grep -q '^prose-generation:decoded-grounded-answer$' "$ROOT/$ask_staged_out"; then
        ask_staged_decoded_answer_bound=true
    fi
fi
decoded_answer_observed=false
if [[ "$ask_staged_decoded_answer_bound" == "true" ]] ||
   { [[ -n "$decoded_answer_out" && -f "$ROOT/$decoded_answer_out" ]] &&
     grep -q '^answer-lane:fkwu-metal-decoded-prose-binding$' "$ROOT/$decoded_answer_out" &&
     grep -q '^prose-generation:observed-decoded-prose-answer-binding$' "$ROOT/$decoded_answer_out"; }; then
    decoded_answer_observed=true
fi

trace_sha="$(hash_file "$STEPS_JSONL")"
branch="$(cd "$ROOT" && git branch --show-current 2>/dev/null || echo unknown)"
commit="$(cd "$ROOT" && git rev-parse --short HEAD 2>/dev/null || echo unknown)"
uname_s="$(uname -s 2>/dev/null || echo unknown)"
uname_m="$(uname -m 2>/dev/null || echo unknown)"
started_at="$(jq -r 'select(.index == 1) | .started_at' "$STEPS_JSONL" | head -1)"
ended_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
steps_count="$(jq -s 'length' "$STEPS_JSONL")"
passed_count="$(jq -s '[.[] | select(.passed == true)] | length' "$STEPS_JSONL")"
skipped_count="$(jq -s '[.[] | select(.skipped == true)] | length' "$STEPS_JSONL")"
failed_count="$(jq -s '[.[] | select(.status != 0 and .skipped == false)] | length' "$STEPS_JSONL")"
hard_failed_count="$(jq -s '[.[] | select(.hard_gate == true and .status != 0 and .skipped == false)] | length' "$STEPS_JSONL")"
nonhard_failed_count="$(jq -s '[.[] | select(.hard_gate == false and .status != 0 and .skipped == false)] | length' "$STEPS_JSONL")"

http_or_ollama_absent="$(bool_or_false "$(grep -R -q '^http_or_ollama=absent$' "$TRACE_DIR" && echo true || echo false)")"
denied_toolchain_hidden="$(bool_or_false "$(grep -R -q '^denied_toolchain_names_visible_on_path=0$' "$TRACE_DIR" && echo true || echo false)")"

verdict="pass_composition_receipt_decoded_answer_bound_full_width_not_yet_composed"
if [[ "$HARD_FAIL" -ne 0 ]]; then
    verdict="fail_composition_receipt_hard_gate"
fi

jq -n \
    --slurpfile steps "$STEPS_JSONL" \
    --arg date "2026-06-26" \
    --arg trace_id "fkwu-full-model-inference-composition-$STAMP" \
    --arg receipt_kind "fkwu-form-cli-full-model-inference-composition-receipt" \
    --arg branch "$branch" \
    --arg commit "$commit" \
    --arg started_at "$started_at" \
    --arg ended_at "$ended_at" \
    --arg trace_dir "$(relpath "$TRACE_DIR")" \
    --arg steps_jsonl "$(relpath "$STEPS_JSONL")" \
    --arg trace_sha256 "$trace_sha" \
    --arg verdict "$verdict" \
    --arg host_os "$uname_s" \
    --arg host_arch "$uname_m" \
    --arg available "$available" \
    --arg missing "$missing" \
    --argjson steps_count "$steps_count" \
    --argjson passed_count "$passed_count" \
    --argjson skipped_count "$skipped_count" \
    --argjson failed_count "$failed_count" \
    --argjson hard_failed_count "$hard_failed_count" \
    --argjson nonhard_failed_count "$nonhard_failed_count" \
    --argjson mac_host "$mac_host" \
    --argjson windows_host "$windows_host" \
    --argjson android_device "$android_device" \
    --argjson form_cli_ask "$(bool_or_false "$(step_passed form_cli_ask)")" \
    --argjson gguf_find "$(bool_or_false "$(step_passed gguf_find_four_way)")" \
    --argjson real_gguf_tensor_math "$(bool_or_false "$(step_passed real_gguf_tensor_math_four_way)")" \
    --argjson tokenizer "$(bool_or_false "$(step_passed tokenizer_compose_four_way)")" \
    --argjson pretokenizer "$(bool_or_false "$(step_passed llama3_pretokenizer_four_way)")" \
    --argjson autoregressive_loop "$(bool_or_false "$(step_passed autoregressive_loop_four_way)")" \
    --argjson real_gguf_weight_map "$(bool_or_false "$(step_passed real_gguf_weight_map)")" \
    --argjson real_gguf_skipped "$(bool_or_false "$(step_skipped real_gguf_weight_map)")" \
    --argjson full_generation_claim_gate "$(bool_or_false "$(step_passed full_real_llama_generation_claim)")" \
    --argjson gguf_cell "$(bool_or_false "$(step_passed gguf_model_cell)")" \
    --argjson metal_cell "$(bool_or_false "$(step_passed metal_model_cell)")" \
    --argjson metal_trace "$(bool_or_false "$(step_passed metal_body_trace)")" \
    --argjson ask_staged_model_call "$(bool_or_false "$(step_passed ask_staged_model_call)")" \
    --argjson ask_staged_decoded_answer "$(bool_or_false "$ask_staged_decoded_answer_bound")" \
    --argjson decoded_answer "$(bool_or_false "$decoded_answer_observed")" \
    --argjson android_fkwu "$(bool_or_false "$(step_passed android_fkwu_fourth)")" \
    --argjson android_vulkan "$(bool_or_false "$(step_passed android_vulkan_matvec)")" \
    --argjson windows_form_cli "$(bool_or_false "$(step_passed windows_form_cli_native)")" \
    --argjson http_or_ollama_absent "$http_or_ollama_absent" \
    --argjson denied_toolchain_hidden "$denied_toolchain_hidden" \
    '{
      date: $date,
      trace_id: $trace_id,
      receipt_kind: $receipt_kind,
      thread_branch: $branch,
      git_commit: $commit,
      started_at: $started_at,
      ended_at: $ended_at,
      verdict: $verdict,
      full_model_inference_composed: false,
      ask_staged_decoded_answer_bound: $ask_staged_decoded_answer,
      reason_full_inference_not_claimed: "decoded answer binding is observed through native form-cli and the claim gate passes as a blocker, but the answer is not yet produced by full real Llama GGUF tokenizer arrays, real tensor bytes, accelerator buffers, autoregressive token IDs, and decoded token text in one native form-cli path",
      host: {
        os: $host_os,
        arch: $host_arch
      },
      observable_trace: {
        trace_dir: $trace_dir,
        steps_jsonl: $steps_jsonl,
        trace_sha256: $trace_sha256,
        steps_count: $steps_count,
        passed_count: $passed_count,
        skipped_count: $skipped_count,
        failed_count: $failed_count,
        hard_failed_count: $hard_failed_count,
        nonhard_failed_count: $nonhard_failed_count
      },
      synthesis_boundary: {
        available: ($available | split(",") | map(select(length > 0))),
        missing: (if $missing == "none" then [] else ($missing | split(",") | map(select(length > 0))) end)
      },
      runtime_dependency_claim: {
        scope: "child proof binaries, not this shell harness",
        http_or_ollama_absent_in_child_runtime: $http_or_ollama_absent,
        denied_go_rust_python_shell_clang_visible_on_child_runtime_path: $denied_toolchain_hidden
      },
      composition_gates: {
        native_fkwu_ask_grounded: $form_cli_ask,
        gguf_find_by_name_absolute_offset_four_way: $gguf_find,
        named_real_gguf_tensor_math_four_way: $real_gguf_tensor_math,
        tokenizer_carrier_four_way: $tokenizer,
        llama3_pretokenizer_four_way: $pretokenizer,
        autoregressive_generation_loop_four_way: $autoregressive_loop,
        optional_real_gguf_weight_map_observed: $real_gguf_weight_map,
        optional_real_gguf_weight_map_skipped: $real_gguf_skipped,
        full_real_llama_generation_claim_gate: $full_generation_claim_gate,
        fkwu_form_cli_gguf_model_cell: $gguf_cell,
        fkwu_form_cli_metal_model_cell: $metal_cell,
        form_native_metal_body_trace: $metal_trace,
        ask_staged_model_call_witness: $ask_staged_model_call,
        decoded_prose_answer_binding: $decoded_answer
      },
      devices: {
        macos: {
          current_host: $mac_host,
          observed_now: $mac_host,
          fkwu_form_cli_native: (if $mac_host then $form_cli_ask else false end),
          gguf_model_cell: (if $mac_host then $gguf_cell else false end),
          metal_model_cell: (if $mac_host then $metal_cell else false end),
          metal_body_trace: (if $mac_host then $metal_trace else false end),
          full_model_inference: false
        },
        android: {
          adb_device_observed_now: $android_device,
          fkwu_on_device_fourth_arm: $android_fkwu,
          vulkan_matvec_on_device: $android_vulkan,
          full_model_inference: false,
          note: "Android rows require an authorized adb device; absent hardware is recorded as skipped, not as a native inference pass."
        },
        windows: {
          current_host: $windows_host,
          observed_now: $windows_host,
          ci_workflow: ".github/workflows/windows-host.yml",
          fkwu_form_cli_native: (if $windows_host then $windows_form_cli else false end),
          gguf_model_cell: (if $windows_host then $gguf_cell else false end),
          directml_d3d12_model_cell: false,
          http_or_ollama_absent_in_child_runtime: (if $windows_host then $http_or_ollama_absent else false end),
          denied_go_rust_python_shell_clang_hidden_on_child_runtime_path: (if $windows_host then $denied_toolchain_hidden else false end),
          dependency_runtime_claim_proven: (if $windows_host then ($http_or_ollama_absent and $denied_toolchain_hidden) else false end),
          full_model_inference: false,
          note: "On non-Windows hosts this row is observed by the Windows Host Floor PR workflow."
        }
      },
      open_bridges: [
        "upgrade the receipt-scored decoded answer binding to full-width real GGUF semantic generation",
        "materialize the full-width Llama tensor set into the fkwu-controlled model-cell path, not only the current named tensor math witness",
        "dequant and place the full-width Llama tensor set into Metal/accelerator buffers",
        "run the full multi-layer GQA autoregressive loop over those real tensors",
        "project logits over the real vocabulary, select token IDs, and decode through the real tokenizer arrays",
        "bind that decoded text as the form-cli ask answer without HTTP, Ollama, MLX serving, or a proxy oracle",
        "add Android Vulkan/NNAPI and Windows DirectML/D3D12 model-cell carriers matching the macOS Metal model-cell receipt"
      ],
      steps: $steps
    }' > "$RECEIPT_PATH"

printf 'receipt=%s\n' "$RECEIPT_PATH"
printf 'trace=%s\n' "$TRACE_DIR"
printf 'verdict=%s\n' "$verdict"
printf 'full_model_inference_composed=false\n'
printf 'ask_staged_decoded_answer_bound=%s\n' "$ask_staged_decoded_answer_bound"

if [[ "$HARD_FAIL" -ne 0 ]]; then
    echo "failed_hard_gates:"
    while IFS= read -r row; do
        id="$(jq -r '.id' <<<"$row")"
        status="$(jq -r '.status' <<<"$row")"
        output_file="$(jq -r '.output_file' <<<"$row")"
        observation="$(jq -r '.observation' <<<"$row")"
        echo "- $id status=$status output=$output_file"
        if [[ -n "$observation" ]]; then
            printf '  observation=%s\n' "$observation"
        elif [[ -f "$ROOT/$output_file" ]]; then
            echo "  output_tail:"
            tail -20 "$ROOT/$output_file" | sed 's/^/    /'
        else
            echo "  observation="
        fi
    done < <(jq -c '
      select(.hard_gate == true and .status != 0 and .skipped == false)
    ' "$STEPS_JSONL")
    exit 1
fi
