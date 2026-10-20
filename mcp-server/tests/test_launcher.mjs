// Exercise the npm carrier as a real subprocess using isolated executable fixtures.
import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawn, spawnSync } from "node:child_process";
import { once } from "node:events";

const launcher = fileURLToPath(new URL("../index.mjs", import.meta.url));
const options = { skip: process.platform === "win32" };
function fixtures(t, programs) {
  const path = mkdtempSync(join(tmpdir(), "coherence launcher "));
  t.after(() => rmSync(path, { recursive: true, force: true }));
  for (const [name, source] of Object.entries(programs)) {
    writeFileSync(join(path, name), "#!" + process.execPath + "\n" + source, { mode: 0o755 });
  }
  return path;
}
function run(path, input = "") {
  return spawnSync(process.execPath, [launcher], {
    env: { ...process.env, PATH: path }, input, encoding: "utf8", timeout: 10000,
  });
}

test("uv child preserves protocol bytes and failure status without retry", options, (t) => {
  const path = fixtures(t, {
    uv: 'process.stdin.pipe(process.stdout); process.stdin.on("end", () => { process.stderr.write("child error\\n"); process.exitCode = 7; });',
    python3: 'process.stdout.write("unexpected retry");',
  });
  const result = run(path, '{"jsonrpc":"2.0"}\n');
  assert.equal(result.stdout, '{"jsonrpc":"2.0"}\n');
  assert.equal(result.status, 7);
  assert.match(result.stderr, /child error/);
});

test("missing uv uses Python with package cwd and forwards its exit", options, (t) => {
  const path = fixtures(t, {
    python3: 'process.stdout.write(JSON.stringify({args: process.argv.slice(2), cwd: process.cwd()})); process.exitCode = 23;',
  });
  const result = run(path);
  assert.equal(result.status, 23);
  assert.deepEqual(JSON.parse(result.stdout), {
    args: ["-m", "coherence_mcp_server"], cwd: resolve(launcher, ".."),
  });
  assert.match(result.stderr, /uv is unavailable/);
});

test("missing both runtimes reports failure on stderr only", options, (t) => {
  const result = run(fixtures(t, {}));
  assert.equal(result.status, 1);
  assert.equal(result.stdout, "");
  assert.match(result.stderr, /could not start python3/);
});

test("termination reaches the active fallback child", { ...options, timeout: 10000 }, async (t) => {
  const path = fixtures(t, {
    python3: 'process.on("SIGTERM", () => { process.stderr.write("stopped\\n"); process.exit(29); }); process.stdout.write("ready\\n"); setInterval(() => {}, 1000);',
  });
  const proc = spawn(process.execPath, [launcher], {
    env: { ...process.env, PATH: path }, stdio: ["pipe", "pipe", "pipe"],
  });
  t.after(() => proc.kill("SIGKILL"));
  let stderr = "";
  proc.stderr.on("data", (data) => { stderr += data; });
  await once(proc.stdout, "data");
  const closed = once(proc, "close");
  proc.kill("SIGTERM");
  const [code] = await closed;
  assert.equal(code, 29);
  assert.match(stderr, /stopped/);
});
