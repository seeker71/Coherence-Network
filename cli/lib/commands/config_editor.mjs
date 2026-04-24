import { createInterface } from "node:readline/promises";
import { stdin, stdout } from "node:process";

import { request } from "../api.mjs";
import {
  CONFIG_FILE,
  getAdminKey,
  getConfigValue,
  loadConfig,
  saveConfig,
  setConfigValue,
  unsetConfigValue,
} from "../config.mjs";

const REMOTE_FIELD_MAP = {
  "server.environment": { field: "server_environment", label: "Environment", type: "string" },
  "database.url": { field: "database_url", label: "Database URL", type: "string" },
  "cors.allowed_origins": { field: "cors_allowed_origins", label: "CORS origins", type: "list" },
  "agent_providers.api_base_url": { field: "api_base_url", label: "API base URL", type: "string" },
  "agent_providers.web_ui_base_url": { field: "web_ui_base_url", label: "Web UI base URL", type: "string" },
  "agent_executor.execute_token": {
    field: "execute_token",
    clearField: "clear_execute_token",
    label: "Execute token",
    type: "secret",
  },
  "agent_executor.execute_token_allow_unauth": {
    field: "execute_token_allow_unauth",
    label: "Allow unauth execute token",
    type: "boolean",
  },
  "telegram.bot_token": {
    field: "telegram_bot_token",
    clearField: "clear_telegram_bot_token",
    label: "Telegram bot token",
    type: "secret",
  },
  "telegram.chat_ids": { field: "telegram_chat_ids", label: "Telegram chat IDs", type: "list" },
  "agent_tasks.task_log_dir": { field: "task_log_dir", label: "Task log dir", type: "string" },
  "runtime.events_path": { field: "runtime_events_path", label: "Runtime events path", type: "string" },
  "friction.events_path": { field: "friction_events_path", label: "Friction events path", type: "string" },
  "live_updates.poll_ms": { field: "live_updates_poll_ms", label: "Live updates poll ms", type: "number" },
  "live_updates.router_refresh_every_ticks": {
    field: "live_updates_router_refresh_every_ticks",
    label: "Live updates refresh ticks",
    type: "number",
  },
  "live_updates.global": { field: "live_updates_global", label: "Live updates global", type: "boolean" },
  "runtime_beacon.sample_rate": { field: "runtime_beacon_sample_rate", label: "Runtime beacon sample rate", type: "number" },
  "health_proxy.failure_threshold": {
    field: "health_proxy_failure_threshold",
    label: "Health proxy failure threshold",
    type: "number",
  },
  "health_proxy.cooldown_ms": {
    field: "health_proxy_cooldown_ms",
    label: "Health proxy cooldown ms",
    type: "number",
  },
  "cli.provider": { field: "cli_provider", label: "CLI provider", type: "string" },
  "cli.active_task_id": { field: "cli_active_task_id", label: "CLI active task", type: "string" },
};

function parseFlags(args) {
  const positional = [];
  let adminKey = null;
  let local = false;
  let jsonMode = false;

  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--local") {
      local = true;
      continue;
    }
    if (arg === "--json") {
      jsonMode = true;
      continue;
    }
    if (arg === "--admin-key") {
      adminKey = args[index + 1] || "";
      index += 1;
      continue;
    }
    positional.push(arg);
  }

  return { positional, adminKey, local, jsonMode };
}

function normalizeList(value) {
  if (Array.isArray(value)) {
    return value.map((item) => String(item).trim()).filter(Boolean);
  }
  return String(value || "")
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseBoolean(value) {
  const normalized = String(value || "").trim().toLowerCase();
  if (["1", "true", "yes", "y", "on"].includes(normalized)) return true;
  if (["0", "false", "no", "n", "off"].includes(normalized)) return false;
  throw new Error(`Could not parse boolean value: ${value}`);
}

function coerceLocalValue(path, rawValue) {
  if (path === "cors.allowed_origins" || path === "telegram.chat_ids") {
    return normalizeList(rawValue);
  }
  if (path === "agent_executor.execute_token_allow_unauth") {
    return parseBoolean(rawValue);
  }
  if (
    path === "live_updates.global"
    || path === "agent_executor.execute_token_allow_unauth"
  ) {
    return parseBoolean(rawValue);
  }
  if (
    path === "live_updates.poll_ms"
    || path === "live_updates.router_refresh_every_ticks"
    || path === "health_proxy.failure_threshold"
    || path === "health_proxy.cooldown_ms"
  ) {
    return Number.parseInt(String(rawValue), 10);
  }
  if (path === "runtime_beacon.sample_rate") {
    return Number.parseFloat(String(rawValue));
  }
  return String(rawValue);
}

function printLocalConfig(config, { jsonMode = false } = {}) {
  if (jsonMode) {
    console.log(JSON.stringify({ config_path: CONFIG_FILE, fields: config }, null, 2));
    return;
  }
  console.log();
  console.log(`\x1b[1m  LOCAL CONFIG\x1b[0m`);
  console.log(`  ${"─".repeat(64)}`);
  console.log(`  Path: ${CONFIG_FILE}`);
  for (const [key, value] of Object.entries(config)) {
    console.log(`  ${key}: ${JSON.stringify(value)}`);
  }
  console.log();
}

async function fetchRemoteConfig(adminKey) {
  const response = await request("GET", "/api/agent/diagnostics/config-editor", {
    headers: { "X-Admin-Key": adminKey },
  });
  if (!response.ok) {
    const detail = response.json?.detail || response.text || `HTTP ${response.status}`;
    throw new Error(`Config editor request failed: ${detail}`);
  }
  return response.json;
}

async function patchRemoteConfig(adminKey, payload) {
  const response = await request("PATCH", "/api/agent/diagnostics/config-editor", {
    headers: { "X-Admin-Key": adminKey },
    body: payload,
  });
  if (!response.ok) {
    const detail = response.json?.detail || response.text || `HTTP ${response.status}`;
    throw new Error(`Config save failed: ${detail}`);
  }
  return response.json;
}

function printRemoteConfig(payload, { jsonMode = false } = {}) {
  if (jsonMode) {
    console.log(JSON.stringify(payload, null, 2));
    return;
  }
  const fields = payload.fields || {};
  console.log();
  console.log(`\x1b[1m  REMOTE CONFIG\x1b[0m`);
  console.log(`  ${"─".repeat(64)}`);
  console.log(`  Path: ${payload.config_path}`);
  console.log(`  Environment: ${fields.server_environment}`);
  console.log(`  Database URL: ${fields.database_url}`);
  console.log(`  API base URL: ${fields.api_base_url}`);
  console.log(`  Web UI base URL: ${fields.web_ui_base_url}`);
  console.log(`  CORS origins: ${(fields.cors_allowed_origins || []).join(", ") || "none"}`);
  console.log(`  Execute token: ${fields.execute_token_configured ? "configured" : "not configured"}`);
  console.log(`  Execute allow unauth: ${fields.execute_token_allow_unauth ? "true" : "false"}`);
  console.log(`  Telegram bot token: ${fields.telegram_bot_token_configured ? "configured" : "not configured"}`);
  console.log(`  Telegram chat IDs: ${(fields.telegram_chat_ids || []).join(", ") || "none"}`);
  console.log(`  Task log dir: ${fields.task_log_dir || "n/a"}`);
  console.log(`  Runtime events path: ${fields.runtime_events_path || "n/a"}`);
  console.log(`  Friction events path: ${fields.friction_events_path || "n/a"}`);
  console.log(`  Live updates poll ms: ${fields.live_updates_poll_ms ?? "n/a"}`);
  console.log(`  Live updates refresh ticks: ${fields.live_updates_router_refresh_every_ticks ?? "n/a"}`);
  console.log(`  Live updates global: ${fields.live_updates_global ? "true" : "false"}`);
  console.log(`  Runtime beacon sample rate: ${fields.runtime_beacon_sample_rate ?? "n/a"}`);
  console.log(`  Health proxy failure threshold: ${fields.health_proxy_failure_threshold ?? "n/a"}`);
  console.log(`  Health proxy cooldown ms: ${fields.health_proxy_cooldown_ms ?? "n/a"}`);
  console.log(`  CLI provider: ${fields.cli_provider || "n/a"}`);
  console.log(`  CLI active task: ${fields.cli_active_task_id || "n/a"}`);
  console.log();
}

function resolveAdminKey(flagValue) {
  const adminKey = String(flagValue || getAdminKey() || "").trim();
  if (!adminKey) {
    throw new Error("Admin key is required. Set auth.admin_key in ~/.coherence-network/config.json or pass --admin-key.");
  }
  return adminKey;
}

export async function showConfigCommand(args = []) {
  const { local, jsonMode, adminKey } = parseFlags(args);
  if (local) {
    printLocalConfig(loadConfig(), { jsonMode });
    return;
  }
  const payload = await fetchRemoteConfig(resolveAdminKey(adminKey));
  printRemoteConfig(payload, { jsonMode });
}

export async function setConfigCommand(args = []) {
  const { positional, local, adminKey } = parseFlags(args);
  const [path, ...valueParts] = positional;
  const value = valueParts.join(" ");
  if (!path || !valueParts.length) {
    console.log("Usage: coh config set <path> <value> [--local] [--admin-key <key>]");
    return;
  }

  if (local) {
    setConfigValue(path, coerceLocalValue(path, value));
    console.log(`\x1b[32m✓\x1b[0m Updated ${path} in ${CONFIG_FILE}`);
    return;
  }

  const mapping = REMOTE_FIELD_MAP[path];
  if (!mapping) {
    console.log(`Unsupported remote config path: ${path}`);
    return;
  }

  let payload;
  if (mapping.type === "list") payload = { [mapping.field]: normalizeList(value) };
  else if (mapping.type === "boolean") payload = { [mapping.field]: parseBoolean(value) };
  else if (mapping.type === "number") payload = { [mapping.field]: Number(value) };
  else payload = { [mapping.field]: value };

  const result = await patchRemoteConfig(resolveAdminKey(adminKey), payload);
  console.log(`\x1b[32m✓\x1b[0m Updated ${path} on ${result.config_path}`);
}

export async function unsetConfigCommand(args = []) {
  const { positional, local, adminKey } = parseFlags(args);
  const [path] = positional;
  if (!path) {
    console.log("Usage: coh config unset <path> [--local] [--admin-key <key>]");
    return;
  }

  if (local) {
    unsetConfigValue(path);
    console.log(`\x1b[32m✓\x1b[0m Removed ${path} from ${CONFIG_FILE}`);
    return;
  }

  const mapping = REMOTE_FIELD_MAP[path];
  if (!mapping) {
    console.log(`Unsupported remote config path: ${path}`);
    return;
  }

  const payload = {};
  if (mapping.clearField) {
    payload[mapping.clearField] = true;
  } else if (mapping.type === "list") {
    payload[mapping.field] = [];
  } else if (mapping.type === "string" && path !== "database.url" && path !== "server.environment") {
    payload[mapping.field] = "";
  } else {
    console.log(`Remote unset is not supported for ${path}. Use coh config set instead.`);
    return;
  }

  const result = await patchRemoteConfig(resolveAdminKey(adminKey), payload);
  console.log(`\x1b[32m✓\x1b[0m Cleared ${path} on ${result.config_path}`);
}

async function promptValue(rl, label, currentValue, options = {}) {
  const preview = options.secret
    ? currentValue
      ? "[configured]"
      : "[not configured]"
    : `[${currentValue}]`;
  const answer = (await rl.question(`${label} ${preview}: `)).trim();
  if (!answer) return { action: "keep" };
  if (options.secret && answer === "-") return { action: "clear" };
  return { action: "set", value: answer };
}

export async function editConfigCommand(args = []) {
  const { local, adminKey: flagAdminKey } = parseFlags(args);
  const rl = createInterface({ input: stdin, output: stdout });

  try {
    if (local) {
      const current = loadConfig();
      console.log(`Editing local config at ${CONFIG_FILE}`);
      const hub = await promptValue(rl, "hub_url", current.hub_url || "");
      if (hub.action === "set") {
        setConfigValue("hub_url", hub.value);
      }
      const contributor = await promptValue(rl, "contributor_id", current.contributor_id || "");
      if (contributor.action === "set") {
        setConfigValue("contributor_id", contributor.value);
      }
      const admin = await promptValue(rl, "auth.admin_key", current.auth?.admin_key || "", { secret: true });
      if (admin.action === "set") {
        saveConfig({ auth: { ...(loadConfig().auth || {}), admin_key: admin.value } });
      }
      if (admin.action === "clear") {
        unsetConfigValue("auth.admin_key");
      }
      console.log(`\x1b[32m✓\x1b[0m Local config updated at ${CONFIG_FILE}`);
      return;
    }

    let adminKey = String(flagAdminKey || getAdminKey() || "").trim();
    if (!adminKey) {
      adminKey = (await rl.question("Admin key: ")).trim();
    }
    const payload = await fetchRemoteConfig(resolveAdminKey(adminKey));
    const fields = payload.fields || {};
    const updates = {};

    const environment = await promptValue(rl, "server.environment", fields.server_environment || "development");
    if (environment.action === "set") updates.server_environment = environment.value;
    const databaseUrl = await promptValue(rl, "database.url", fields.database_url || "");
    if (databaseUrl.action === "set") updates.database_url = databaseUrl.value;
    const apiBase = await promptValue(rl, "agent_providers.api_base_url", fields.api_base_url || "");
    if (apiBase.action === "set") updates.api_base_url = apiBase.value;
    const webUi = await promptValue(rl, "agent_providers.web_ui_base_url", fields.web_ui_base_url || "");
    if (webUi.action === "set") updates.web_ui_base_url = webUi.value;
    const cors = await promptValue(rl, "cors.allowed_origins (comma or newline list)", (fields.cors_allowed_origins || []).join(", "));
    if (cors.action === "set") updates.cors_allowed_origins = normalizeList(cors.value);
    const executeToken = await promptValue(rl, "agent_executor.execute_token", fields.execute_token_configured, { secret: true });
    if (executeToken.action === "set") updates.execute_token = executeToken.value;
    if (executeToken.action === "clear") updates.clear_execute_token = true;
    const allowUnauth = await promptValue(
      rl,
      "agent_executor.execute_token_allow_unauth",
      fields.execute_token_allow_unauth ? "true" : "false",
    );
    if (allowUnauth.action === "set") updates.execute_token_allow_unauth = parseBoolean(allowUnauth.value);
    const telegramToken = await promptValue(rl, "telegram.bot_token", fields.telegram_bot_token_configured, { secret: true });
    if (telegramToken.action === "set") updates.telegram_bot_token = telegramToken.value;
    if (telegramToken.action === "clear") updates.clear_telegram_bot_token = true;
    const telegramChats = await promptValue(rl, "telegram.chat_ids (comma or newline list)", (fields.telegram_chat_ids || []).join(", "));
    if (telegramChats.action === "set") updates.telegram_chat_ids = normalizeList(telegramChats.value);
    const taskLogDir = await promptValue(rl, "agent_tasks.task_log_dir", fields.task_log_dir || "");
    if (taskLogDir.action === "set") updates.task_log_dir = taskLogDir.value;
    const runtimePath = await promptValue(rl, "runtime.events_path", fields.runtime_events_path || "");
    if (runtimePath.action === "set") updates.runtime_events_path = runtimePath.value;
    const frictionPath = await promptValue(rl, "friction.events_path", fields.friction_events_path || "");
    if (frictionPath.action === "set") updates.friction_events_path = frictionPath.value;

    if (!Object.keys(updates).length) {
      console.log("No changes submitted.");
      return;
    }

    const confirm = (await rl.question("Save these changes? [y/N]: ")).trim().toLowerCase();
    if (!["y", "yes"].includes(confirm)) {
      console.log("Cancelled.");
      return;
    }

    const result = await patchRemoteConfig(resolveAdminKey(adminKey), updates);
    console.log(`\x1b[32m✓\x1b[0m Saved ${result.config_path}`);
  } finally {
    rl.close();
  }
}

export async function handleConfig(args = []) {
  const sub = args[0] || "show";
  const subArgs = args.slice(1);
  switch (sub) {
    case "show":
      return showConfigCommand(subArgs);
    case "set":
      return setConfigCommand(subArgs);
    case "unset":
      return unsetConfigCommand(subArgs);
    case "edit":
      return editConfigCommand(subArgs);
    default:
      console.log("Usage: coh config <show|set|unset|edit> [args]");
  }
}
