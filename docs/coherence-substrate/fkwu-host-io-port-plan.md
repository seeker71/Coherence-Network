# fkwu host-io: Windows 11 port + HTTP client methods — turn-key plan

Companion to [`fourth-arm-substrate-carriers.form`](fourth-arm-substrate-carriers.form).
Scopes the two host-io asks that are **not** shippable-and-verifiable from the
current Linux container, with every edit point identified so the next cell (or a
Windows host) can execute without re-discovery.

## Status (2026-06-19)

Shipped + proven this arc (Linux + macOS, byte-identical Darwin fallback):
- File read/write/append/mtime — portable open flags (`#include <fcntl.h>`, O_* macros). Four-way: hostio-observation 63, write-file-text 1111, file-append 11111, hostio-roundtrip 111.
- Socket **server** bind/listen/accept — portable `sockaddr` + setsockopt (`FK_SOL_SOCKET`/`FK_SO_REUSEADDR`/`FK_SA_B0`/`FK_SA_B1`). Verified: emitted server binds+listens on Linux.
- HTTP client **GET** (tag 105) — already portable (`getaddrinfo`).

This doc scopes: **(A) Windows 11**, **(B) HTTP client methods**.

## A. Windows 11 — scope + defer (no unverified code until a Windows host/CI gates it)

There is no Windows toolchain in the dev container (no mingw / cl / wine), so any
Windows code is unverifiable here. All Windows shims go in
`form/form-stdlib/hati-os-kernel-emit.fk`, **`_WIN32`-guarded** so Linux/macOS
emit is untouched (zero regression by construction, as with the Darwin fallback).

1. **File I/O** (tags 55–63, 104, 107): map POSIX → MSVCRT — `open/read/write/close/lseek` → `_open/_read/_write/_close/_lseeki64` (`<io.h>`), add `O_BINARY`; `mkdir(p,mode)` → `_mkdir(p)` (no mode arg); `unlink`→`_unlink`, `rmdir`→`_rmdir`; `file_mtime` via `_stat64`. `<fcntl.h>` already included provides O_* on MinGW.
2. **Sockets** (client tag 105 + server): `#include <winsock2.h> <ws2tcpip.h>`; `WSAStartup` once at process entry; `closesocket()` not `close()`; `SOCKET` type not `int`; `getaddrinfo` lives in ws2tcpip. The existing `FK_SOL_SOCKET`/`FK_SO_REUSEADDR` and `FK_SA_B0/B1` `#define` blocks just need a `_WIN32` branch — and conveniently Winsock `SOL_SOCKET`=0xffff/`SO_REUSEADDR`=4 match the Darwin values, while `sockaddr_in` has the 2-byte `sin_family` (no `sin_len`) matching the Linux values (`FK_SA_B0/B1` = 2/0).
3. **Server fork model — the hard blocker.** `fkc-server-main-text` / `fkc-main-server-universal-text` use `fork()`-per-connection. Windows has no `fork()`. This is a real rewrite, not a `#define`: `_beginthreadex`/`CreateThread` per accepted connection, or a single-threaded accept loop. Scope this as its own change.
4. **Build/CI target.** Go cross-compiles (`GOOS=windows GOARCH=amd64`); Rust adds `x86_64-pc-windows-gnu`; TS runs on Node (cross-platform). The emitted C needs MinGW/MSVC. **Gate:** a GitHub Actions `windows-latest` job that builds + runs the host-io bands (`hostio-roundtrip`, `hostio-observation`, `write-file-text`, `file-append`) — they must cross on Windows what they cross on Linux/macOS. **Windows host-io is not claimed until that job is green.**

## B. HTTP client methods (POST / PUT / DELETE / OPTIONS / any `*`) — one general `http_request`

**Design:** `http_request(method, url, body)`. The method is just a string in the
request line (`"%s %s HTTP/1.0\r\n..."`), so POST/PUT/DELETE/OPTIONS **and any
custom method** fall out for free. Auto `Content-Length` + `Content-Type:
application/json` when a body is present. Arity 3 fits the 4-column node table;
**tag 114** is free.

This is a **four-kernel** feature (http_get already exists in all four), and the
**Go kernel does the flattening** — so it must register the op even to run on fkwu
via a table (discovered the hard way: a fkwu-only op panics the Go flattener with
`trivialValue: ... is composite`). Edit points:

1. `form/form-stdlib/form-flatten.fk` — op-list `(list "http_request" 3 114)` + add to the `flt-do-let-effect-op` recognizer. *(drafted)*
2. `form/form-stdlib/hati-os-kernel-emit.fk` — `fk_http_request_native(method, url, body)` (mirror `fk_http_get_plain` + method in the request line + `Content-Length`/body append) and a tag-114 dispatch arm. *(drafted — compiles clean, no regression; http:// path; https pending)*
3. `form/form-kernel-go/server.go` — `registerNative("http_request", ...)` + an `externalHTTPRequestValue(method,url,body)` mirroring `externalHTTPGetValue` (net/http). **Required even to flatten+run on fkwu.**
4. `form/form-kernel-rust/src/main.rs` + `form/form-kernel-ts/src/kernel.ts` — equivalents for execution parity on those kernels.

**Test path** (once Go + fkwu land): local http echo server → flatten a `(do (_get (http_request "POST" "http://127.0.0.1:PORT/p" "body") "status_code"))` band through the Go kernel (`fks-table-file` via the `FOURTH_CHAIN` flatten driver) → run `$FKWU table 0` → assert the echo server logged method+body and fkwu returned the status. (The plain-http path was drafted and compiles; the table run needs step 3 first.)

**Honest lanes:**
- **HTTPS POST** needs the same method/body generalization inside `fk_https_get_ssl` (the dlopen'd openssl path) — a second increment. The nanite's mesh POST is HTTPS, so it needs this before going fully Form-native.
- HTTP request/response bytes are **environmental** (carrier-witnessed), not four-way value-proven. The four-kernel parity here is that the **op exists** and the **request construction agrees** across kernels, not that a live response is byte-identical.
