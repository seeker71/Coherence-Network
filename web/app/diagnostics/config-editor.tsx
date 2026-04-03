"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { getApiBase } from "@/lib/api";

type ConfigEditorFields = {
  server_environment: string;
  database_url: string;
  cors_allowed_origins: string[];
  api_base_url: string;
  web_ui_base_url: string;
  execute_token_configured: boolean;
  execute_token_allow_unauth: boolean;
  telegram_bot_token_configured: boolean;
  telegram_chat_ids: string[];
  task_log_dir: string;
  runtime_events_path: string;
  friction_events_path: string;
  live_updates_poll_ms: number;
  live_updates_router_refresh_every_ticks: number;
  live_updates_global: boolean;
  runtime_beacon_sample_rate: number;
  health_proxy_failure_threshold: number;
  health_proxy_cooldown_ms: number;
  cli_provider: string;
  cli_active_task_id: string;
};

type ConfigEditorPayload = {
  generated_at: string;
  config_path: string;
  fields: ConfigEditorFields;
};

function listToTextarea(values: string[]): string {
  return values.join("\n");
}

function textareaToList(value: string): string[] {
  return value
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function ConfigEditor() {
  const router = useRouter();
  const apiBase = getApiBase();
  const [isPending, startTransition] = useTransition();
  const [adminKey, setAdminKey] = useState("");
  const [loaded, setLoaded] = useState<ConfigEditorPayload | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    server_environment: "development",
    database_url: "",
    cors_allowed_origins: "",
    api_base_url: "",
    web_ui_base_url: "",
    execute_token: "",
    clear_execute_token: false,
    execute_token_allow_unauth: false,
    telegram_bot_token: "",
    clear_telegram_bot_token: false,
    telegram_chat_ids: "",
    task_log_dir: "",
    runtime_events_path: "",
    friction_events_path: "",
    live_updates_poll_ms: "120000",
    live_updates_router_refresh_every_ticks: "8",
    live_updates_global: false,
    runtime_beacon_sample_rate: "0.2",
    health_proxy_failure_threshold: "2",
    health_proxy_cooldown_ms: "30000",
    cli_provider: "cli",
    cli_active_task_id: "",
  });

  async function loadEditor() {
    setError(null);
    setStatus("Loading config editor…");
    const response = await fetch(`${apiBase}/api/agent/diagnostics/config-editor`, {
      headers: {
        "X-Admin-Key": adminKey,
      },
      cache: "no-store",
    });
    if (!response.ok) {
      setLoaded(null);
      setStatus(null);
      setError(`Config editor request failed with HTTP ${response.status}`);
      return;
    }
    const payload = (await response.json()) as ConfigEditorPayload;
    setLoaded(payload);
    setForm({
      server_environment: payload.fields.server_environment,
      database_url: payload.fields.database_url,
      cors_allowed_origins: listToTextarea(payload.fields.cors_allowed_origins),
      api_base_url: payload.fields.api_base_url,
      web_ui_base_url: payload.fields.web_ui_base_url,
      execute_token: "",
      clear_execute_token: false,
      execute_token_allow_unauth: payload.fields.execute_token_allow_unauth,
      telegram_bot_token: "",
      clear_telegram_bot_token: false,
      telegram_chat_ids: listToTextarea(payload.fields.telegram_chat_ids),
      task_log_dir: payload.fields.task_log_dir,
      runtime_events_path: payload.fields.runtime_events_path,
      friction_events_path: payload.fields.friction_events_path,
      live_updates_poll_ms: String(payload.fields.live_updates_poll_ms),
      live_updates_router_refresh_every_ticks: String(payload.fields.live_updates_router_refresh_every_ticks),
      live_updates_global: payload.fields.live_updates_global,
      runtime_beacon_sample_rate: String(payload.fields.runtime_beacon_sample_rate),
      health_proxy_failure_threshold: String(payload.fields.health_proxy_failure_threshold),
      health_proxy_cooldown_ms: String(payload.fields.health_proxy_cooldown_ms),
      cli_provider: payload.fields.cli_provider,
      cli_active_task_id: payload.fields.cli_active_task_id,
    });
    setStatus(`Loaded ${payload.config_path}`);
  }

  async function saveEditor() {
    setError(null);
    setStatus("Saving config…");
    const response = await fetch(`${apiBase}/api/agent/diagnostics/config-editor`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        "X-Admin-Key": adminKey,
      },
      body: JSON.stringify({
        server_environment: form.server_environment,
        database_url: form.database_url,
        cors_allowed_origins: textareaToList(form.cors_allowed_origins),
        api_base_url: form.api_base_url,
        web_ui_base_url: form.web_ui_base_url,
        execute_token: form.execute_token,
        clear_execute_token: form.clear_execute_token,
        execute_token_allow_unauth: form.execute_token_allow_unauth,
        telegram_bot_token: form.telegram_bot_token,
        clear_telegram_bot_token: form.clear_telegram_bot_token,
        telegram_chat_ids: textareaToList(form.telegram_chat_ids),
        task_log_dir: form.task_log_dir,
        runtime_events_path: form.runtime_events_path,
        friction_events_path: form.friction_events_path,
        live_updates_poll_ms: Number.parseInt(form.live_updates_poll_ms, 10),
        live_updates_router_refresh_every_ticks: Number.parseInt(form.live_updates_router_refresh_every_ticks, 10),
        live_updates_global: form.live_updates_global,
        runtime_beacon_sample_rate: Number.parseFloat(form.runtime_beacon_sample_rate),
        health_proxy_failure_threshold: Number.parseInt(form.health_proxy_failure_threshold, 10),
        health_proxy_cooldown_ms: Number.parseInt(form.health_proxy_cooldown_ms, 10),
        cli_provider: form.cli_provider,
        cli_active_task_id: form.cli_active_task_id,
      }),
    });
    if (!response.ok) {
      setStatus(null);
      setError(`Config save failed with HTTP ${response.status}`);
      return;
    }
    const payload = (await response.json()) as ConfigEditorPayload;
    setLoaded(payload);
    setStatus(`Saved ${payload.config_path}`);
    startTransition(() => {
      router.refresh();
    });
  }

  return (
    <section className="border rounded-2xl p-5 space-y-4">
      <div>
        <h2 className="text-xl font-semibold">Config Editor</h2>
        <p className="text-sm text-muted-foreground">
          Writes allowlisted operational settings into <code>~/.coherence-network/config.json</code>.
          Secret fields are write-only here: leave them blank to keep the current value.
        </p>
      </div>
      <div className="grid gap-4 lg:grid-cols-[1fr_auto]">
        <label className="space-y-2 text-sm">
          <span className="font-medium">Admin key</span>
          <input
            type="password"
            value={adminKey}
            onChange={(event) => setAdminKey(event.target.value)}
            className="w-full rounded-xl border bg-background px-3 py-2"
            placeholder="X-Admin-Key"
          />
        </label>
        <div className="flex items-end">
          <button
            type="button"
            onClick={() => void loadEditor()}
            disabled={!adminKey || isPending}
            className="rounded-xl border px-4 py-2 text-sm font-medium disabled:opacity-50"
          >
            Load editor
          </button>
        </div>
      </div>
      {status ? <p className="text-sm text-muted-foreground">{status}</p> : null}
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {loaded ? (
        <div className="space-y-5">
          <div className="text-xs text-muted-foreground">Editing {loaded.config_path}</div>
          <div className="grid gap-4 md:grid-cols-2">
            <label className="space-y-2 text-sm">
              <span className="font-medium">Environment</span>
              <select
                value={form.server_environment}
                onChange={(event) => setForm((current) => ({ ...current, server_environment: event.target.value }))}
                className="w-full rounded-xl border bg-background px-3 py-2"
              >
                <option value="development">development</option>
                <option value="production">production</option>
                <option value="test">test</option>
              </select>
            </label>
            <label className="space-y-2 text-sm">
              <span className="font-medium">Database URL</span>
              <input
                value={form.database_url}
                onChange={(event) => setForm((current) => ({ ...current, database_url: event.target.value }))}
                className="w-full rounded-xl border bg-background px-3 py-2"
              />
            </label>
            <label className="space-y-2 text-sm">
              <span className="font-medium">API base URL</span>
              <input
                value={form.api_base_url}
                onChange={(event) => setForm((current) => ({ ...current, api_base_url: event.target.value }))}
                className="w-full rounded-xl border bg-background px-3 py-2"
              />
            </label>
            <label className="space-y-2 text-sm">
              <span className="font-medium">Web UI base URL</span>
              <input
                value={form.web_ui_base_url}
                onChange={(event) => setForm((current) => ({ ...current, web_ui_base_url: event.target.value }))}
                className="w-full rounded-xl border bg-background px-3 py-2"
              />
            </label>
          </div>
          <label className="space-y-2 text-sm block">
            <span className="font-medium">CORS allowed origins</span>
            <textarea
              value={form.cors_allowed_origins}
              onChange={(event) => setForm((current) => ({ ...current, cors_allowed_origins: event.target.value }))}
              className="min-h-28 w-full rounded-xl border bg-background px-3 py-2"
            />
          </label>
          <div className="grid gap-4 md:grid-cols-2">
            <label className="space-y-2 text-sm">
              <span className="font-medium">Execute token</span>
              <input
                type="password"
                value={form.execute_token}
                onChange={(event) => setForm((current) => ({ ...current, execute_token: event.target.value }))}
                className="w-full rounded-xl border bg-background px-3 py-2"
                placeholder={loaded.fields.execute_token_configured ? "configured; enter new value to replace" : "not configured"}
              />
            </label>
            <label className="space-y-2 text-sm">
              <span className="font-medium">Telegram bot token</span>
              <input
                type="password"
                value={form.telegram_bot_token}
                onChange={(event) => setForm((current) => ({ ...current, telegram_bot_token: event.target.value }))}
                className="w-full rounded-xl border bg-background px-3 py-2"
                placeholder={loaded.fields.telegram_bot_token_configured ? "configured; enter new value to replace" : "not configured"}
              />
            </label>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.execute_token_allow_unauth}
                onChange={(event) => setForm((current) => ({ ...current, execute_token_allow_unauth: event.target.checked }))}
              />
              <span>Allow unauthenticated execute token bypass</span>
            </label>
            <div className="flex flex-wrap gap-4">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.clear_execute_token}
                  onChange={(event) => setForm((current) => ({ ...current, clear_execute_token: event.target.checked }))}
                />
                <span>Clear execute token</span>
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.clear_telegram_bot_token}
                  onChange={(event) => setForm((current) => ({ ...current, clear_telegram_bot_token: event.target.checked }))}
                />
                <span>Clear Telegram bot token</span>
              </label>
            </div>
          </div>
          <label className="space-y-2 text-sm block">
            <span className="font-medium">Telegram chat IDs</span>
            <textarea
              value={form.telegram_chat_ids}
              onChange={(event) => setForm((current) => ({ ...current, telegram_chat_ids: event.target.value }))}
              className="min-h-24 w-full rounded-xl border bg-background px-3 py-2"
            />
          </label>
          <div className="grid gap-4 md:grid-cols-3">
            <label className="space-y-2 text-sm">
              <span className="font-medium">Task log dir</span>
              <input
                value={form.task_log_dir}
                onChange={(event) => setForm((current) => ({ ...current, task_log_dir: event.target.value }))}
                className="w-full rounded-xl border bg-background px-3 py-2"
              />
            </label>
            <label className="space-y-2 text-sm">
              <span className="font-medium">Runtime events path</span>
              <input
                value={form.runtime_events_path}
                onChange={(event) => setForm((current) => ({ ...current, runtime_events_path: event.target.value }))}
                className="w-full rounded-xl border bg-background px-3 py-2"
              />
            </label>
            <label className="space-y-2 text-sm">
              <span className="font-medium">Friction events path</span>
              <input
                value={form.friction_events_path}
                onChange={(event) => setForm((current) => ({ ...current, friction_events_path: event.target.value }))}
                className="w-full rounded-xl border bg-background px-3 py-2"
              />
            </label>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <label className="space-y-2 text-sm">
              <span className="font-medium">Live updates poll ms</span>
              <input
                value={form.live_updates_poll_ms}
                onChange={(event) => setForm((current) => ({ ...current, live_updates_poll_ms: event.target.value }))}
                className="w-full rounded-xl border bg-background px-3 py-2"
              />
            </label>
            <label className="space-y-2 text-sm">
              <span className="font-medium">Live updates refresh ticks</span>
              <input
                value={form.live_updates_router_refresh_every_ticks}
                onChange={(event) => setForm((current) => ({ ...current, live_updates_router_refresh_every_ticks: event.target.value }))}
                className="w-full rounded-xl border bg-background px-3 py-2"
              />
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.live_updates_global}
                onChange={(event) => setForm((current) => ({ ...current, live_updates_global: event.target.checked }))}
              />
              <span>Enable live updates on every route</span>
            </label>
            <label className="space-y-2 text-sm">
              <span className="font-medium">Runtime beacon sample rate</span>
              <input
                value={form.runtime_beacon_sample_rate}
                onChange={(event) => setForm((current) => ({ ...current, runtime_beacon_sample_rate: event.target.value }))}
                className="w-full rounded-xl border bg-background px-3 py-2"
              />
            </label>
            <label className="space-y-2 text-sm">
              <span className="font-medium">Health proxy failure threshold</span>
              <input
                value={form.health_proxy_failure_threshold}
                onChange={(event) => setForm((current) => ({ ...current, health_proxy_failure_threshold: event.target.value }))}
                className="w-full rounded-xl border bg-background px-3 py-2"
              />
            </label>
            <label className="space-y-2 text-sm">
              <span className="font-medium">Health proxy cooldown ms</span>
              <input
                value={form.health_proxy_cooldown_ms}
                onChange={(event) => setForm((current) => ({ ...current, health_proxy_cooldown_ms: event.target.value }))}
                className="w-full rounded-xl border bg-background px-3 py-2"
              />
            </label>
            <label className="space-y-2 text-sm">
              <span className="font-medium">CLI provider</span>
              <input
                value={form.cli_provider}
                onChange={(event) => setForm((current) => ({ ...current, cli_provider: event.target.value }))}
                className="w-full rounded-xl border bg-background px-3 py-2"
              />
            </label>
            <label className="space-y-2 text-sm">
              <span className="font-medium">CLI active task ID</span>
              <input
                value={form.cli_active_task_id}
                onChange={(event) => setForm((current) => ({ ...current, cli_active_task_id: event.target.value }))}
                className="w-full rounded-xl border bg-background px-3 py-2"
              />
            </label>
          </div>
          <div className="flex justify-end">
            <button
              type="button"
              onClick={() => void saveEditor()}
              disabled={!adminKey || isPending}
              className="rounded-xl border px-4 py-2 text-sm font-medium disabled:opacity-50"
            >
              Save config
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
