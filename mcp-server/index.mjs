#!/usr/bin/env node

// Existing npm-to-Python MCP carrier: preserve stdio, termination and failure.
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname } from "node:path";
import { constants } from "node:os";

const packageDirectory = dirname(fileURLToPath(import.meta.url));
let child;
let stopping = false;
const pythonRuntimes = process.platform === "win32"
  ? [["py", ["-3"]], ["python", []], ["python3", []]]
  : [["python3", []]];

function start(command, args, remaining = []) {
  child = spawn(command, args, { stdio: "inherit", cwd: packageDirectory, shell: false });
  let failedToSpawn = false;
  child.once("error", (error) => {
    failedToSpawn = true;
    if (remaining.length && error.code === "ENOENT" && !stopping) {
      const [[next, prefix], ...rest] = remaining;
      console.error(`Coherence MCP: ${command} is unavailable; trying ${next} with installed MCP dependencies.`);
      start(next, [...prefix, "-m", "coherence_mcp_server"], rest);
      return;
    }
    console.error(`Coherence MCP could not start ${command} (${error.code || "spawn error"}). Install uv or Python with coherence-mcp-server dependencies.`);
    process.exitCode = 1;
  });
  child.once("close", (code, signal) => {
    if (!failedToSpawn) process.exitCode = code ?? (128 + (constants.signals[signal] || 1));
  });
}

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => {
    stopping = true;
    if (child?.pid) child.kill(signal);
    else process.exitCode = 128 + constants.signals[signal];
  });
}

start("uv", ["run", "--locked", "--project", packageDirectory, "coherence-mcp-server"], pythonRuntimes);
