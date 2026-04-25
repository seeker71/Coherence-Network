import Link from "next/link";

import { ConfigEditor } from "./config-editor";
import { OperationsWorkbench } from "./operations-workbench";
import { getApiBase } from "@/lib/api";
import { fetchJsonOrNull } from "@/lib/fetch";

type DiagnosticsPayload = {
  generated_at: string;
  config: {
    environment: string;
    sources: Array<{
      source: string;
      path: string;
      exists: boolean;
      loaded: boolean;
      section_count: number;
      sections: string[];
    }>;
    database: {
      backend: string;
      url: string;
      override_services: string[];
    };
    auth: {
      api_key: { configured: boolean; preview: string | null };
      admin_key: { configured: boolean; preview: string | null };
      execute_token: { configured: boolean; preview: string | null };
      execute_token_allow_unauth: boolean;
    };
    telegram: {
      bot_token: { configured: boolean; preview: string | null };
      chat_ids_count: number;
      allowed_user_ids_count: number;
    };
    cors: {
      allowed_origins: string[];
    };
    files: Record<string, { path: string; exists: boolean; kind: string }>;
    provider_surfaces: {
      api_base_url: string;
      web_ui_base_url: string;
    };
    web_controls: {
      live_updates_poll_ms: number;
      live_updates_router_refresh_every_ticks: number;
      live_updates_global: boolean;
      runtime_beacon_sample_rate: number;
      health_proxy_failure_threshold: number;
      health_proxy_cooldown_ms: number;
    };
    cli_defaults: {
      provider: string;
      active_task_id: string;
    };
  };
  health: {
    status: string;
    version: string;
    deployed_sha?: string | null;
    uptime_human: string;
    schema_ok: boolean;
    integrity_compromised: boolean;
  };
  persistence: {
    pass_contract?: boolean;
    failures?: string[];
  };
  tasks: {
    counts: {
      total: number;
      by_status?: Record<string, number>;
    };
    context_budget: {
      score: number;
      flagged_tasks: number;
      task_count: number;
      average_context_bytes: number;
      average_output_chars: number;
      average_file_scope_count: number;
      average_command_count: number;
      top_flags: Array<{
        flag: string;
        count: number;
      }>;
      priority_actions: string[];
    };
    recent: Array<{
      id: string;
      status: string;
      task_type: string;
      direction: string;
      updated_at?: string | null;
    }>;
    active: Array<{
      id: string;
      status: string;
      direction: string;
    }>;
    attention_total: number;
    attention: Array<{
      id: string;
      status: string;
      direction: string;
      decision_prompt?: string | null;
    }>;
    log_previews: Array<{
      task_id: string;
      source: string;
      preview: string;
      path: string;
    }>;
  };
  runners: {
    total: number;
    stale: number;
    running: number;
    items: Array<{
      runner_id: string;
      status: string;
      active_task_id?: string | null;
      host?: string | null;
      version?: string | null;
      is_stale?: boolean;
    }>;
  };
  lifecycle: {
    total_events?: number;
    stage_counts?: Record<string, number>;
  };
  runtime: {
    endpoint_attention: {
      items?: Array<{
        endpoint: string;
        event_count: number;
        avg_runtime_ms?: number | null;
        p95_runtime_ms?: number | null;
        attention_score: number;
      }>;
    };
    recent_events: Array<{
      endpoint?: string;
      source?: string;
      runtime_ms?: number;
      status_code?: number;
      timestamp?: string;
    }>;
  };
  friction: {
    summary: {
      total_events: number;
      open_events: number;
      total_energy_loss: number;
      top_block_types: Array<{
        key: string;
        count: number;
      }>;
    };
    events: Array<{
      id: string;
      block_type: string;
      stage: string;
      severity: string;
      status: string;
      notes?: string | null;
    }>;
  };
};

export const dynamic = "force-dynamic";

async function loadDiagnostics(): Promise<DiagnosticsPayload | null> {
  return fetchJsonOrNull<DiagnosticsPayload>(`${getApiBase()}/api/agent/diagnostics/overview`, {}, 5000);
}

function formatStamp(value: string | null | undefined): string {
  if (!value) return "n/a";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function healthTone(ok: boolean): string {
  return ok ? "text-emerald-700" : "text-amber-700";
}

export default async function DiagnosticsPage() {
  const diagnostics = await loadDiagnostics();

  return (
    <main className="min-h-screen max-w-7xl mx-auto px-4 py-8 space-y-8">
      <section className="space-y-3 border rounded-2xl p-6 bg-background/80 backdrop-blur">
        <div className="flex flex-wrap gap-3 text-sm text-muted-foreground">
          <Link href="/" className="hover:text-foreground">Home</Link>
          <Link href="/tasks" className="hover:text-foreground">Tasks</Link>
          <Link href="/pipeline" className="hover:text-foreground">Pipeline</Link>
          <Link href="/gates" className="hover:text-foreground">Gates</Link>
          <Link href="/diagnostics" className="hover:text-foreground">Diagnostics</Link>
        </div>
        <div className="space-y-2">
          <h1 className="text-3xl font-semibold tracking-tight">Diagnostics Console</h1>
          <p className="text-muted-foreground max-w-3xl">
            One place to inspect effective config, log surfaces, runner fleet state, queued work,
            task logs, runtime hotspots, and recent friction before something turns into guesswork.
          </p>
        </div>
      </section>

      {!diagnostics ? (
        <section className="border rounded-2xl p-6" data-placeholder="true">
          <h2 className="text-xl font-semibold">Diagnostics unavailable</h2>
          <p className="text-muted-foreground mt-2">
            The diagnostics API is not reachable right now. Once the local API is up, this page will
            show config, logs, runner state, tasks, runtime attention, and friction in one place.
          </p>
        </section>
      ) : (
        <>
          <section className="grid gap-4 md:grid-cols-5">
            <div className="border rounded-2xl p-4">
              <div className="text-sm text-muted-foreground">Health</div>
              <div className={`mt-2 text-2xl font-semibold ${healthTone(diagnostics.health.status === "ok")}`}>
                {diagnostics.health.status}
              </div>
              <div className="mt-1 text-sm text-muted-foreground">
                uptime {diagnostics.health.uptime_human}
              </div>
            </div>
            <div className="border rounded-2xl p-4">
              <div className="text-sm text-muted-foreground">Persistence</div>
              <div
                className={`mt-2 text-2xl font-semibold ${healthTone(Boolean(diagnostics.persistence.pass_contract))}`}
              >
                {diagnostics.persistence.pass_contract ? "passing" : "attention"}
              </div>
              <div className="mt-1 text-sm text-muted-foreground">
                {diagnostics.persistence.failures?.length ? diagnostics.persistence.failures.join(", ") : "core contract intact"}
              </div>
            </div>
            <div className="border rounded-2xl p-4">
              <div className="text-sm text-muted-foreground">Runner fleet</div>
              <div className="mt-2 text-2xl font-semibold">{diagnostics.runners.running}</div>
              <div className="mt-1 text-sm text-muted-foreground">
                {diagnostics.runners.total} total, {diagnostics.runners.stale} stale
              </div>
            </div>
            <div className="border rounded-2xl p-4">
              <div className="text-sm text-muted-foreground">Queue pressure</div>
              <div className="mt-2 text-2xl font-semibold">{diagnostics.tasks.counts.total}</div>
              <div className="mt-1 text-sm text-muted-foreground">
                {diagnostics.tasks.attention_total} task{diagnostics.tasks.attention_total === 1 ? "" : "s"} need attention
              </div>
            </div>
            <div className="border rounded-2xl p-4">
              <div className="text-sm text-muted-foreground">Context budget</div>
              <div className="mt-2 text-2xl font-semibold">{diagnostics.tasks.context_budget.score}</div>
              <div className="mt-1 text-sm text-muted-foreground">
                {diagnostics.tasks.context_budget.flagged_tasks}/{diagnostics.tasks.context_budget.task_count} recent tasks flagged
              </div>
            </div>
          </section>

          <section className="grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
            <div className="border rounded-2xl p-5 space-y-4">
              <div>
                <h2 className="text-xl font-semibold">Config Summary</h2>
                <p className="text-sm text-muted-foreground">
                  Effective runtime config, redacted where it would leak credentials.
                </p>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="rounded-xl border p-4">
                  <div className="text-sm text-muted-foreground">Environment</div>
                  <div className="mt-1 font-medium">{diagnostics.config.environment}</div>
                  <div className="mt-3 text-sm text-muted-foreground">Database</div>
                  <div className="mt-1 font-mono text-xs break-all">{diagnostics.config.database.url}</div>
                  <div className="mt-1 text-sm">{diagnostics.config.database.backend}</div>
                </div>
                <div className="rounded-xl border p-4">
                  <div className="text-sm text-muted-foreground">Credentials</div>
                  <div className="mt-2 space-y-1 text-sm">
                    <div>API key: {diagnostics.config.auth.api_key.preview ?? "not set"}</div>
                    <div>Admin key: {diagnostics.config.auth.admin_key.preview ?? "not set"}</div>
                    <div>Execute token: {diagnostics.config.auth.execute_token.preview ?? "not set"}</div>
                    <div>Token bypass: {diagnostics.config.auth.execute_token_allow_unauth ? "allowed" : "disabled"}</div>
                  </div>
                </div>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="rounded-xl border p-4">
                  <div className="text-sm text-muted-foreground">Config sources</div>
                  <div className="mt-3 space-y-3">
                    {diagnostics.config.sources.map((source) => (
                      <div key={source.path} className="text-sm">
                        <div className="font-medium capitalize">{source.source}</div>
                        <div className="font-mono text-xs break-all text-muted-foreground">{source.path}</div>
                        <div className="text-muted-foreground">
                          {source.exists ? `${source.section_count} sections` : "missing"}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="rounded-xl border p-4">
                  <div className="text-sm text-muted-foreground">Log and file surfaces</div>
                  <div className="mt-3 space-y-2 text-sm">
                    {Object.entries(diagnostics.config.files).map(([key, file]) => (
                      <div key={key}>
                        <div className="font-medium">{key}</div>
                        <div className="font-mono text-xs break-all text-muted-foreground">{file.path}</div>
                        <div className={file.exists ? "text-emerald-700" : "text-amber-700"}>
                          {file.exists ? "present" : "missing"}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="rounded-xl border p-4">
                  <div className="text-sm text-muted-foreground">Web runtime controls</div>
                  <div className="mt-2 space-y-1 text-sm">
                    <div>Poll ms: {diagnostics.config.web_controls.live_updates_poll_ms}</div>
                    <div>Refresh ticks: {diagnostics.config.web_controls.live_updates_router_refresh_every_ticks}</div>
                    <div>Global live updates: {diagnostics.config.web_controls.live_updates_global ? "on" : "off"}</div>
                    <div>Beacon sample rate: {diagnostics.config.web_controls.runtime_beacon_sample_rate}</div>
                    <div>Health proxy threshold: {diagnostics.config.web_controls.health_proxy_failure_threshold}</div>
                    <div>Health proxy cooldown: {diagnostics.config.web_controls.health_proxy_cooldown_ms}ms</div>
                  </div>
                </div>
                <div className="rounded-xl border p-4">
                  <div className="text-sm text-muted-foreground">CLI defaults</div>
                  <div className="mt-2 space-y-1 text-sm">
                    <div>Provider: {diagnostics.config.cli_defaults.provider || "n/a"}</div>
                    <div>Active task: {diagnostics.config.cli_defaults.active_task_id || "none"}</div>
                    <div>API base: {diagnostics.config.provider_surfaces.api_base_url || "n/a"}</div>
                    <div>Web base: {diagnostics.config.provider_surfaces.web_ui_base_url || "n/a"}</div>
                  </div>
                </div>
              </div>
            </div>

            <div className="border rounded-2xl p-5 space-y-4">
              <div>
                <h2 className="text-xl font-semibold">Runner And Tasks</h2>
                <p className="text-sm text-muted-foreground">
                  Who is working, what is blocked, and where to click next.
                </p>
              </div>
              <div className="space-y-3">
                {diagnostics.runners.items.slice(0, 6).map((runner) => (
                  <div key={runner.runner_id} className="rounded-xl border p-3 text-sm">
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-medium">{runner.runner_id}</span>
                      <span className={runner.is_stale ? "text-amber-700" : "text-emerald-700"}>{runner.status}</span>
                    </div>
                    <div className="text-muted-foreground">{runner.host || "unknown host"}</div>
                    {runner.active_task_id ? (
                      <Link href={`/tasks/${encodeURIComponent(runner.active_task_id)}`} className="text-sm text-primary hover:underline">
                        Open active task {runner.active_task_id}
                      </Link>
                    ) : null}
                  </div>
                ))}
              </div>
              <div className="space-y-2">
                <h3 className="font-medium">Needs attention</h3>
                {diagnostics.tasks.attention.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No tasks currently require operator attention.</p>
                ) : (
                  diagnostics.tasks.attention.map((task) => (
                    <div key={task.id} className="rounded-xl border p-3 text-sm">
                      <Link href={`/tasks/${encodeURIComponent(task.id)}`} className="font-medium text-primary hover:underline">
                        {task.id}
                      </Link>
                      <div className="mt-1">{task.direction}</div>
                      {task.decision_prompt ? (
                        <div className="mt-1 text-muted-foreground">{task.decision_prompt}</div>
                      ) : null}
                    </div>
                  ))
                )}
              </div>
            </div>
          </section>

          <section className="grid gap-6 lg:grid-cols-[0.95fr_1.05fr]">
            <div className="border rounded-2xl p-5 space-y-4">
              <div>
                <h2 className="text-xl font-semibold">Context Efficiency</h2>
                <p className="text-sm text-muted-foreground">
                  Compact signals that show when task setup is getting too broad, noisy, or expensive.
                </p>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="rounded-xl border p-4">
                  <div className="text-sm text-muted-foreground">Average context bytes</div>
                  <div className="mt-1 text-2xl font-semibold">
                    {Math.round(diagnostics.tasks.context_budget.average_context_bytes)}
                  </div>
                </div>
                <div className="rounded-xl border p-4">
                  <div className="text-sm text-muted-foreground">Average file scope</div>
                  <div className="mt-1 text-2xl font-semibold">
                    {diagnostics.tasks.context_budget.average_file_scope_count.toFixed(1)}
                  </div>
                </div>
                <div className="rounded-xl border p-4">
                  <div className="text-sm text-muted-foreground">Average output chars</div>
                  <div className="mt-1 text-2xl font-semibold">
                    {Math.round(diagnostics.tasks.context_budget.average_output_chars)}
                  </div>
                </div>
                <div className="rounded-xl border p-4">
                  <div className="text-sm text-muted-foreground">Average command count</div>
                  <div className="mt-1 text-2xl font-semibold">
                    {diagnostics.tasks.context_budget.average_command_count.toFixed(1)}
                  </div>
                </div>
              </div>
              <div className="space-y-2">
                <h3 className="font-medium">Top flags</h3>
                {diagnostics.tasks.context_budget.top_flags.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No recurring context hygiene risks in the recent task sample.</p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {diagnostics.tasks.context_budget.top_flags.map((flag) => (
                      <span key={flag.flag} className="rounded-full border px-3 py-1 text-sm">
                        {flag.flag} x{flag.count}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="border rounded-2xl p-5 space-y-4">
              <div>
                <h2 className="text-xl font-semibold">Priority Actions</h2>
                <p className="text-sm text-muted-foreground">
                  The fastest ways to cut token burn and wrong-path execution before it compounds.
                </p>
              </div>
              {diagnostics.tasks.context_budget.priority_actions.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No context-efficiency actions recommended from the recent task sample.
                </p>
              ) : (
                <div className="space-y-3">
                  {diagnostics.tasks.context_budget.priority_actions.map((action) => (
                    <div key={action} className="rounded-xl border p-3 text-sm">
                      {action}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>

          <ConfigEditor />

          <OperationsWorkbench
            apiBase={getApiBase()}
            initialTasks={diagnostics.tasks.recent}
            initialRunners={diagnostics.runners.items}
          />

          <section className="grid gap-6 lg:grid-cols-2">
            <div className="border rounded-2xl p-5 space-y-4">
              <div>
                <h2 className="text-xl font-semibold">Recent Task Logs</h2>
                <p className="text-sm text-muted-foreground">
                  The fastest way to see whether the runner is doing real work or just looping.
                </p>
              </div>
              <div className="space-y-4">
                {diagnostics.tasks.log_previews.map((entry) => (
                  <div key={entry.task_id} className="rounded-xl border p-4">
                    <div className="flex items-center justify-between gap-3">
                      <Link href={`/tasks/${encodeURIComponent(entry.task_id)}`} className="font-medium text-primary hover:underline">
                        {entry.task_id}
                      </Link>
                      <span className="text-xs uppercase tracking-wide text-muted-foreground">{entry.source}</span>
                    </div>
                    <div className="mt-2 font-mono text-xs text-muted-foreground break-all">{entry.path}</div>
                    <pre className="mt-3 whitespace-pre-wrap rounded-lg bg-muted/40 p-3 text-xs leading-5">
                      {entry.preview}
                    </pre>
                  </div>
                ))}
              </div>
            </div>

            <div className="border rounded-2xl p-5 space-y-4">
              <div>
                <h2 className="text-xl font-semibold">Runtime Attention</h2>
                <p className="text-sm text-muted-foreground">
                  Slow or noisy endpoints and the latest runtime events behind them.
                </p>
              </div>
              <div className="space-y-3">
                {(diagnostics.runtime.endpoint_attention.items ?? []).map((item) => (
                  <div key={item.endpoint} className="rounded-xl border p-3 text-sm">
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-mono text-xs break-all">{item.endpoint}</span>
                      <span className="font-medium">{item.attention_score.toFixed(1)}</span>
                    </div>
                    <div className="mt-1 text-muted-foreground">
                      {item.event_count} events, avg {Math.round(item.avg_runtime_ms ?? 0)} ms, p95 {Math.round(item.p95_runtime_ms ?? 0)} ms
                    </div>
                  </div>
                ))}
              </div>
              <div className="space-y-2">
                <h3 className="font-medium">Recent runtime events</h3>
                {diagnostics.runtime.recent_events.map((event, index) => (
                  <div key={`${event.endpoint ?? "event"}-${index}`} className="rounded-xl border p-3 text-sm">
                    <div className="font-mono text-xs break-all">{event.endpoint ?? "unknown endpoint"}</div>
                    <div className="mt-1 text-muted-foreground">
                      {event.source ?? "unknown source"} • {event.status_code ?? "n/a"} • {Math.round(event.runtime_ms ?? 0)} ms • {formatStamp(event.timestamp)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>

          <section className="grid gap-6 lg:grid-cols-2">
            <div className="border rounded-2xl p-5 space-y-4">
              <div>
                <h2 className="text-xl font-semibold">Friction</h2>
                <p className="text-sm text-muted-foreground">
                  Open failure patterns that are still wasting attention or momentum.
                </p>
              </div>
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="rounded-xl border p-4">
                  <div className="text-sm text-muted-foreground">Events</div>
                  <div className="mt-1 text-2xl font-semibold">{diagnostics.friction.summary.total_events}</div>
                </div>
                <div className="rounded-xl border p-4">
                  <div className="text-sm text-muted-foreground">Open</div>
                  <div className="mt-1 text-2xl font-semibold">{diagnostics.friction.summary.open_events}</div>
                </div>
                <div className="rounded-xl border p-4">
                  <div className="text-sm text-muted-foreground">Energy loss</div>
                  <div className="mt-1 text-2xl font-semibold">{diagnostics.friction.summary.total_energy_loss.toFixed(1)}</div>
                </div>
              </div>
              <div className="space-y-2">
                {diagnostics.friction.events.map((event) => (
                  <div key={event.id} className="rounded-xl border p-3 text-sm">
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-medium">{event.block_type}</span>
                      <span className="text-muted-foreground">{event.severity}</span>
                    </div>
                    <div className="mt-1 text-muted-foreground">{event.stage} • {event.status}</div>
                    {event.notes ? <div className="mt-1">{event.notes}</div> : null}
                  </div>
                ))}
              </div>
            </div>

            <div className="border rounded-2xl p-5 space-y-4">
              <div>
                <h2 className="text-xl font-semibold">Useful links</h2>
                <p className="text-sm text-muted-foreground">
                  Fast paths into the places that matter when the system is unhealthy.
                </p>
              </div>
              <div className="grid gap-3 sm:grid-cols-2 text-sm">
                <a href={`${getApiBase()}/api/health`} className="rounded-xl border p-3 hover:border-foreground/40">API health</a>
                <a href={`${getApiBase()}/api/health/persistence`} className="rounded-xl border p-3 hover:border-foreground/40">Persistence contract</a>
                <a href={`${getApiBase()}/api/agent/diagnostics/overview`} className="rounded-xl border p-3 hover:border-foreground/40">Diagnostics API</a>
                <a href={`${getApiBase()}/api/runtime/endpoints/attention`} className="rounded-xl border p-3 hover:border-foreground/40">Endpoint attention API</a>
                <Link href="/tasks" className="rounded-xl border p-3 hover:border-foreground/40">Task queue</Link>
                <Link href="/gates" className="rounded-xl border p-3 hover:border-foreground/40">Release gates</Link>
              </div>
              <div className="rounded-xl border p-4 text-sm text-muted-foreground">
                Generated {diagnostics.generated_at}. Deployed SHA {diagnostics.health.deployed_sha ?? "unknown"}.
              </div>
            </div>
          </section>
        </>
      )}
    </main>
  );
}
