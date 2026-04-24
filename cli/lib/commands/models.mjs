/**
 * coh models — Model listing and routing management.
 *
 * Usage:
 *   coh models                              List all models by executor
 *   coh models routing                      Show task-type → tier mapping
 *   coh models set <executor> <type> <model> Override model for executor + task type
 *   coh usage                               Show automation usage overview
 *   coh usage alerts                        Show active usage alerts
 */

import { get, patch } from "../api.mjs";

// ── coh models ──────────────────────────────────────────────────────

export async function modelsCommand(args) {
  const sub = (args[0] || "").toLowerCase();

  if (!sub || sub === "list") {
    return listModels();
  }

  if (sub === "routing") {
    return showRouting();
  }

  if (sub === "set") {
    const executor = args[1];
    const taskType = args[2];
    const model = args[3];
    if (!executor || !taskType || !model) {
      console.log("\x1b[33m⚠\x1b[0m Usage: coh models set <executor> <task_type> <model>");
      return;
    }
    return setModelOverride(executor, taskType, model);
  }

  console.log("\x1b[33m⚠\x1b[0m Unknown subcommand. Use: coh models [list|routing|set]");
}

async function listModels() {
  const data = await get("/api/models");
  if (!data) {
    console.log("\x1b[31m✗\x1b[0m Could not fetch models.");
    return;
  }

  console.log();
  console.log(`  \x1b[1mCONFIGURED MODELS\x1b[0m  (${data.total} total)`);
  console.log(`  ${"─".repeat(50)}`);

  for (const [executor, entries] of Object.entries(data.executors || {})) {
    console.log(`\n  \x1b[36m${executor}\x1b[0m`);

    // Group by tier
    const byTier = {};
    for (const e of entries) {
      const t = e.tier || "default";
      if (!byTier[t]) byTier[t] = [];
      byTier[t].push(e.model_id);
    }

    for (const [tier, models] of Object.entries(byTier)) {
      const tierIcon = tier === "strong" ? "\x1b[32m▸\x1b[0m" :
                       tier === "fast" ? "\x1b[33m▸\x1b[0m" :
                       "\x1b[2m▸\x1b[0m";
      console.log(`    ${tierIcon} ${tier}`);
      for (const m of models) {
        console.log(`      \x1b[2m•\x1b[0m ${m}`);
      }
    }
  }
  console.log();
}

async function showRouting() {
  const data = await get("/api/models/routing");
  if (!data) {
    console.log("\x1b[31m✗\x1b[0m Could not fetch routing config.");
    return;
  }

  console.log();
  console.log(`  \x1b[1mTASK-TYPE → TIER MAPPING\x1b[0m`);
  console.log(`  ${"─".repeat(40)}`);

  const mapping = data.task_type_tier_mapping || {};
  for (const [taskType, tier] of Object.entries(mapping)) {
    const icon = tier === "strong" ? "\x1b[32m■\x1b[0m" : "\x1b[33m■\x1b[0m";
    console.log(`    ${icon} ${taskType.padEnd(16)} → ${tier}`);
  }

  const overrides = data.openrouter_task_overrides || {};
  if (Object.keys(overrides).length > 0) {
    console.log(`\n  \x1b[1mOPENROUTER TASK OVERRIDES\x1b[0m`);
    console.log(`  ${"─".repeat(40)}`);
    for (const [taskType, model] of Object.entries(overrides)) {
      console.log(`    \x1b[36m▸\x1b[0m ${taskType.padEnd(16)} → ${model}`);
    }
  }

  const fallbacks = data.fallback_chains || {};
  if (Object.keys(fallbacks).length > 0) {
    console.log(`\n  \x1b[1mFALLBACK CHAINS\x1b[0m`);
    console.log(`  ${"─".repeat(40)}`);
    for (const [executor, chain] of Object.entries(fallbacks)) {
      console.log(`    \x1b[36m${executor}\x1b[0m: ${chain.join(" → ")}`);
    }
  }

  console.log();
}

async function setModelOverride(executor, taskType, model) {
  // For openrouter, use the override mechanism
  let body;
  if (executor === "openrouter") {
    body = { openrouter_override_set: { [taskType]: model } };
  } else {
    // Add model to the executor's strong tier
    body = { executor_tier_add: { [executor]: { strong: [model] } } };
  }

  const data = await patch("/api/models/routing", body);
  if (!data) {
    console.log("\x1b[31m✗\x1b[0m Failed to update routing.");
    return;
  }

  console.log(`  \x1b[32m✓\x1b[0m Model routing updated: ${executor}/${taskType} → ${model}`);
}

// ── coh usage ───────────────────────────────────────────────────────

export async function usageCommand(args) {
  const sub = (args[0] || "").toLowerCase();

  if (sub === "alerts") {
    return showAlerts();
  }

  return showUsage();
}

async function showUsage() {
  const data = await get("/api/automation/usage", { compact: true });
  if (!data) {
    console.log("\x1b[31m✗\x1b[0m Could not fetch usage data.");
    return;
  }

  console.log();
  console.log(`  \x1b[1mAUTOMATION USAGE\x1b[0m`);
  console.log(`  ${"─".repeat(50)}`);

  // Display provider overviews
  const providers = data.providers || data.provider_overviews || [];
  if (Array.isArray(providers)) {
    for (const p of providers) {
      const name = p.provider || p.name || "?";
      const status = p.status || p.health || "unknown";
      const icon = status === "healthy" || status === "ok" ? "\x1b[32m●\x1b[0m" :
                   status === "warning" ? "\x1b[33m●\x1b[0m" :
                   "\x1b[31m●\x1b[0m";
      console.log(`\n  ${icon} \x1b[1m${name}\x1b[0m  (${status})`);
      if (p.requests_used != null && p.requests_limit != null) {
        const pct = Math.round((p.requests_used / p.requests_limit) * 100);
        console.log(`    Requests: ${p.requests_used}/${p.requests_limit} (${pct}%)`);
      }
      if (p.tokens_used != null) {
        console.log(`    Tokens: ${Number(p.tokens_used).toLocaleString()}`);
      }
      if (p.cost_usd != null) {
        console.log(`    Cost: $${Number(p.cost_usd).toFixed(4)}`);
      }
    }
  }

  // External tool usage
  const tools = data.external_tool_events || [];
  if (Array.isArray(tools) && tools.length > 0) {
    console.log(`\n  \x1b[1mEXTERNAL TOOLS\x1b[0m (last ${tools.length})`);
    for (const t of tools.slice(0, 5)) {
      console.log(`    \x1b[2m${t.tool || t.tool_name || "?"}\x1b[0m  ${t.operation || ""}  ${t.status || ""}`);
    }
  }

  console.log();
}

async function showAlerts() {
  const data = await get("/api/automation/usage/alerts");
  if (!data) {
    console.log("\x1b[31m✗\x1b[0m Could not fetch alerts.");
    return;
  }

  const alerts = data.alerts || data || [];
  if (!Array.isArray(alerts) || alerts.length === 0) {
    console.log("  \x1b[32m✓\x1b[0m No active usage alerts.");
    return;
  }

  console.log();
  console.log(`  \x1b[1mUSAGE ALERTS\x1b[0m  (${alerts.length})`);
  console.log(`  ${"─".repeat(40)}`);

  for (const a of alerts) {
    const severity = a.severity || a.level || "info";
    const icon = severity === "critical" ? "\x1b[31m!\x1b[0m" :
                 severity === "warning" ? "\x1b[33m!\x1b[0m" :
                 "\x1b[36mi\x1b[0m";
    console.log(`  ${icon} ${a.message || a.description || JSON.stringify(a)}`);
  }
  console.log();
}
