#!/usr/bin/env python3
"""Probe fatal HTTP replies across the current four kernel carriers.

The first two rows use the real persistent HTTP front doors:
  - form-kernel-rust serve
  - form-kernel-go serve

The TypeScript row uses the TS kernel + JS JIT under a tiny HTTP harness because
the TS carrier does not yet ship a persistent route-listener CLI. The fourth row
uses the Form-emitted server binary lane; today that net organ serves a static
program response, so the probe writes the trace file before emitting the fatal
response. Both limitations are printed in the row notes instead of hidden.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
FORM = ROOT / "form"
RUST_BIN = FORM / "form-kernel-rust" / "target" / "release" / "form-kernel-rust"
GO_BIN = FORM / "form-kernel-go" / "bin-go"


@dataclass
class ProbeResult:
    name: str
    command: list[str]
    reply: str
    note: str


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def wait_port(port: int, proc: subprocess.Popen[bytes], timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            err = proc.stderr.read().decode("utf-8", "replace") if proc.stderr else ""
            raise RuntimeError(f"server exited before listen: {err}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.03)
    raise TimeoutError(f"listener did not open on 127.0.0.1:{port}")


def raw_get(port: int, path: str = "/boom") -> str:
    req = (
        f"GET {path} HTTP/1.1\r\n"
        "Host: 127.0.0.1\r\n"
        "Connection: close\r\n"
        "\r\n"
    ).encode("ascii")
    with socket.create_connection(("127.0.0.1", port), timeout=5.0) as s:
        s.sendall(req)
        chunks: list[bytes] = []
        while True:
            chunk = s.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
    return b"".join(chunks).decode("utf-8", "replace")


def terminate(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=3)


def build_binaries() -> None:
    subprocess.run(["cargo", "build", "--release", "--quiet"], cwd=FORM / "form-kernel-rust", check=True)
    subprocess.run(["go", "build", "-o", "bin-go", "."], cwd=FORM / "form-kernel-go", check=True)


ROUTES_SOURCE = """
(defn route_boom (q) (form_error "as_str: Null"))
(defn route_ok (q) "ok")
(let routes (list
  (list "/boom" route_boom)
  (list "/ok" route_ok)))
"""


def probe_rust(work: Path) -> ProbeResult:
    port = free_port()
    routes = work / "rust-routes.fk"
    routes.write_text(ROUTES_SOURCE, encoding="utf-8")
    cmd = [str(RUST_BIN), "serve", "--port", str(port), "--workers", "1", "--routes", str(routes)]
    proc = subprocess.Popen(cmd, cwd=FORM, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        wait_port(port, proc)
        reply = raw_get(port)
        ok_reply = raw_get(port, "/ok")
        if "HTTP/1.1 200 OK" not in ok_reply or "\r\n\r\nok" not in ok_reply:
            raise RuntimeError(f"rust worker did not continue after fatal:\n{ok_reply}")
        return ProbeResult(
            "rust-serve",
            cmd,
            reply,
            "real form-kernel-rust serve route; /ok answered after /boom",
        )
    finally:
        terminate(proc)


def probe_go(work: Path) -> ProbeResult:
    port = free_port()
    routes = work / "go-routes.fk"
    routes.write_text(ROUTES_SOURCE, encoding="utf-8")
    cmd = [str(GO_BIN), "serve", "--port", str(port), str(routes)]
    proc = subprocess.Popen(cmd, cwd=FORM, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        wait_port(port, proc)
        reply = raw_get(port)
        ok_reply = raw_get(port, "/ok")
        if "200 OK" not in ok_reply or "\r\n\r\nok" not in ok_reply:
            raise RuntimeError(f"go worker did not continue after fatal:\n{ok_reply}")
        return ProbeResult(
            "go-serve",
            cmd,
            reply,
            "real form-kernel-go serve route; /ok answered after /boom",
        )
    finally:
        terminate(proc)


def probe_ts_jit(work: Path) -> ProbeResult:
    port = free_port()
    server = work / "ts-fatal-server.ts"
    kernel = json.dumps(str(FORM / "form-kernel-ts" / "src" / "kernel.ts"))
    reader = json.dumps(str(FORM / "form-kernel-ts" / "src" / "reader.ts"))
    compiler = json.dumps(str(FORM / "form-kernel-ts" / "src" / "compiler.ts"))
    trace_dir = json.dumps(str(ROOT / ".cache" / "form-kernel-ts"))
    server.write_text(
        f"""
import http from "node:http";
import {{ mkdirSync, writeFileSync }} from "node:fs";
import {{ join }} from "node:path";
import {{ Frame, Kernel, shutdownSocketWorker, walk }} from {kernel};
import {{ readAll }} from {reader};
import {{ compileNode }} from {compiler};

const port = Number(process.argv[2]);
const traceDir = {trace_dir};

function diagnose(message: string) {{
  if (message.includes("as_str") || message.toLowerCase().includes("string")) {{
    return {{
      fatal_kind: "type_contract_violation",
      likely_root_cause: "a Form/native recipe passed a non-string value to a string-only primitive",
      avoidance: "guard with value_kind/value-kind, convert with value_str, or use null-safe JSON constructors before calling string primitives",
    }};
  }}
  return {{
    fatal_kind: "kernel_panic",
    likely_root_cause: "the kernel crossed an unchecked host-language panic boundary",
    avoidance: "inspect the trace stack and source excerpt, then move the failing boundary into a checked fatal/error return",
  }};
}}

function writeTrace(message: string, stack: string | undefined, source: string) {{
  mkdirSync(traceDir, {{ recursive: true }});
  const path = join(traceDir, `crash-${{new Date().toISOString().replace(/[:.]/g, "")}}-${{process.pid}}.json`);
  const d = diagnose(message);
  writeFileSync(path, JSON.stringify({{
    when_utc: new Date().toISOString(),
    mode: "ts-jit-http-proof",
    fatal_kind: d.fatal_kind,
    fatal_message: message,
    likely_root_cause: d.likely_root_cause,
    avoidance: d.avoidance,
    source_label: "ts jit proof source",
    operation: "request=GET /boom route=/boom handler=route_boom jit_compile=1",
    source_head: source.slice(0, 2000),
    js_stack: stack ?? null,
  }}, null, 2) + "\\n");
  return path;
}}

function fatalBody(message: string, d: ReturnType<typeof diagnose>, trace: string) {{
  return `fatal[${{d.fatal_kind}}]: ${{message}}\\nlikely_root_cause: ${{d.likely_root_cause}}\\navoidance: ${{d.avoidance}}\\ntrace: ${{trace}}\\n`;
}}

function runBoom() {{
  const source = `(do
    (defn route_boom (q) (form_error "as_str: Null"))
    (let _jit (jit_compile "route_boom"))
    (route_boom (list)))`;
  const k = new Kernel();
  k.jitCompileHook = compileNode;
  const frame = new Frame(null);
  const root = readAll(k, source);
  try {{
    walk(k, root, frame);
  }} catch (err) {{
    const message = err instanceof Error ? err.message : String(err);
    const stack = err instanceof Error ? err.stack : undefined;
    const d = diagnose(message);
    const trace = writeTrace(message, stack, source);
    return {{ ok: false, message, diagnosis: d, trace }};
  }}
  return {{ ok: true }};
}}

const server = http.createServer((req, res) => {{
  if (req.url === "/ok") {{
    res.statusCode = 200;
    res.setHeader("X-Form-Router", "native-kernel-ts-jit");
    res.end("ok");
    return;
  }}
  const result = runBoom();
  if (result.ok) {{
    res.statusCode = 200;
    res.end("unexpected ok");
    return;
  }}
  res.statusCode = 500;
  res.setHeader("Content-Type", "text/plain; charset=utf-8");
  res.setHeader("Connection", "close");
  res.setHeader("X-Form-Router", "native-kernel-error");
  res.setHeader("X-Form-Fatal-Kind", result.diagnosis.fatal_kind);
  res.setHeader("X-Form-Crash-Trace", result.trace);
  res.setHeader("X-Form-JIT-Compile", "1");
  res.end(fatalBody(result.message, result.diagnosis, result.trace));
}});

server.listen(port, "127.0.0.1", () => {{
  process.stderr.write(`ts fatal proof listening on ${{port}}\\n`);
}});

process.on("SIGTERM", () => {{
  server.close(() => {{
    shutdownSocketWorker();
    process.exit(0);
  }});
}});
""",
        encoding="utf-8",
    )
    cmd = ["npx", "--yes", "tsx", str(server), str(port)]
    proc = subprocess.Popen(cmd, cwd=FORM / "form-kernel-ts", stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        wait_port(port, proc)
        reply = raw_get(port)
        ok_reply = raw_get(port, "/ok")
        if "200 OK" not in ok_reply or "\r\n\r\nok" not in ok_reply:
            raise RuntimeError(f"ts proof server did not continue after fatal:\n{ok_reply}")
        return ProbeResult(
            "typescript-jit-http-wrapper",
            cmd,
            reply,
            "TS kernel has no serve CLI yet; this wraps Kernel+compileNode JIT in HTTP and proves fatal envelope",
        )
    finally:
        terminate(proc)


def probe_fourth(work: Path) -> ProbeResult:
    if shutil.which("clang") is None:
        raise RuntimeError("clang is required for fourth-kernel HTTP proof")
    trace_dir = ROOT / ".cache" / "fourth-kernel"
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace_path = trace_dir / f"crash-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{os.getpid()}.json"
    trace_path.write_text(
        json.dumps(
            {
                "when_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "mode": "fourth-kernel-static-http-proof",
                "fatal_kind": "kernel_panic",
                "fatal_message": "fourth-kernel fatal proof responder",
                "likely_root_cause": "the fourth HTTP organ is a static responder today; dynamic route panic capture is still the next API-host slice",
                "avoidance": "move request-line parsing, route dispatch, and fatal capture into the fourth-kernel API host before counting it as dynamic route parity",
                "source_label": "fourth-walker-emit.fk fkc-emit-server",
                "operation": "request=GET /boom static fatal responder",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    response = (
        "HTTP/1.0 500 Internal Server Error\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        "Connection: close\r\n"
        "X-Form-Router: fourth-kernel-error\r\n"
        "X-Form-Fatal-Kind: kernel_panic\r\n"
        f"X-Form-Crash-Trace: {trace_path}\r\n"
        "\r\n"
        "fatal[kernel_panic]: fourth-kernel fatal proof responder\n"
        "likely_root_cause: the fourth HTTP organ is a static responder today; dynamic route panic capture is still the next API-host slice\n"
        "avoidance: move request-line parsing, route dispatch, and fatal capture into the fourth-kernel API host before counting it as dynamic route parity\n"
        f"trace: {trace_path}\n"
    )
    driver = work / "fourth-server-driver.fk"
    driver.write_text(
        (FORM / "form-stdlib" / "minimal-surface.fk").read_text(encoding="utf-8")
        + (FORM / "form-stdlib" / "fourth-walker.fk").read_text(encoding="utf-8")
        + (FORM / "form-stdlib" / "fourth-walker-emit.fk").read_text(encoding="utf-8")
        + "\n"
        + f'(let resp (fkresp {sexp_string(response)}))\n'
        + '(print "==SRV==")\n'
        + '(print (fkc-emit-server (list resp)))\n'
        + '(print "==END==")\n',
        encoding="utf-8",
    )
    emit = subprocess.run([str(GO_BIN), str(driver)], cwd=FORM, check=True, capture_output=True, text=True)
    c_path = work / "fourth-api.c"
    in_block = False
    lines: list[str] = []
    for line in emit.stdout.splitlines():
        if line == "==SRV==":
            in_block = True
            continue
        if line == "==END==":
            break
        if in_block:
            lines.append(line)
    c_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    bin_path = work / "fourth-api"
    subprocess.run(["clang", "-O2", "-o", str(bin_path), str(c_path)], check=True)
    port = free_port()
    cmd = [str(bin_path), str(port)]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        wait_port(port, proc)
        reply = raw_get(port)
        return ProbeResult(
            "fourth-kernel-emitted-http",
            cmd,
            reply,
            "Form-emitted HTTP binary; static fatal responder until fourth API-host routing lands",
        )
    finally:
        terminate(proc)


def sexp_string(value: str) -> str:
    return json.dumps(value)


def compact_reply(reply: str) -> str:
    head, sep, body = reply.partition("\r\n\r\n")
    interesting = []
    for line in head.splitlines():
        lower = line.lower()
        if (
            line.startswith("HTTP/")
            or lower.startswith("x-form-router:")
            or lower.startswith("x-form-fatal-kind:")
            or lower.startswith("x-form-crash-trace:")
            or lower.startswith("x-form-jit-compile:")
            or lower.startswith("content-type:")
            or lower.startswith("connection:")
        ):
            interesting.append(line)
    return "\n".join(interesting) + (sep.replace("\r\n", "\n") if sep else "\n\n") + body


def main() -> int:
    build_binaries()
    results: list[ProbeResult] = []
    with tempfile.TemporaryDirectory(prefix="fatal-http-kernels-") as tmp:
        work = Path(tmp)
        for probe in (probe_rust, probe_go, probe_ts_jit, probe_fourth):
            results.append(probe(work))
    print("fatal HTTP replies across kernel carriers")
    for result in results:
        print(f"\n## {result.name}")
        print("note:", result.note)
        print("command:", " ".join(result.command))
        print(compact_reply(result.reply).rstrip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
