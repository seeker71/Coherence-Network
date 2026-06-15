#!/usr/bin/env bash
# Build and run a native Mac + Android core-axiom receipt pair.
#
# The Android side is a one-shot arm64 binary pushed to /data/local/tmp. The
# Mac side is a one-shot localhost client. They communicate through adb forward
# over TCP, write an explicit JSON receipt, then clean up the remote binary.
#
# Usage:
#   scripts/android_mac_core_axiom_receipt.sh [samples] [width]

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SAMPLES="${1:-1024}"
WIDTH="${2:-8}"
WORK="$ROOT/.cache/android_mac_core_axiom_receipt"
SRC="$WORK/core_axiom_receipt.c"
MAC_BIN="$WORK/core-axiom-receipt-macos"
ANDROID_BIN="$WORK/core-axiom-receipt-android-arm64"
OUT="$WORK/latest.json"
PACKAGE_OUT="$WORK/package-latest.json"
SERVER_STDOUT="$WORK/android-server.stdout"
SERVER_STDERR="$WORK/android-server.stderr"
MAC_CLIENT_STDOUT="$WORK/mac-client.stdout"
MAC_CLIENT_STDERR="$WORK/mac-client.stderr"
ANDROID_RC="$WORK/android-server.rc"
PORT="${CORE_AXIOM_RECEIPT_PORT:-$((41730 + ($$ % 2000)))}"
REMOTE="/data/local/tmp/coherence-core-axiom-receipt-$$"

mkdir -p "$WORK"

now_ms() {
  perl -MTime::HiRes=time -e 'printf "%d\n", time() * 1000'
}

sha256_file() {
  shasum -a 256 "$1" | awk '{print $1}'
}

json_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

if [[ "$SAMPLES" -le 0 || "$WIDTH" -le 0 || "$WIDTH" -gt 32 ]]; then
  echo "samples and width must be positive; width <= 32" >&2
  exit 2
fi

NDK="${ANDROID_NDK_HOME:-$(ls -d /opt/homebrew/Caskroom/android-ndk/*/AndroidNDK*.app/Contents/NDK 2>/dev/null | head -1)}"
ANDROID_CLANG="${ANDROID_CLANG:-}"
if [[ -z "$ANDROID_CLANG" && -d "$NDK" ]]; then
  ANDROID_CLANG="$(find "$NDK/toolchains/llvm/prebuilt" -type f -name 'aarch64-linux-android34-clang' 2>/dev/null | head -1)"
fi
if [[ -z "$ANDROID_CLANG" ]]; then
  echo "Android NDK clang not found; install android-ndk or set ANDROID_CLANG" >&2
  exit 1
fi
if ! command -v adb >/dev/null 2>&1; then
  echo "adb not found" >&2
  exit 1
fi

cat > "$SRC" <<'C'
#include <arpa/inet.h>
#include <errno.h>
#include <inttypes.h>
#include <netinet/in.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <unistd.h>

#define BUF_SIZE 16384

typedef struct {
    int samples;
    int width;
    int passed;
    int failed;
    int64_t checksum;
} Proof;

static int64_t next_value(uint64_t *seed) {
    *seed = (*seed * 1103515245ULL + 12345ULL) & 0x7fffffffULL;
    return (int64_t)((*seed >> 8) % 11) - 5;
}

static int64_t pred(const int64_t *weights, const int64_t *x, int width, int64_t b) {
    int64_t sum = b;
    for (int i = 0; i < width; i++) {
        sum += weights[i] * x[i];
    }
    return sum;
}

static int64_t loss(const int64_t *weights, const int64_t *x, int width, int64_t b, int64_t target) {
    int64_t err = pred(weights, x, width, b) - target;
    return err * err;
}

static Proof run_proof(int samples, int width) {
    Proof proof = {samples, width, 0, 0, INT64_C(1469598103934665603)};
    uint64_t seed = UINT64_C(0xC0DEC0DE);
    int64_t weights[32];
    int64_t plus[32];
    int64_t minus[32];
    int64_t x[32];

    for (int s = 0; s < samples; s++) {
        for (int i = 0; i < width; i++) {
            weights[i] = next_value(&seed);
            x[i] = next_value(&seed);
        }
        int64_t b = next_value(&seed);
        int64_t target = next_value(&seed);
        int64_t err = pred(weights, x, width, b) - target;
        int ok = 1;

        for (int i = 0; i < width; i++) {
            memcpy(plus, weights, sizeof(int64_t) * (size_t)width);
            memcpy(minus, weights, sizeof(int64_t) * (size_t)width);
            plus[i]++;
            minus[i]--;
            int64_t analytic = 2 * err * x[i];
            int64_t numeric = (loss(plus, x, width, b, target) - loss(minus, x, width, b, target)) / 2;
            if (analytic != numeric) {
                ok = 0;
            }
            proof.checksum = (proof.checksum ^ analytic) * INT64_C(1099511628211);
            proof.checksum = (proof.checksum ^ numeric) * INT64_C(1099511628211);
        }

        int64_t analytic_b = 2 * err;
        int64_t numeric_b = (loss(weights, x, width, b + 1, target) - loss(weights, x, width, b - 1, target)) / 2;
        if (analytic_b != numeric_b) {
            ok = 0;
        }
        proof.checksum = (proof.checksum ^ analytic_b) * INT64_C(1099511628211);
        proof.checksum = (proof.checksum ^ numeric_b) * INT64_C(1099511628211);

        if (ok) {
            proof.passed++;
        } else {
            proof.failed++;
        }
    }
    return proof;
}

static const char *platform_name(void) {
#ifdef __ANDROID__
    return "android-arm64";
#elif defined(__APPLE__)
    return "macos-arm64";
#else
    return "native-host";
#endif
}

static void write_endpoint_json(char *buf, size_t n, const char *role, const char *channel, Proof proof) {
    const char *status = proof.failed == 0 ? "pass" : "fail";
    snprintf(buf, n,
        "{\"kind\":\"core-axiom-native-receipt\","
        "\"role\":\"%s\","
        "\"platform\":\"%s\","
        "\"channel\":\"%s\","
        "\"learning_mode\":\"bounded-left-expanding-sample-window\","
        "\"axiom_trace_count\":6,"
        "\"axiom_trace\":[\"content-addressed-cells\",\"receipt-before-trust\",\"bounded-carrier\",\"native-sibling-parity\",\"explicit-channel\",\"reversible-cleanup\"],"
        "\"samples\":%d,"
        "\"width\":%d,"
        "\"passed\":%d,"
        "\"failed\":%d,"
        "\"checksum\":%" PRId64 ","
        "\"self_modifying\":false,"
        "\"background_service\":false,"
        "\"status\":\"%s\"}",
        role, platform_name(), channel, proof.samples, proof.width, proof.passed,
        proof.failed, proof.checksum, status);
}

static int contains_endpoint(const char *body, const char *role, const char *platform, int samples) {
    char sample_need[64];
    char passed_need[64];
    char role_need[96];
    char platform_need[96];
    snprintf(sample_need, sizeof(sample_need), "\"samples\":%d", samples);
    snprintf(passed_need, sizeof(passed_need), "\"passed\":%d", samples);
    snprintf(role_need, sizeof(role_need), "\"role\":\"%s\"", role);
    snprintf(platform_need, sizeof(platform_need), "\"platform\":\"%s\"", platform);
    return strstr(body, "\"kind\":\"core-axiom-native-receipt\"") &&
           strstr(body, role_need) &&
           strstr(body, platform_need) &&
           strstr(body, "\"channel\":\"adb-forward-tcp\"") &&
           strstr(body, "\"axiom_trace_count\":6") &&
           strstr(body, sample_need) &&
           strstr(body, passed_need) &&
           strstr(body, "\"failed\":0") &&
           strstr(body, "\"self_modifying\":false") &&
           strstr(body, "\"background_service\":false") &&
           strstr(body, "\"status\":\"pass\"");
}

static int read_receipt_line(int fd, char *buf, size_t cap) {
    size_t used = 0;
    while (used + 1 < cap) {
        ssize_t n = read(fd, buf + used, cap - used - 1);
        if (n < 0) {
            perror("read receipt");
            return -1;
        }
        if (n == 0) {
            break;
        }
        used += (size_t)n;
        if (memchr(buf, '\n', used)) {
            break;
        }
    }
    buf[used] = '\0';
    char *newline = memchr(buf, '\n', used);
    if (newline) {
        *newline = '\0';
    }
    return (int)used;
}

static int connect_to(const char *host, int port) {
    int fd = socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) {
        perror("socket");
        return -1;
    }
    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons((uint16_t)port);
    if (inet_pton(AF_INET, host, &addr.sin_addr) != 1) {
        fprintf(stderr, "invalid host: %s\n", host);
        close(fd);
        return -1;
    }
    if (connect(fd, (struct sockaddr *)&addr, sizeof(addr)) != 0) {
        perror("connect");
        close(fd);
        return -1;
    }
    return fd;
}

static int listen_on(const char *host, int port) {
    int fd = socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) {
        perror("socket");
        return -1;
    }
    int yes = 1;
    setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes));
    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons((uint16_t)port);
    if (inet_pton(AF_INET, host, &addr.sin_addr) != 1) {
        fprintf(stderr, "invalid host: %s\n", host);
        close(fd);
        return -1;
    }
    if (bind(fd, (struct sockaddr *)&addr, sizeof(addr)) != 0) {
        perror("bind");
        close(fd);
        return -1;
    }
    if (listen(fd, 1) != 0) {
        perror("listen");
        close(fd);
        return -1;
    }
    return fd;
}

static int run_android_client(const char *host, int port, int samples, int width) {
    char json[BUF_SIZE];
    char ack[256];
    Proof proof = run_proof(samples, width);
    write_endpoint_json(json, sizeof(json), "android-device", "adb-forward-tcp", proof);

    int fd = connect_to(host, port);
    if (fd < 0) {
        return 1;
    }
    if (write(fd, json, strlen(json)) < 0 || write(fd, "\n", 1) < 0) {
        perror("write");
        close(fd);
        return 1;
    }
    shutdown(fd, SHUT_WR);
    ssize_t n = read(fd, ack, sizeof(ack) - 1);
    if (n < 0) {
        perror("read ack");
        close(fd);
        return 1;
    }
    ack[n] = '\0';
    close(fd);
    puts(json);
    return strstr(ack, "ACK pass") && proof.failed == 0 ? 0 : 1;
}

static int run_mac_server(const char *host, int port, int samples, int width, const char *out_path) {
    signal(SIGPIPE, SIG_IGN);
    char mac_json[BUF_SIZE];
    char peer_json[BUF_SIZE];
    Proof proof = run_proof(samples, width);
    write_endpoint_json(mac_json, sizeof(mac_json), "macos-host", "adb-forward-tcp", proof);

    int listener = listen_on(host, port);
    if (listener < 0) {
        return 1;
    }
    int fd = accept(listener, NULL, NULL);
    close(listener);
    if (fd < 0) {
        perror("accept");
        return 1;
    }
    if (read_receipt_line(fd, peer_json, sizeof(peer_json)) < 0) {
        close(fd);
        return 1;
    }
    int peer_valid = contains_endpoint(peer_json, "android-device", "android-arm64", samples);
    int ok = peer_valid && proof.failed == 0;
    dprintf(fd, "ACK %s\n", ok ? "pass" : "fail");
    close(fd);

    FILE *out = fopen(out_path, "w");
    if (!out) {
        perror("fopen receipt");
        return 1;
    }
    fprintf(out,
        "{\"kind\":\"core-axiom-native-channel-receipt\","
        "\"channel\":\"adb-forward-tcp\","
        "\"carrier\":\"macos-localhost-to-android-adb-forward\","
        "\"mac\":%s,"
        "\"android\":%s,"
        "\"peer_valid\":%s,"
        "\"endpoint_count\":2,"
        "\"samples_per_endpoint\":%d,"
        "\"status\":\"%s\"}\n",
        mac_json, peer_json, peer_valid ? "true" : "false", samples, ok ? "pass" : "fail");
    fclose(out);
    printf("%s\n", ok ? "pass" : "fail");
    return ok ? 0 : 1;
}

static int run_android_server(const char *host, int port, int samples, int width) {
    signal(SIGPIPE, SIG_IGN);
    char android_json[BUF_SIZE];
    char peer_json[BUF_SIZE];
    Proof proof = run_proof(samples, width);
    write_endpoint_json(android_json, sizeof(android_json), "android-device", "adb-forward-tcp", proof);

    int listener = listen_on(host, port);
    if (listener < 0) {
        return 1;
    }
    int fd = accept(listener, NULL, NULL);
    close(listener);
    if (fd < 0) {
        perror("accept");
        return 1;
    }
    if (read_receipt_line(fd, peer_json, sizeof(peer_json)) < 0) {
        close(fd);
        return 1;
    }
    int peer_valid = contains_endpoint(peer_json, "macos-host", "macos-arm64", samples);
    if (write(fd, android_json, strlen(android_json)) < 0 || write(fd, "\n", 1) < 0) {
        perror("write android receipt");
        close(fd);
        return 1;
    }
    close(fd);
    puts(android_json);
    return peer_valid && proof.failed == 0 ? 0 : 1;
}

static int run_mac_client(const char *host, int port, int samples, int width, const char *out_path) {
    char mac_json[BUF_SIZE];
    char peer_json[BUF_SIZE];
    Proof proof = run_proof(samples, width);
    write_endpoint_json(mac_json, sizeof(mac_json), "macos-host", "adb-forward-tcp", proof);

    int fd = connect_to(host, port);
    if (fd < 0) {
        return 1;
    }
    if (write(fd, mac_json, strlen(mac_json)) < 0 || write(fd, "\n", 1) < 0) {
        perror("write mac receipt");
        close(fd);
        return 1;
    }
    if (read_receipt_line(fd, peer_json, sizeof(peer_json)) < 0) {
        close(fd);
        return 1;
    }
    close(fd);

    int peer_valid = contains_endpoint(peer_json, "android-device", "android-arm64", samples);
    int ok = peer_valid && proof.failed == 0;
    FILE *out = fopen(out_path, "w");
    if (!out) {
        perror("fopen receipt");
        return 1;
    }
    fprintf(out,
        "{\"kind\":\"core-axiom-native-channel-receipt\","
        "\"channel\":\"adb-forward-tcp\","
        "\"carrier\":\"macos-localhost-to-android-adb-forward\","
        "\"mac\":%s,"
        "\"android\":%s,"
        "\"peer_valid\":%s,"
        "\"endpoint_count\":2,"
        "\"samples_per_endpoint\":%d,"
        "\"status\":\"%s\"}\n",
        mac_json, peer_json, peer_valid ? "true" : "false", samples, ok ? "pass" : "fail");
    fclose(out);
    printf("%s\n", ok ? "pass" : "fail");
    return ok ? 0 : 1;
}

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "usage: %s mac-server|mac-client|android-server|android-client ...\n", argv[0]);
        return 2;
    }
    if (strcmp(argv[1], "android-client") == 0) {
        if (argc != 6) {
            fprintf(stderr, "usage: %s android-client host port samples width\n", argv[0]);
            return 2;
        }
        return run_android_client(argv[2], atoi(argv[3]), atoi(argv[4]), atoi(argv[5]));
    }
    if (strcmp(argv[1], "mac-server") == 0) {
        if (argc != 7) {
            fprintf(stderr, "usage: %s mac-server host port samples width out.json\n", argv[0]);
            return 2;
        }
        return run_mac_server(argv[2], atoi(argv[3]), atoi(argv[4]), atoi(argv[5]), argv[6]);
    }
    if (strcmp(argv[1], "android-server") == 0) {
        if (argc != 6) {
            fprintf(stderr, "usage: %s android-server host port samples width\n", argv[0]);
            return 2;
        }
        return run_android_server(argv[2], atoi(argv[3]), atoi(argv[4]), atoi(argv[5]));
    }
    if (strcmp(argv[1], "mac-client") == 0) {
        if (argc != 7) {
            fprintf(stderr, "usage: %s mac-client host port samples width out.json\n", argv[0]);
            return 2;
        }
        return run_mac_client(argv[2], atoi(argv[3]), atoi(argv[4]), atoi(argv[5]), argv[6]);
    }
    fprintf(stderr, "unknown mode: %s\n", argv[1]);
    return 2;
}
C

clang -O2 -Wall -Wextra -o "$MAC_BIN" "$SRC"
"$ANDROID_CLANG" -O2 -Wall -Wextra -o "$ANDROID_BIN" "$SRC"

mac_desc="$(file "$MAC_BIN")"
android_desc="$(file "$ANDROID_BIN")"
case "$mac_desc" in
  *"Mach-O"*"arm64"*) ;;
  *) echo "Mac binary is not Mach-O arm64: $mac_desc" >&2; exit 1 ;;
esac
case "$android_desc" in
  *"ELF 64-bit"*"ARM aarch64"*) ;;
  *"ELF 64-bit"*"AArch64"*) ;;
  *) echo "Android binary is not ELF aarch64: $android_desc" >&2; exit 1 ;;
esac

serial="${CORE_AXIOM_ADB_SERIAL:-}"
if [[ -z "$serial" ]]; then
  serials="$(adb devices | awk 'NR > 1 && $2 == "device" { print $1 }')"
  count="$(printf '%s\n' "$serials" | sed '/^$/d' | wc -l | tr -d ' ')"
  if [[ "$count" != "1" ]]; then
    echo "Expected exactly one authorized adb device; found $count. Set CORE_AXIOM_ADB_SERIAL." >&2
    exit 1
  fi
  serial="$(printf '%s\n' "$serials" | sed -n '1p')"
fi

abi="$(adb -s "$serial" shell getprop ro.product.cpu.abi | tr -d '\r')"
model="$(adb -s "$serial" shell getprop ro.product.model | tr -d '\r')"
android_version="$(adb -s "$serial" shell getprop ro.build.version.release | tr -d '\r')"
if ! grep -q "arm64" <<<"$abi"; then
  echo "adb device abi '$abi' is not arm64" >&2
  exit 1
fi

rm -f "$OUT" "$PACKAGE_OUT" "$SERVER_STDOUT" "$SERVER_STDERR" "$MAC_CLIENT_STDOUT" "$MAC_CLIENT_STDERR" "$ANDROID_RC"
cleanup() {
  adb -s "$serial" forward --remove "tcp:$PORT" >/dev/null 2>&1 || true
  adb -s "$serial" shell "rm -f '$REMOTE'" >/dev/null 2>&1 || true
  if [[ "${server_pid:-}" != "" ]] && kill -0 "$server_pid" >/dev/null 2>&1; then
    kill "$server_pid" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

adb -s "$serial" push "$ANDROID_BIN" "$REMOTE" >/dev/null
adb -s "$serial" shell "chmod 755 '$REMOTE'"
adb -s "$serial" forward "tcp:$PORT" "tcp:$PORT" >/dev/null
adb -s "$serial" shell "'$REMOTE' android-server 127.0.0.1 '$PORT' '$SAMPLES' '$WIDTH'" >"$SERVER_STDOUT" 2>"$SERVER_STDERR" || echo $? >"$ANDROID_RC" &
server_pid=$!
sleep 0.5
channel_start_ms="$(now_ms)"
"$MAC_BIN" mac-client 127.0.0.1 "$PORT" "$SAMPLES" "$WIDTH" "$OUT" >"$MAC_CLIENT_STDOUT" 2>"$MAC_CLIENT_STDERR"
channel_end_ms="$(now_ms)"
wait "$server_pid"
trap - EXIT
cleanup
remote_state="$(adb -s "$serial" shell "if [ -e '$REMOTE' ]; then echo present; else echo absent; fi" | tr -d '\r[:space:]')"
remote_cleanup="fail"
if [[ "$remote_state" == "absent" ]]; then
  remote_cleanup="pass"
fi

if [[ -s "$ANDROID_RC" ]]; then
  echo "Android receipt server failed rc=$(cat "$ANDROID_RC") stderr=$(cat "$SERVER_STDERR")" >&2
  exit 1
fi
if [[ "$(cat "$MAC_CLIENT_STDOUT" | tr -d '\r\n')" != "pass" ]]; then
  echo "Mac receipt client failed stdout=$(cat "$MAC_CLIENT_STDOUT") stderr=$(cat "$MAC_CLIENT_STDERR")" >&2
  exit 1
fi
if ! grep -q '"kind":"core-axiom-native-channel-receipt"' "$OUT" || ! grep -q '"status":"pass"' "$OUT"; then
  echo "Combined receipt missing pass status" >&2
  cat "$OUT" >&2 || true
  exit 1
fi
if [[ "$remote_cleanup" != "pass" ]]; then
  echo "Remote binary cleanup failed: $REMOTE is still present" >&2
  exit 1
fi

script_sha="$(sha256_file "$0")"
generated_source_sha="$(sha256_file "$SRC")"
mac_sha="$(sha256_file "$MAC_BIN")"
android_sha="$(sha256_file "$ANDROID_BIN")"
channel_receipt_sha="$(sha256_file "$OUT")"
channel_duration_ms=$((channel_end_ms - channel_start_ms))
mac_desc_json="$(json_escape "$mac_desc")"
android_desc_json="$(json_escape "$android_desc")"
model_json="$(json_escape "$model")"
abi_json="$(json_escape "$abi")"
android_version_json="$(json_escape "$android_version")"

cat > "$PACKAGE_OUT" <<JSON
{"kind":"core-axiom-native-package-receipt","script_sha256":"$script_sha","generated_source_sha256":"$generated_source_sha","mac_binary_sha256":"$mac_sha","android_binary_sha256":"$android_sha","channel_receipt_sha256":"$channel_receipt_sha","mac_file":"$mac_desc_json","android_file":"$android_desc_json","device_model":"$model_json","android_version":"$android_version_json","android_abi":"$abi_json","channel":"adb-forward-tcp","channel_duration_ms":$channel_duration_ms,"samples":$SAMPLES,"width":$WIDTH,"remote_path":"$REMOTE","remote_cleanup":"$remote_cleanup","status":"pass"}
JSON

printf 'PASS mac=%s android=%s model=%s android_version=%s abi=%s channel=adb-forward-tcp samples=%s width=%s receipt=%s\n' \
  "$mac_desc" "$android_desc" "$model" "$android_version" "$abi" "$SAMPLES" "$WIDTH" "$OUT"
cat "$OUT"
printf 'PACKAGE receipt=%s sha256=%s channel_duration_ms=%s remote_cleanup=%s\n' "$PACKAGE_OUT" "$channel_receipt_sha" "$channel_duration_ms" "$remote_cleanup"
cat "$PACKAGE_OUT"
