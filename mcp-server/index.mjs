#!/usr/bin/env node

/**
 * Coherence Network MCP Server — Bridge
 * 
 * This is a lightweight Node.js wrapper that executes the Python-based 
 * MCP server. It ensures that 'npx coherence-mcp-server' continues to 
 * work while the primary implementation is centralized in Python.
 */

import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));

function main() {
  // Use uvx if available, otherwise fallback to python3
  const args = ["run", "coherence-mcp-server"];
  const options = {
    stdio: "inherit",
    shell: true,
    cwd: __dirname
  };

  // Check if we are running in a context where we should use the local package
  // instead of 'uvx' (which fetches from PyPI).
  const pythonServer = spawn("uv", args, options);

  pythonServer.on("error", (err) => {
    if (err.code === 'ENOENT') {
      // Fallback to python3 if 'uv' is not installed
      console.error("Warning: 'uv' not found. Falling back to 'python3'.");
      spawn("python3", ["-m", "coherence_mcp_server"], options);
    } else {
      console.error("Failed to start Python MCP server:", err);
      process.exit(1);
    }
  });

  // Handle termination
  process.on("SIGINT", () => pythonServer.kill("SIGINT"));
  process.on("SIGTERM", () => pythonServer.kill("SIGTERM"));
}

main();
