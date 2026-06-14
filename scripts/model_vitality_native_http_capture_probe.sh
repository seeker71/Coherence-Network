#!/usr/bin/env bash
# model_vitality_native_http_capture_probe.sh — prove public pulse/runtime capture through kernel-native http_get.
#
# Floor: run Form code through the Go, Rust, TypeScript, and emitted fkwu
# kernels so public HTTP/HTTPS bytes are fetched by each kernel's native
# http_get carrier. Go/Rust/TypeScript also fetch the public HTTPS pulse/runtime
# lanes and lift them through model-vitality.fk into production rows. This
# script orchestrates the kernels and records their stdout; it does not use curl
# for the HTTP capture.
#
# North star: every kernel captures external HTTPS directly into the same Form
# row grammar, with no shell projection. The current all-kernel floor is
# plaintext external HTTP plus verified TLS body capture; Go/Rust/TypeScript
# already carry direct HTTPS production headers. The next lift is fourth-arm
# response-header row capture.
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

GO_BIN="form-kernel-go/bin-go"
RS_BIN="form-kernel-rust/target/release/form-kernel-rust"
# shellcheck source=form/scripts/fourth-arm.sh
source scripts/fourth-arm.sh
build_fourth
if ! fourth_available; then
    echo "FAIL fourth native-http carrier build failed"
    exit 1
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

write_external_http_band() {
    local target_url="$1"
    local verdict_path="$2"
    local detail_path="$3"
    cat > "$verdict_path" <<FK
(do
    (defn dict-get-pairs (xs key)
        (if (eq (len xs) 0)
            0
            (if (str_eq (head xs) key)
                (head (tail xs))
                (dict-get-pairs (tail (tail xs)) key))))
    (defn dict-get (d key) (dict-get-pairs (tail d) key))
    (defn dict-sentinel? (s)
        (and (eq (str_len s) 8)
        (and (eq (ord (char_at s 0)) 95)
        (and (eq (ord (char_at s 1)) 95)
        (and (eq (ord (char_at s 2)) 100)
        (and (eq (ord (char_at s 3)) 105)
        (and (eq (ord (char_at s 4)) 99)
        (and (eq (ord (char_at s 5)) 116)
        (and (eq (ord (char_at s 6)) 95)
             (eq (ord (char_at s 7)) 95))))))))))
    (let response (http_get "$target_url" (list) 8000))
    (let status (dict-get response "status_code"))
    (let body (dict-get response "body"))
    (let err (dict-get response "error"))
    (let duration (dict-get response "duration_ms"))
    (let c0 (if (dict-sentinel? (head response)) 1 0))
    (let c1 (if (eq status 200) 2 0))
    (let c2 (if (gt (str_len body) 100) 4 0))
    (let c3 (if (str_eq err "") 8 0))
    (let c4 (if (ge (str_find body "Example Domain" 0) 0) 16 0))
    (let c5 (if (ge duration 0) 32 0))
    (sum (list c0 c1 c2 c3 c4 c5)))
FK

    cat > "$detail_path" <<FK
(do
    (defn dict-get-pairs (xs key)
        (if (eq (len xs) 0)
            0
            (if (str_eq (head xs) key)
                (head (tail xs))
                (dict-get-pairs (tail (tail xs)) key))))
    (defn dict-get (d key) (dict-get-pairs (tail d) key))
    (let response (http_get "$target_url" (list) 8000))
    (let status (dict-get response "status_code"))
    (let body (dict-get response "body"))
    (let err (dict-get response "error"))
    (let duration (dict-get response "duration_ms"))
    (str_concat
        (str_concat
            (str_concat "status=" (int_to_str status))
            (str_concat " bytes=" (int_to_str (str_len body))))
            (str_concat
                (str_concat " error=" err)
                (str_concat " duration_ms=" (int_to_str duration)))))
FK
}

all_http_fk="$out_dir/all-kernel-http-verdict.fk"
all_http_detail_fk="$out_dir/all-kernel-http-detail.fk"
all_https_fk="$out_dir/all-kernel-https-verdict.fk"
all_https_detail_fk="$out_dir/all-kernel-https-detail.fk"
write_external_http_band "http://example.com/" "$all_http_fk" "$all_http_detail_fk"
write_external_http_band "https://example.com/" "$all_https_fk" "$all_https_detail_fk"

run_http_kernel() {
    local name="$1"
    shift
    "$@" "$compiled_core" "$all_http_fk" > "$out_dir/$name.http.verdict" 2> "$out_dir/$name.http.verdict.err" || {
        echo "FAIL $name all-kernel-http verdict failed"
        cat "$out_dir/$name.http.verdict.err"
        exit 1
    }
    "$@" "$compiled_core" "$all_http_detail_fk" > "$out_dir/$name.http.detail" 2> "$out_dir/$name.http.detail.err" || {
        echo "FAIL $name all-kernel-http detail failed"
        cat "$out_dir/$name.http.detail.err"
        exit 1
    }
}

run_fourth_http() {
    local src="$1"
    local out="$2"
    local err="$3"
    local driver="$out_dir/$(basename "$out").driver.fk"
    local table="$out_dir/$(basename "$out").table.txt"
    cat "${FOURTH_CHAIN[@]}" > "$driver"
    fourth_flatten_expr fks "$src" >> "$driver"
    "$GO_BIN" "$driver" > "$table" 2> "$err.flatten" || {
        echo "FAIL fourth all-kernel-http flatten failed"
        cat "$err.flatten"
        exit 1
    }
    "$FKWU" "$table" 0 > "$out.full" 2> "$err" || {
        echo "FAIL fourth all-kernel-http fkwu failed"
        cat "$err"
        exit 1
    }
    head -n 1 "$out.full" > "$out"
}

run_http_kernel http-go "$GO_BIN"
run_http_kernel http-rust "$RS_BIN"
run_http_kernel http-typescript run_ts
run_fourth_http "$all_http_fk" "$out_dir/http-fourth.http.verdict" "$out_dir/http-fourth.http.verdict.err"
run_fourth_http "$all_http_detail_fk" "$out_dir/http-fourth.http.detail" "$out_dir/http-fourth.http.detail.err"

run_https_kernel() {
    local name="$1"
    shift
    "$@" "$compiled_core" "$all_https_fk" > "$out_dir/$name.https.verdict" 2> "$out_dir/$name.https.verdict.err" || {
        echo "FAIL $name all-kernel-https verdict failed"
        cat "$out_dir/$name.https.verdict.err"
        exit 1
    }
    "$@" "$compiled_core" "$all_https_detail_fk" > "$out_dir/$name.https.detail" 2> "$out_dir/$name.https.detail.err" || {
        echo "FAIL $name all-kernel-https detail failed"
        cat "$out_dir/$name.https.detail.err"
        exit 1
    }
}

run_https_kernel https-go "$GO_BIN"
run_https_kernel https-rust "$RS_BIN"
run_https_kernel https-typescript run_ts
run_fourth_http "$all_https_fk" "$out_dir/https-fourth.https.verdict" "$out_dir/https-fourth.https.verdict.err"
run_fourth_http "$all_https_detail_fk" "$out_dir/https-fourth.https.detail" "$out_dir/https-fourth.https.detail.err"

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

http_go_v="$(cat "$out_dir/http-go.http.verdict")"
http_rust_v="$(cat "$out_dir/http-rust.http.verdict")"
http_ts_v="$(cat "$out_dir/http-typescript.http.verdict")"
http_fourth_v="$(cat "$out_dir/http-fourth.http.verdict")"
if [[ "$http_go_v" != "63" || "$http_rust_v" != "63" || "$http_ts_v" != "63" || "$http_fourth_v" != "63" ]]; then
    echo "FAIL all-kernel-http verdict go=$http_go_v rust=$http_rust_v typescript=$http_ts_v fourth=$http_fourth_v cache=$out_dir"
    echo "http go detail: $(cat "$out_dir/http-go.http.detail" 2>/dev/null || true)"
    echo "http rust detail: $(cat "$out_dir/http-rust.http.detail" 2>/dev/null || true)"
    echo "http typescript detail: $(cat "$out_dir/http-typescript.http.detail" 2>/dev/null || true)"
    echo "http fourth detail: $(cat "$out_dir/http-fourth.http.detail" 2>/dev/null || true)"
    exit 1
fi

https_go_v="$(cat "$out_dir/https-go.https.verdict")"
https_rust_v="$(cat "$out_dir/https-rust.https.verdict")"
https_ts_v="$(cat "$out_dir/https-typescript.https.verdict")"
https_fourth_v="$(cat "$out_dir/https-fourth.https.verdict")"
if [[ "$https_go_v" != "63" || "$https_rust_v" != "63" || "$https_ts_v" != "63" || "$https_fourth_v" != "63" ]]; then
    echo "FAIL all-kernel-https verdict go=$https_go_v rust=$https_rust_v typescript=$https_ts_v fourth=$https_fourth_v cache=$out_dir"
    echo "https go detail: $(cat "$out_dir/https-go.https.detail" 2>/dev/null || true)"
    echo "https rust detail: $(cat "$out_dir/https-rust.https.detail" 2>/dev/null || true)"
    echo "https typescript detail: $(cat "$out_dir/https-typescript.https.detail" 2>/dev/null || true)"
    echo "https fourth detail: $(cat "$out_dir/https-fourth.https.detail" 2>/dev/null || true)"
    exit 1
fi

cat > "$out_dir/native-http-capture-summary.txt" <<EOF
https_model_vitality:
go: $(cat "$out_dir/go.detail")
rust: $(cat "$out_dir/rust.detail")
typescript: $(cat "$out_dir/typescript.detail")
all_kernel_plain_http:
go: $(cat "$out_dir/http-go.http.detail")
rust: $(cat "$out_dir/http-rust.http.detail")
typescript: $(cat "$out_dir/http-typescript.http.detail")
fourth: $(cat "$out_dir/http-fourth.http.detail")
all_kernel_verified_https:
go: $(cat "$out_dir/https-go.https.detail")
rust: $(cat "$out_dir/https-rust.https.detail")
typescript: $(cat "$out_dir/https-typescript.https.detail")
fourth: $(cat "$out_dir/https-fourth.https.detail")
fourth_arm_header_gap: HTTPS/TLS body capture is native; response-header rows are not yet captured by fkwu.
EOF

echo "PASS native-http-capture go=127 rust=127 typescript=127 cache=$out_dir/native-http-capture-summary.txt"
echo "PASS go $(cat "$out_dir/go.detail")"
echo "PASS rust $(cat "$out_dir/rust.detail")"
echo "PASS typescript $(cat "$out_dir/typescript.detail")"
echo "PASS all-kernel-external-http go=63 rust=63 typescript=63 fourth=63 url=http://example.com/"
echo "PASS http-go $(cat "$out_dir/http-go.http.detail")"
echo "PASS http-rust $(cat "$out_dir/http-rust.http.detail")"
echo "PASS http-typescript $(cat "$out_dir/http-typescript.http.detail")"
echo "PASS http-fourth $(cat "$out_dir/http-fourth.http.detail")"
echo "PASS all-kernel-external-https go=63 rust=63 typescript=63 fourth=63 url=https://example.com/"
echo "PASS https-go $(cat "$out_dir/https-go.https.detail")"
echo "PASS https-rust $(cat "$out_dir/https-rust.https.detail")"
echo "PASS https-typescript $(cat "$out_dir/https-typescript.https.detail")"
echo "PASS https-fourth $(cat "$out_dir/https-fourth.https.detail")"
echo "PASS fourth-arm-https native-tls=openssl-dlopen verified=true"
echo "GAP fourth-arm-headers native-header-list=empty next=fourth-kernel-header-row-capture"
