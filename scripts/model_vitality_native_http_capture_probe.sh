#!/usr/bin/env bash
# model_vitality_native_http_capture_probe.sh — prove public pulse/runtime capture through kernel-native http_get.
#
# Floor: run Form code through the Go, Rust, and TypeScript kernels so public HTTPS bytes are
# fetched by each kernel's native http_get carrier, then lifted by
# model-vitality.fk into production pulse/runtime rows. This script orchestrates
# the kernels and records their stdout; it does not use curl for the HTTP
# capture.
#
# North star: every kernel captures external HTTPS directly into the same Form
# row grammar, with no shell projection. The current native floor is Go+Rust+TS
# direct HTTPS; the next lift is fourth-arm channel support.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"
cd "$FORM"

if [[ ! -x form-kernel-go/bin-go ]]; then
    (cd form-kernel-go && go build -o bin-go .)
fi
if [[ ! -x form-kernel-rust/target/release/form-kernel-rust ]]; then
    (cd form-kernel-rust && cargo build --release --quiet)
fi
ts_bundle="form-kernel-ts/dist/main.mjs"
ts_stale=0
if [[ ! -f "$ts_bundle" ]]; then
    ts_stale=1
else
    for f in form-kernel-ts/src/*.ts; do
        [[ "$f" -nt "$ts_bundle" ]] && { ts_stale=1; break; }
    done
fi
if [[ "$ts_stale" == "1" ]]; then
    npx --yes esbuild form-kernel-ts/src/main.ts --bundle --platform=node \
        --format=esm --outfile="$ts_bundle" --log-level=warning >/dev/null
fi

run_ts() {
    node --stack_size=262144 "$ts_bundle" "$@"
}

stamp="$(date -u +"%Y%m%dT%H%M%SZ")"
out_dir="$ROOT/.cache/model-vitality-native-http/$stamp"
mkdir -p "$out_dir"

compiled_core="$out_dir/core.fk"
compile_driver="$out_dir/compile-core.fk"
printf '(do (form-source-compile-file "form-stdlib/core.fk" "%s"))\n' "$compiled_core" > "$compile_driver"
./form-kernel-go/bin-go \
    form-stdlib/json.fk \
    form-stdlib/cache.fk \
    form-stdlib/form-ontology-loader.fk \
    form-stdlib/source-compiler.fk \
    "$compile_driver" > "$out_dir/source-compile.out" 2> "$out_dir/source-compile.err" || {
        echo "FAIL source-compile core.fk"
        cat "$out_dir/source-compile.err"
        exit 1
    }

verdict_fk="$out_dir/native-http-verdict.fk"
detail_fk="$out_dir/native-http-detail.fk"

cat > "$verdict_fk" <<'FK'
(do
    (let floor (mv-floor))
    (let north (mv-north-star))
    (let pulse-url "https://api.coherencycoin.com/api/pulse/now")
    (let runtime-url "https://api.coherencycoin.com/api/runtime/endpoints/summary?limit=5")
    (let headers (list (mv-http-header "Accept" "application/json")))
    (let pulse-response (http_get pulse-url headers 8000))
    (let runtime-response (http_get runtime-url headers 8000))
    (let capture (mv-native-http-capture pulse-url pulse-response floor north))
    (let runtime (mv-native-http-runtime-telemetry runtime-url runtime-response floor north))
    (let c0 (if (mv-native-http-capture-valid? capture) 1 0))
    (let c1 (if (eq (mv-http-response-status pulse-response) 200) 2 0))
    (let c2 (if (mv-production-runtime-valid? runtime) 4 0))
    (let c3 (if (str_eq (mv-production-runtime-router runtime) "native-kernel") 8 0))
    (let c4 (if (str_eq (mv-production-runtime-python-authority runtime) "false") 16 0))
    (let c5 (if (gt (mv-native-http-capture-body-bytes capture) 0) 32 0))
    (let c6 (if (gt (mv-production-runtime-body-bytes runtime) 0) 64 0))
    (sum (list c0 c1 c2 c3 c4 c5 c6)))
FK

cat > "$detail_fk" <<'FK'
(do
    (let floor (mv-floor))
    (let north (mv-north-star))
    (let pulse-url "https://api.coherencycoin.com/api/pulse/now")
    (let runtime-url "https://api.coherencycoin.com/api/runtime/endpoints/summary?limit=5")
    (let headers (list (mv-http-header "Accept" "application/json")))
    (let pulse-response (http_get pulse-url headers 8000))
    (let runtime-response (http_get runtime-url headers 8000))
    (let capture (mv-native-http-capture pulse-url pulse-response floor north))
    (let runtime (mv-native-http-runtime-telemetry runtime-url runtime-response floor north))
    (str_concat
        (str_concat
            (str_concat
                (str_concat "api_status=" (int_to_str (mv-native-http-capture-status capture)))
                (str_concat " api_capture_authority=" (mv-native-http-capture-authority capture)))
            (str_concat
                (str_concat " api_bytes=" (int_to_str (mv-native-http-capture-body-bytes capture)))
                (str_concat " api_latency_ms=" (int_to_str (mv-native-http-capture-duration-ms capture)))))
        (str_concat
            (str_concat
                (str_concat " runtime_status=" (int_to_str (mv-production-runtime-status runtime)))
                (str_concat " runtime_router=" (mv-production-runtime-router runtime)))
            (str_concat
                (str_concat " runtime_handler=" (mv-production-runtime-handler runtime))
                (str_concat
                    (str_concat " runtime_python_authority=" (mv-production-runtime-python-authority runtime))
                    (str_concat " runtime_latency_ms=" (int_to_str (mv-production-runtime-latency-ms runtime))))))))
FK

run_kernel() {
    local name="$1"
    shift
    "$@" "$compiled_core" form-stdlib/json.fk form-stdlib/model-vitality.fk "$verdict_fk" > "$out_dir/$name.verdict" 2> "$out_dir/$name.verdict.err" || {
        echo "FAIL $name native-http verdict failed"
        cat "$out_dir/$name.verdict.err"
        exit 1
    }
    "$@" "$compiled_core" form-stdlib/json.fk form-stdlib/model-vitality.fk "$detail_fk" > "$out_dir/$name.detail" 2> "$out_dir/$name.detail.err" || {
        echo "FAIL $name native-http detail failed"
        cat "$out_dir/$name.detail.err"
        exit 1
    }
}

run_kernel go ./form-kernel-go/bin-go
run_kernel rust ./form-kernel-rust/target/release/form-kernel-rust
run_kernel typescript run_ts

go_v="$(cat "$out_dir/go.verdict")"
rust_v="$(cat "$out_dir/rust.verdict")"
ts_v="$(cat "$out_dir/typescript.verdict")"
if [[ "$go_v" != "127" || "$rust_v" != "127" || "$ts_v" != "127" ]]; then
    echo "FAIL native-http verdict go=$go_v rust=$rust_v typescript=$ts_v cache=$out_dir"
    echo "go detail: $(cat "$out_dir/go.detail")"
    echo "rust detail: $(cat "$out_dir/rust.detail")"
    echo "typescript detail: $(cat "$out_dir/typescript.detail")"
    exit 1
fi

cat > "$out_dir/native-http-capture-summary.txt" <<EOF
go: $(cat "$out_dir/go.detail")
rust: $(cat "$out_dir/rust.detail")
typescript: $(cat "$out_dir/typescript.detail")
fourth_arm_gap: external HTTPS channel support is not accepted as native capture evidence here yet.
EOF

echo "PASS native-http-capture go=127 rust=127 typescript=127 cache=$out_dir/native-http-capture-summary.txt"
echo "PASS go $(cat "$out_dir/go.detail")"
echo "PASS rust $(cat "$out_dir/rust.detail")"
echo "PASS typescript $(cat "$out_dir/typescript.detail")"
echo "GAP fourth-arm-http-get native-carrier=missing next=fourth-kernel-channel-support"
