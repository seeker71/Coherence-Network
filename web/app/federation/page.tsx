import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";

export const metadata: Metadata = {
  title: "Federation",
  description:
    "Federation nodes that form the distributed backbone of the Coherence Network.",
};

type FederationNode = {
  node_id: string;
  hostname: string;
  os_type: string;
  providers: string[];
  capabilities: Record<string, unknown>;
  registered_at: string;
  last_seen_at: string;
  status: string;
  is_autonomous: boolean;
  heartbeat_interval_ms: number;
  git_sha: string | null;
};

function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function statusColor(status: string): { bg: string; text: string } {
  switch (status) {
    case "online":
      return { bg: "bg-emerald-500/10", text: "text-emerald-400" };
    case "idle":
      return { bg: "bg-amber-500/10", text: "text-amber-400" };
    case "offline":
      return { bg: "bg-red-500/10", text: "text-red-400" };
    default:
      return { bg: "bg-muted", text: "text-muted-foreground" };
  }
}

async function loadNodes(): Promise<FederationNode[]> {
  try {
    const API = getApiBase();
    const res = await fetch(`${API}/api/federation/nodes`, {
      cache: "no-store",
    });
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}

export default async function FederationPage() {
  const nodes = await loadNodes();

  const totalNodes = nodes.length;
  const autonomousCount = nodes.filter((n) => n.is_autonomous).length;
  const onlineCount = nodes.filter((n) => n.status === "online").length;

  return (
    <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-8 max-w-5xl mx-auto space-y-8">
      <header className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Federation</h1>
        <p className="max-w-3xl text-muted-foreground leading-relaxed">
          The distributed network of nodes that power Coherence. Each node
          contributes compute, models, and capabilities to the collective.
        </p>
        <div className="flex flex-wrap gap-2">
          <Link
            href="/constellation"
            className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200"
          >
            Constellation
          </Link>
        </div>
      </header>

      {/* Stats */}
      <section className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-4">
          <p className="text-xs uppercase tracking-widest text-muted-foreground">
            Total Nodes
          </p>
          <p className="mt-2 text-3xl font-light">{totalNodes}</p>
        </div>
        <div className="rounded-2xl border border-emerald-500/20 bg-gradient-to-b from-emerald-500/5 to-card/30 p-4">
          <p className="text-xs uppercase tracking-widest text-emerald-400">
            Online
          </p>
          <p className="mt-2 text-3xl font-light text-emerald-300">
            {onlineCount}
          </p>
        </div>
        <div className="rounded-2xl border border-purple-500/20 bg-gradient-to-b from-purple-500/5 to-card/30 p-4">
          <p className="text-xs uppercase tracking-widest text-purple-400">
            Autonomous
          </p>
          <p className="mt-2 text-3xl font-light text-purple-300">
            {autonomousCount}
          </p>
        </div>
      </section>

      {/* Node cards */}
      <section className="space-y-4">
        <h2 className="text-lg font-medium">Registered Nodes</h2>

        {nodes.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border/30 bg-background/30 p-8 text-center space-y-3">
            <p className="text-muted-foreground">
              No federation nodes registered yet. Nodes will appear here once
              they connect to the network.
            </p>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {nodes.map((node) => {
              const sc = statusColor(node.status);
              const capabilityList = node.capabilities
                ? Object.keys(node.capabilities).filter(
                    (k) => k !== "git_sha"
                  )
                : [];
              return (
                <article
                  key={node.node_id}
                  className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-3"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1">
                      <h3 className="text-base font-medium">
                        {node.hostname || node.node_id}
                      </h3>
                      <div className="flex flex-wrap items-center gap-2">
                        <span
                          className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${sc.bg} ${sc.text}`}
                        >
                          {node.status}
                        </span>
                        {node.is_autonomous ? (
                          <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-purple-500/10 text-purple-400">
                            autonomous
                          </span>
                        ) : null}
                        <span className="text-xs text-muted-foreground">
                          {node.os_type}
                        </span>
                      </div>
                    </div>
                  </div>

                  {node.providers.length > 0 ? (
                    <div className="flex flex-wrap gap-1.5">
                      {node.providers.map((p) => (
                        <span
                          key={p}
                          className="rounded-full border border-border/20 bg-background/40 px-2 py-0.5 text-xs text-muted-foreground"
                        >
                          {p}
                        </span>
                      ))}
                    </div>
                  ) : null}

                  {capabilityList.length > 0 ? (
                    <div className="flex flex-wrap gap-1.5">
                      {capabilityList.slice(0, 8).map((cap) => (
                        <span
                          key={cap}
                          className="rounded-full border border-teal-500/20 bg-teal-500/5 px-2 py-0.5 text-xs text-teal-300"
                        >
                          {cap}
                        </span>
                      ))}
                    </div>
                  ) : null}

                  <div className="text-xs text-muted-foreground space-y-0.5">
                    <p>
                      Last heartbeat: {formatTimestamp(node.last_seen_at)}
                    </p>
                    <p>Registered: {formatTimestamp(node.registered_at)}</p>
                    {node.git_sha ? (
                      <p className="font-mono">
                        SHA: {node.git_sha.slice(0, 8)}
                      </p>
                    ) : null}
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>

      {/* Navigation */}
      <nav
        className="py-8 text-center space-y-2 border-t border-border/20"
        aria-label="Related pages"
      >
        <p className="text-xs text-muted-foreground/80 uppercase tracking-wider">
          Explore more
        </p>
        <div className="flex flex-wrap justify-center gap-4 text-sm">
          <Link href="/constellation" className="text-blue-400 hover:underline">
            Constellation
          </Link>
          <Link href="/vitality" className="text-emerald-400 hover:underline">
            Vitality
          </Link>
          <Link href="/activity" className="text-amber-400 hover:underline">
            Activity
          </Link>
        </div>
      </nav>
    </main>
  );
}
