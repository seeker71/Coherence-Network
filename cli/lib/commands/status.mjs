/**
 * Status commands: status, resonance
 */

import { get } from "../api.mjs";
import { getContributorId, getHubUrl, getFocus } from "../config.mjs";
import { hasJsonFlag, printJson, printJsonError } from "../ui/json.mjs";
import { hostname } from "node:os";
import { execSync } from "node:child_process";
import { stdin, stdout } from "node:process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import chalk from "chalk";
import boxen from "boxen";
import Table from "cli-table3";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

function getLocalVersion() {
  try {
    const pkg = JSON.parse(readFileSync(join(__dirname, "../../package.json"), "utf8"));
    return pkg.version;
  } catch { return "?"; }
}

async function checkForUpdate(localVersion) {
  try {
    const latest = execSync("npm view coherence-cli version", { encoding: "utf8", timeout: 5000 }).trim();
    if (latest && latest !== localVersion && localVersion !== "?") {
      return latest;
    }
  } catch {}
  return null;
}

export async function showStatus(args = []) {
  const isTTY = process.stdout.isTTY;
  const focus = getFocus();
  const jsonMode = hasJsonFlag(args);

  // Fetch everything in parallel
  const [health, ideas, nodes, pendingData, runningData, completedData, coherence, ledger, messages] =
    await Promise.all([
      get("/api/health"),
      get("/api/ideas/count"),
      get("/api/federation/nodes"),
      get("/api/agent/tasks", { status: "pending", limit: 100 }),
      get("/api/agent/tasks", { status: "running", limit: 100 }),
      get("/api/agent/tasks", { status: "completed", limit: 5 }),
      get("/api/coherence/score"),
      getContributorId() ? get(`/api/contributions/ledger/${encodeURIComponent(getContributorId())}`) : null,
      getContributorId() ? get(`/api/federation/nodes/${encodeURIComponent(getContributorId())}/messages`, { unread_only: true, limit: 10 }) : null,
    ]);

  // JSON mode — single structured payload covering every fetched source.
  // The shape is intentionally flat so jq filters can pull any field
  // without walking a deep tree.
  if (jsonMode) {
    const envelope = {
      hub: getHubUrl(),
      contributor_id: getContributorId(),
      focus: { idea_id: focus.idea_id, task_id: focus.task_id },
      health: health ?? null,
      ideas_count: ideas ?? null,
      nodes: Array.isArray(nodes) ? nodes : nodes?.items ?? null,
      coherence: coherence ?? null,
      tasks: {
        pending: pendingData ?? null,
        running: runningData ?? null,
        completed: completedData ?? null,
      },
      ledger: ledger ?? null,
      messages: messages ?? null,
    };
    // If every field is null, the API is likely unreachable.
    const allNull = [health, ideas, nodes, pendingData, runningData, completedData, coherence].every((v) => v == null);
    if (allNull) {
      printJsonError("api_unreachable", { status: 0 });
      return;
    }
    printJson(envelope);
    return;
  }

  const taskList = (d) => {
    if (!d) return [];
    if (Array.isArray(d)) return d;
    return d.tasks || [];
  };

  const pending = taskList(pendingData);
  const running = taskList(runningData);
  const completed = taskList(completedData);

  /** Extract a human-readable name from a task */
  function _taskName(t) {
    const ctx = t.context || {};
    if (ctx.idea_name) return ctx.idea_name.slice(0, 45);
    if (t.direction) {
      const match = t.direction.match(/for:\s*(.+?)[\.\n]/);
      if (match) return match[1].slice(0, 45);
      return t.direction.slice(0, 45);
    }
    return t.id?.slice(0, 20) || "?";
  }

  // --- Header & Focus ---
  if (isTTY) {
    let focusContent = "";
    if (focus.idea_id || focus.task_id) {
      if (focus.idea_id) focusContent += `${chalk.cyan.bold("FOCUS IDEA:")} ${focus.idea_id}\n`;
      if (focus.task_id) focusContent += `${chalk.magenta.bold("FOCUS TASK:")} ${focus.task_id}`;
    } else {
      focusContent = chalk.dim("No active focus. Use 'cc focus' to pick an idea.");
    }

    console.log(boxen(focusContent, {
      padding: 1,
      margin: { top: 1, bottom: 0 },
      borderStyle: 'round',
      borderColor: 'cyan',
      title: chalk.bold(' COHERENCE NETWORK '),
      titleAlignment: 'center'
    }));
  } else {
    console.log();
    console.log(chalk.bold("  COHERENCE NETWORK STATUS"));
    console.log(`  ${"─".repeat(50)}`);
    if (focus.idea_id) console.log(`  Focus Idea:  ${focus.idea_id}`);
    if (focus.task_id) console.log(`  Focus Task:  ${focus.task_id}`);
  }

  // --- Network Core ---
  if (isTTY) {
    const table = new Table({
      chars: { 'mid': '', 'left-mid': '', 'mid-mid': '', 'right-mid': '' },
      style: { 'padding-left': 2, 'padding-right': 2 }
    });

    // API Health
    let apiStatus = chalk.red("offline");
    if (health) {
      const schemaIcon = health.schema_ok === false ? chalk.red("✗") : chalk.green("✓");
      apiStatus = `${chalk.green(health.status)} (${health.version || "?"}) ${schemaIcon}`;
    }
    table.push([chalk.dim("API"), apiStatus]);

    // Coherence
    if (coherence && coherence.score != null) {
      const score = coherence.score.toFixed(2);
      const color = coherence.score >= 0.7 ? chalk.green : coherence.score >= 0.4 ? chalk.yellow : chalk.red;
      table.push([chalk.dim("Coherence"), `${color(score)} (${coherence.signals_with_data || 0}/${coherence.total_signals || 0} signals)`]);
    }

    table.push([chalk.dim("Hub"), getHubUrl()]);
    table.push([chalk.dim("Identity"), getContributorId() || chalk.dim("anonymous")]);

    // Ideas & Nodes summary
    if (ideas) {
      const byStatus = ideas.by_status || {};
      table.push([chalk.dim("Ideas"), `${ideas.total || 0} (${byStatus.validated || 0} validated)`]);
    }

    if (Array.isArray(nodes)) {
      const alive = nodes.filter(n => (Date.now() - new Date(n.last_seen_at || n.registered_at).getTime()) < 600_000);
      table.push([chalk.dim("Nodes"), `${nodes.length} registered (${alive.length} live)`]);
    }

    console.log(table.toString());
  } else {
    // API health
    if (health) {
      const schemaIcon = health.schema_ok === false ? "✗" : "✓";
      console.log(`  API:         ${health.status} (${health.version || "?"}) ${schemaIcon} schema`);
    } else {
      console.log(`  API:         offline`);
    }

    if (coherence && coherence.score != null) {
      console.log(`  Coherence:   ${coherence.score.toFixed(2)}`);
    }
    console.log(`  Hub:         ${getHubUrl()}`);
    console.log(`  Identity:    ${getContributorId() || "(anonymous)"}`);
  }

  // --- Pipeline ---
  console.log();
  console.log(chalk.bold("  PIPELINE"));
  console.log(chalk.dim(`  ${"─".repeat(50)}`));
  console.log(`  Pending:     ${pending.length}`);
  console.log(`  Running:     ${running.length}`);

  if (running.length > 0) {
    for (const t of running.slice(0, 3)) {
      const name = _taskName(t);
      const age = t.created_at ? Math.round((Date.now() - new Date(t.created_at).getTime()) / 60000) : 0;
      const ageColor = age > 15 ? chalk.red : age > 5 ? chalk.yellow : chalk.green;
      console.log(`    ${chalk.yellow("▸")} ${(t.task_type || "?").padEnd(6)} ${ageColor(age + "m")}  ${name}`);
    }
  }

  if (completed.length > 0) {
    console.log(`  Recent:      last ${completed.length} completed`);
    for (const t of completed.slice(0, 3)) {
      console.log(`    ${chalk.green("✓")} ${t.task_type || "?"}  ${_taskName(t)}`);
    }
  }

  // --- Ledger ---
  if (ledger && ledger.balance) {
    console.log();
    console.log(chalk.bold("  MY LEDGER"));
    console.log(chalk.dim(`  ${"─".repeat(50)}`));
    console.log(`  Total:       ${chalk.green(ledger.balance.grand_total || 0)} CC`);
  }

  // Messages
  if (messages && messages.count > 0) {
    console.log();
    console.log(chalk.yellow(`  📬 ${messages.count} unread message(s)`));
  }

  // Version check + auto-update
  const localVersion = getLocalVersion();
  const latestVersion = await checkForUpdate(localVersion);
  if (latestVersion) {
    console.log();
    console.log(chalk.yellow(`  Update available: ${localVersion} → ${latestVersion}`));
    // ... existing auto-update logic ...

    if (stdin.isTTY) {
      // Interactive — ask
      const { createInterface } = await import("node:readline/promises");
      const rl = createInterface({ input: stdin, output: stdout });
      const answer = await rl.question("  Update now? (Y/n): ");
      rl.close();
      if (!answer || answer.toLowerCase() === "y" || answer.toLowerCase() === "yes") {
        console.log(`  Updating to ${latestVersion}...`);
        try {
          execSync("npm i -g coherence-cli@latest", { stdio: "inherit", timeout: 60000 });
          console.log(`\x1b[32m  ✓ Updated to ${latestVersion}\x1b[0m`);
        } catch {
          console.log(`\x1b[31m  ✗ Update failed. Run manually: npm i -g coherence-cli@latest\x1b[0m`);
        }
      }
    } else {
      // Non-interactive — auto-update silently
      console.log(`  Auto-updating to ${latestVersion}...`);
      try {
        execSync("npm i -g coherence-cli@latest", { stdio: "pipe", timeout: 60000 });
        console.log(`\x1b[32m  ✓ Updated to ${latestVersion}\x1b[0m`);
      } catch {
        console.log(`\x1b[2m  Auto-update failed. Run: npm i -g coherence-cli@latest\x1b[0m`);
      }
    }
  }

  console.log();
}

export async function showResonance() {
  const data = await get("/api/ideas/resonance");
  if (!data) {
    console.log("Could not fetch resonance.");
    return;
  }
  console.log();
  console.log("\x1b[1m  RESONANCE\x1b[0m — what's alive right now");
  console.log(`  ${"─".repeat(40)}`);
  if (Array.isArray(data)) {
    for (const item of data.slice(0, 10)) {
      const name = item.name || item.idea_id || item.id || "?";
      console.log(`  \x1b[33m~\x1b[0m ${name}`);
    }
  } else if (typeof data === "object") {
    for (const [key, val] of Object.entries(data)) {
      console.log(`  ${key}: ${JSON.stringify(val)}`);
    }
  }
  console.log();
}
