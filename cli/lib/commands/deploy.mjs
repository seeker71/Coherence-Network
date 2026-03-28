/**
 * Deploy command: deploy latest main to VPS (coherencycoin.com)
 *
 * cc deploy         — deploy now (directly if SSH key available, otherwise via node message)
 * cc deploy status  — check what SHA is deployed vs origin/main
 */

import { get, post } from "../api.mjs";
import { existsSync } from "node:fs";
import { execSync } from "node:child_process";
import { homedir, hostname as getHostname } from "node:os";
import { join } from "node:path";

const SSH_KEY = join(homedir(), ".ssh", "hostinger-openclaw");
const VPS_HOST = "root@187.77.152.42";
const REPO_DIR = "/docker/coherence-network/repo";
const COMPOSE_DIR = "/docker/coherence-network";

function printDeployUsage() {
  console.log("Usage:");
  console.log("  cc deploy         Deploy latest main to the VPS");
  console.log("  cc deploy status  Show deployed SHA vs current health payload");
  console.log("  cc deploy --help  Show this help");
}

function ssh(cmd, timeout = 120000) {
  return execSync(
    `ssh -i "${SSH_KEY}" -o LogLevel=QUIET -o StrictHostKeyChecking=no ${VPS_HOST} '${cmd}'`,
    { encoding: "utf-8", timeout },
  ).trim();
}

function formatDeployError(error) {
  const raw = [
    error?.stderr?.toString?.() || "",
    error?.stdout?.toString?.() || "",
    error?.message || "",
  ].filter(Boolean).join("\n").trim();

  if (!raw) return "unknown deploy error";
  if (raw.includes("Operation not permitted")) {
    return "SSH blocked by the current environment (Operation not permitted).";
  }
  if (raw.includes("Could not resolve host")) {
    return "DNS resolution failed for the deploy target.";
  }
  if (raw.includes("fetch failed")) {
    return "Network fetch failed while checking deployment health.";
  }

  const compact = raw.replace(/\s+/g, " ").trim();
  return compact.length > 280 ? `${compact.slice(0, 277)}...` : compact;
}

export async function deploy(args) {
  const sub = args[0];
  if (sub === "--help" || sub === "-h" || sub === "help") {
    printDeployUsage();
    return;
  }
  if (sub === "status") return deployStatus();

  console.log("\x1b[1m  DEPLOYING TO VPS\x1b[0m");
  console.log(`  ${"─".repeat(50)}`);

  // If this machine has SSH key, deploy directly — don't send a message to yourself
  if (existsSync(SSH_KEY)) {
    return deployDirect();
  }

  // No SSH key — ask a node that has one to deploy
  return deployViaMessage();
}

async function deployDirect() {
  console.log("  Deploying directly (SSH key found)...");
  console.log();

  try {
    // 1. Capture current SHA
    const prevSha = ssh(`cd ${REPO_DIR} && git rev-parse --short HEAD`, 15000);
    console.log(`  Current VPS: ${prevSha}`);

    // 2. Git pull
    const pullOutput = ssh(`cd ${REPO_DIR} && git pull origin main --ff-only`, 30000);
    const newSha = ssh(`cd ${REPO_DIR} && git rev-parse --short HEAD`, 15000);

    if (newSha === prevSha) {
      console.log(`  \x1b[32m✓\x1b[0m VPS already up to date at ${newSha}`);
      await broadcast(`Deploy: VPS already at ${newSha}, no changes needed.`);
      return;
    }

    console.log(`  Pulled: ${prevSha} → ${newSha}`);

    // 3. Build + restart
    console.log("  Building containers (this may take a minute)...");
    ssh(`cd ${COMPOSE_DIR} && docker compose build --no-cache api web && docker compose up -d api web`, 300000);
    console.log("  Containers restarted, waiting 30s for health check...");

    // 4. Wait
    await new Promise((r) => setTimeout(r, 30000));

    // 5. Health check
    const health = await get("/api/health");
    if (health?.status === "ok" && health?.schema_ok) {
      console.log(`  \x1b[32m✓\x1b[0m Deploy successful: ${prevSha} → ${newSha}`);
      console.log(`  Health: OK | Schema: OK | Uptime: ${health.uptime_human || "?"}`);
      await broadcast(`Deploy successful: ${prevSha} → ${newSha}. Health OK, schema OK.`);
    } else {
      // Rollback
      console.log(`  \x1b[31m✗\x1b[0m Health check failed — rolling back to ${prevSha}`);
      ssh(`cd ${REPO_DIR} && git checkout ${prevSha} && cd ${COMPOSE_DIR} && docker compose build --no-cache api web && docker compose up -d api web`, 300000);
      console.log(`  Rolled back to ${prevSha}`);
      await broadcast(`Deploy FAILED health check. Rolled back ${newSha} → ${prevSha}.`);
    }
  } catch (e) {
    console.log(`  \x1b[31m✗\x1b[0m Deploy error: ${formatDeployError(e)}`);
  }
}

async function deployViaMessage() {
  console.log("  No SSH key on this machine — sending deploy command to a node that has one...");
  console.log();

  const nodes = await get("/api/federation/nodes");
  if (!nodes || !Array.isArray(nodes)) {
    console.log("  \x1b[31m✗\x1b[0m Could not fetch nodes");
    return;
  }

  // Find any node that might have SSH (prefer macOS)
  const target = nodes.find((n) => n.os_type === "macos") || nodes[0];
  if (!target) {
    console.log("  \x1b[31m✗\x1b[0m No nodes available");
    return;
  }

  const myNodeId = nodes.find((n) => n.hostname === getHostname())?.node_id || "cli-user";

  const result = await post(`/api/federation/nodes/${myNodeId}/messages`, {
    from_node: myNodeId,
    to_node: target.node_id,
    type: "command",
    text: "Deploy latest main to VPS",
    payload: { command: "deploy" },
  });

  if (result?.id) {
    console.log(`  \x1b[32m✓\x1b[0m Deploy command sent to ${target.hostname}`);
    console.log("  Node will deploy on next poll (~2 min). Check: cc deploy status");
  } else {
    console.log("  \x1b[31m✗\x1b[0m Failed to send deploy command");
  }
}

async function broadcast(text) {
  try {
    const nodes = await get("/api/federation/nodes");
    const myNodeId = nodes?.find((n) => n.hostname === getHostname())?.node_id || "deployer";
    await post(`/api/federation/broadcast`, {
      from_node: myNodeId,
      type: "deploy",
      text,
    });
  } catch { /* best effort */ }
}

async function deployStatus() {
  console.log("\x1b[1m  DEPLOY STATUS\x1b[0m");
  console.log(`  ${"─".repeat(50)}`);

  const health = await get("/api/health");
  if (!health) {
    console.log("  \x1b[31m✗\x1b[0m API unreachable");
    return;
  }

  const deployedSha = health.deployed_sha || "unknown";
  console.log(`  API:         ${health.status === "ok" ? "\x1b[32mok\x1b[0m" : "\x1b[31m" + health.status + "\x1b[0m"}`);
  console.log(`  Deployed:    ${deployedSha.slice(0, 10)}`);
  console.log(`  Schema:      ${health.schema_ok ? "\x1b[32m✓\x1b[0m" : "\x1b[31m✗\x1b[0m"}`);
  console.log(`  Uptime:      ${health.uptime_human || "?"}`);

  const nodes = await get("/api/federation/nodes");
  if (nodes && Array.isArray(nodes)) {
    console.log();
    console.log("  Node SHAs:");
    for (const n of nodes) {
      const git = n.capabilities?.git || {};
      const sha = (git.local_sha || "?").slice(0, 10);
      const match = sha === deployedSha.slice(0, 10) ? "\x1b[32m✓\x1b[0m" : "\x1b[33m≠\x1b[0m";
      console.log(`    ${match} ${(n.hostname || "?").padEnd(25)} ${sha}`);
    }
  }
}
