"use client";

import type { DeployContract, HealthProxyResponse, HealthResponse } from "./types";
import { formatTs } from "./utils";

type Props = {
  health: HealthResponse | null;
  proxy: HealthProxyResponse | null;
  deploy: DeployContract | null;
};

export function DeploymentUptimeSection({ health, proxy, deploy }: Props) {
  return (
    <section className="space-y-3 border rounded-md p-4">
      <h2 className="text-lg font-semibold">Deployment + Uptime</h2>
      <div className="grid gap-3 md:grid-cols-2">
        <div className="rounded border p-3">
          <h3 className="text-sm font-medium">API</h3>
          {health ? (
            <ul className="text-sm text-muted-foreground space-y-1">
              <li>Status: {health.status}</li>
              <li>Version: {health.version}</li>
              <li>Uptime: {health.uptime_human}</li>
              <li>Started: {formatTs(health.started_at)}</li>
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">Loading API health…</p>
          )}
        </div>
        <div className="rounded border p-3">
          <h3 className="text-sm font-medium">Web</h3>
          {proxy?.web ? (
            <ul className="text-sm text-muted-foreground space-y-1">
              <li>Status: {proxy.web.status}</li>
              <li>Uptime: {proxy.web.uptime_human}</li>
              <li>Checked: {formatTs(proxy.checked_at)}</li>
              <li>Updated SHA: {proxy.web.updated_at || "unknown"}</li>
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">Loading web proxy…</p>
          )}
        </div>
        <div className="rounded border p-3 md:col-span-2">
          <h3 className="text-sm font-medium">Public deploy contract</h3>
          {deploy ? (
            <pre className="text-xs bg-muted p-2 rounded overflow-auto">
              {JSON.stringify(deploy, null, 2)}
            </pre>
          ) : (
            <p className="text-sm text-muted-foreground">Loading deploy check…</p>
          )}
        </div>
      </div>
    </section>
  );
}
