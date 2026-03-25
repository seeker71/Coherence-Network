/**
 * Deploy command: deploy latest main to VPS (coherencycoin.com)
 *
 * cc deploy         — deploy now (asks the Mac node to run the deploy)
 * cc deploy status  — check what SHA is deployed vs origin/main
 */

import { get, post } from "../api.mjs";

export async function deploy(args) {
  const sub = args[0];

  if (sub === "status") {
    return deployStatus();
  }

  // Deploy = send deploy command to the node that has SSH access to VPS
  // Any node with ~/.ssh/hostinger-openclaw can deploy
  console.log("\x1b[1m  DEPLOYING TO VPS\x1b[0m");
  console.log(`  ${"─".repeat(50)}`);
  console.log("  Sending deploy command to Mac node (has SSH key)...");
  console.log();

  // Find Mac node (the one with SSH access)
  const nodes = await get("/api/federation/nodes");
  if (!nodes || !Array.isArray(nodes)) {
    console.log("  \x1b[31m✗\x1b[0m Could not fetch nodes");
    return;
  }

  const macNode = nodes.find((n) => n.os_type === "macos");
  if (!macNode) {
    console.log("  \x1b[31m✗\x1b[0m No Mac node found (needed for SSH deploy)");
    return;
  }

  // Send deploy command
  const { hostname } = await import("node:os");
  const myNodeId = nodes.find((n) => n.hostname === hostname())?.node_id || "cli-user";

  const result = await post(`/api/federation/nodes/${myNodeId}/messages`, {
    from_node: myNodeId,
    to_node: macNode.node_id,
    type: "command",
    text: "Deploy latest main to VPS",
    payload: { command: "deploy" },
  });

  if (result?.id) {
    console.log(`  \x1b[32m✓\x1b[0m Deploy command sent to ${macNode.hostname}`);
    console.log(`  The Mac runner will: git pull → docker build → health check → rollback if failed`);
    console.log(`  Check \x1b[1mcc deploy status\x1b[0m in ~5 min to verify`);
  } else {
    console.log("  \x1b[31m✗\x1b[0m Failed to send deploy command");
  }
}

async function deployStatus() {
  console.log("\x1b[1m  DEPLOY STATUS\x1b[0m");
  console.log(`  ${"─".repeat(50)}`);

  // Check VPS health for deployed SHA
  const health = await get("/api/health");
  if (!health) {
    console.log("  \x1b[31m✗\x1b[0m API unreachable");
    return;
  }

  const deployedSha = health.deployed_sha || "unknown";
  const status = health.status;
  const schemaOk = health.schema_ok;
  const uptime = health.uptime_human || "?";

  console.log(`  API:         ${status === "ok" ? "\x1b[32mok\x1b[0m" : "\x1b[31m" + status + "\x1b[0m"}`);
  console.log(`  Deployed:    ${deployedSha.slice(0, 10)}`);
  console.log(`  Schema:      ${schemaOk ? "\x1b[32m✓\x1b[0m" : "\x1b[31m✗\x1b[0m"}`);
  console.log(`  Uptime:      ${uptime}`);

  // Compare with node SHAs
  const nodes = await get("/api/federation/nodes");
  if (nodes && Array.isArray(nodes)) {
    console.log();
    console.log("  Node SHAs:");
    for (const n of nodes) {
      const caps = n.capabilities || {};
      const git = caps.git || {};
      const sha = (git.local_sha || "?").slice(0, 10);
      const match = sha === deployedSha.slice(0, 10) ? "\x1b[32m✓\x1b[0m" : "\x1b[33m≠\x1b[0m";
      console.log(`    ${match} ${(n.hostname || "?").padEnd(25)} ${sha}`);
    }
  }
}
