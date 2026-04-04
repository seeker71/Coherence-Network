/**
 * cc debug — Runtime debug mode toggle and diagnostics.
 *
 * Usage:
 *   cc debug            Show current debug status
 *   cc debug on         Enable debug mode (log level → DEBUG)
 *   cc debug off        Disable debug mode (log level → INFO)
 *   cc debug level <l>  Set log level (debug/info/warning/error)
 *   cc debug trace <ep> Add endpoint to trace list
 *   cc debug untrace <ep> Remove endpoint from trace list
 */

import { get, patch } from "../api.mjs";

export async function debugCommand(args) {
  const sub = (args[0] || "").toLowerCase();

  if (!sub || sub === "status") {
    return showStatus();
  }

  if (sub === "on") {
    return toggleDebug(true);
  }

  if (sub === "off") {
    return toggleDebug(false);
  }

  if (sub === "level") {
    const level = (args[1] || "").toUpperCase();
    if (!level) {
      console.log("\x1b[33m⚠\x1b[0m Usage: cc debug level <debug|info|warning|error>");
      return;
    }
    return setLevel(level);
  }

  if (sub === "trace") {
    const ep = args[1];
    if (!ep) {
      console.log("\x1b[33m⚠\x1b[0m Usage: cc debug trace <endpoint>");
      return;
    }
    return addTrace(ep);
  }

  if (sub === "untrace") {
    const ep = args[1];
    if (!ep) {
      console.log("\x1b[33m⚠\x1b[0m Usage: cc debug untrace <endpoint>");
      return;
    }
    return removeTrace(ep);
  }

  console.log("\x1b[33m⚠\x1b[0m Unknown subcommand. Use: cc debug [on|off|level|trace|untrace|status]");
}

async function showStatus() {
  const data = await get("/api/debug/status");
  if (!data) {
    console.log("\x1b[31m✗\x1b[0m Could not fetch debug status.");
    return;
  }

  const enabled = data.enabled;
  const icon = enabled ? "\x1b[32m●\x1b[0m" : "\x1b[2m○\x1b[0m";
  const state = enabled ? "\x1b[32mENABLED\x1b[0m" : "\x1b[2mDISABLED\x1b[0m";

  console.log();
  console.log(`  \x1b[1mDEBUG STATUS\x1b[0m`);
  console.log(`  ${"─".repeat(40)}`);
  console.log(`  ${icon} Debug mode:  ${state}`);
  console.log(`  Log level:     \x1b[36m${data.log_level}\x1b[0m`);
  console.log(`  Verbose SSE:   ${data.verbose_sse ? "\x1b[32myes\x1b[0m" : "\x1b[2mno\x1b[0m"}`);

  if (data.trace_endpoints && data.trace_endpoints.length > 0) {
    console.log(`  Tracing:`);
    for (const ep of data.trace_endpoints) {
      console.log(`    \x1b[36m→\x1b[0m ${ep}`);
    }
  } else {
    console.log(`  Tracing:       \x1b[2mnone\x1b[0m`);
  }
  console.log();
}

async function toggleDebug(enabled) {
  const data = await patch("/api/debug/status", { enabled });
  if (!data) {
    console.log("\x1b[31m✗\x1b[0m Failed to update debug status.");
    return;
  }
  const icon = enabled ? "\x1b[32m●\x1b[0m" : "\x1b[2m○\x1b[0m";
  const state = enabled ? "\x1b[32mON\x1b[0m" : "\x1b[2mOFF\x1b[0m";
  console.log(`  ${icon} Debug mode: ${state}  (log level: ${data.log_level})`);
}

async function setLevel(level) {
  const data = await patch("/api/debug/status", { log_level: level });
  if (!data) {
    console.log("\x1b[31m✗\x1b[0m Failed to set log level. Valid: DEBUG, INFO, WARNING, ERROR.");
    return;
  }
  console.log(`  \x1b[36m→\x1b[0m Log level set to \x1b[1m${data.log_level}\x1b[0m`);
}

async function addTrace(ep) {
  const data = await patch("/api/debug/status", { trace_endpoint_add: ep });
  if (!data) {
    console.log("\x1b[31m✗\x1b[0m Failed to add trace.");
    return;
  }
  console.log(`  \x1b[36m→\x1b[0m Tracing: ${data.trace_endpoints.join(", ")}`);
}

async function removeTrace(ep) {
  const data = await patch("/api/debug/status", { trace_endpoint_remove: ep });
  if (!data) {
    console.log("\x1b[31m✗\x1b[0m Failed to remove trace.");
    return;
  }
  console.log(`  \x1b[36m→\x1b[0m Tracing: ${data.trace_endpoints.length ? data.trace_endpoints.join(", ") : "none"}`);
}
