import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";
import MessageForm from "./MessageForm";

export const metadata: Metadata = {
  title: "Federation Nodes",
  description: "Registered federation nodes, status, and messaging.",
};

type FederationNodeCapabilities = {
  executors?: string[];
  tools?: string[];
  hardware?: {
    cpu_count?: number;
    memory_total_gb?: number | null;
    gpu_available?: boolean;
    gpu_type?: string | null;
  };
  models_by_executor?: Record<string, string[]>;
  probed_at?: string;
};

type FederationNode = {
  node_id: string;
  hostname: string;
  os_type: string;
  providers: string[];
  capabilities: FederationNodeCapabilities;
  registered_at: string;
  last_seen_at: string;
  status: string;
};

function osIcon(osType: string): string {
  const lower = osType.toLowerCase();
  if (lower.includes("mac") || lower.includes("darwin")) return "\uD83C\uDF4E";
  if (lower.includes("win")) return "\uD83E\uDE9F";
  if (lower.includes("linux")) return "\uD83D\uDC27";
  return "\uD83D\uDDA5\uFE0F";
}

function statusColor(lastSeen: string): "green" | "yellow" | "red" {
  const diff = Date.now() - new Date(lastSeen).getTime();
  const mins = diff / 60000;
  if (mins < 5) return "green";
  if (mins < 60) return "yellow";
  return "red";
}

function statusDotClass(color: "green" | "yellow" | "red"): string {
  switch (color) {
    case "green":
      return "bg-green-500 shadow-green-500/50 shadow-sm";
    case "yellow":
      return "bg-yellow-500 shadow-yellow-500/50 shadow-sm";
    case "red":
      return "bg-red-500 shadow-red-500/50 shadow-sm";
  }
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

async function loadNodes(): Promise<FederationNode[]> {
  const api = getApiBase();
  try {
    const res = await fetch(`${api}/api/federation/nodes`, { cache: "no-store" });
    if (!res.ok) return [];
    return (await res.json()) as FederationNode[];
  } catch {
    return [];
  }
}

export default async function NodesPage() {
  const nodes = await loadNodes();
  const apiBase = getApiBase();
  const sorted = [...nodes].sort((a, b) => a.hostname.localeCompare(b.hostname));

  return (
    <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-8 max-w-6xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight mb-2">Federation Nodes</h1>
        <p className="text-muted-foreground max-w-2xl leading-relaxed">
          All registered nodes in the Coherence federation. Monitor status, view capabilities, and send messages across the network.
        </p>
      </div>

      {/* Summary */}
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 text-sm space-y-2">
        <p className="text-muted-foreground">
          nodes {nodes.length} | online{" "}
          {nodes.filter((n) => statusColor(n.last_seen_at) === "green").length} | recent{" "}
          {nodes.filter((n) => statusColor(n.last_seen_at) === "yellow").length} | offline{" "}
          {nodes.filter((n) => statusColor(n.last_seen_at) === "red").length}
        </p>
      </section>

      {/* Node list */}
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3 text-sm">
        <h2 className="text-xl font-semibold">Registered Nodes</h2>
        {sorted.length === 0 && (
          <p className="text-muted-foreground">No federation nodes registered yet.</p>
        )}
        <ul className="space-y-3">
          {sorted.map((node) => {
            const color = statusColor(node.last_seen_at);
            return (
              <li
                key={node.node_id}
                className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-2"
              >
                <div className="flex items-center gap-2">
                  <span
                    className={`inline-block w-2.5 h-2.5 rounded-full ${statusDotClass(color)}`}
                  />
                  <span className="text-lg mr-1">{osIcon(node.os_type)}</span>
                  <span className="font-medium">{node.hostname}</span>
                  <span className="text-muted-foreground text-xs ml-auto">
                    {relativeTime(node.last_seen_at)}
                  </span>
                </div>

                <div className="flex flex-wrap gap-1.5">
                  {node.providers.map((p) => (
                    <span
                      key={`${node.node_id}-${p}`}
                      className="inline-flex items-center rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-0.5 text-xs font-medium text-amber-600 dark:text-amber-400"
                    >
                      {p}
                    </span>
                  ))}
                  {node.providers.length === 0 && (
                    <span className="text-muted-foreground text-xs">no providers</span>
                  )}
                </div>

                <p className="text-muted-foreground text-xs">
                  ID: {node.node_id} | OS: {node.os_type} | registered:{" "}
                  {new Date(node.registered_at).toLocaleDateString()}
                </p>

                {node.capabilities?.executors && node.capabilities.executors.length > 0 && (
                  <p className="text-xs text-muted-foreground">
                    executors: {node.capabilities.executors.join(", ")}
                  </p>
                )}
                {node.capabilities?.hardware && (
                  <p className="text-xs text-muted-foreground">
                    cpu: {node.capabilities.hardware.cpu_count ?? "?"} | memory:{" "}
                    {node.capabilities.hardware.memory_total_gb != null
                      ? `${node.capabilities.hardware.memory_total_gb.toFixed(1)} GB`
                      : "?"}
                    {node.capabilities.hardware.gpu_available && (
                      <> | gpu: {node.capabilities.hardware.gpu_type ?? "yes"}</>
                    )}
                  </p>
                )}
              </li>
            );
          })}
        </ul>
      </section>

      <MessageForm
        nodes={sorted.map((n) => ({ node_id: n.node_id, hostname: n.hostname }))}
        apiBase={apiBase}
      />

      {/* Navigation */}
      <nav
        className="py-8 text-center space-y-2 border-t border-border/20"
        aria-label="Where to go next"
      >
        <p className="text-xs text-muted-foreground/60 uppercase tracking-wider">
          Where to go next
        </p>
        <div className="flex flex-wrap justify-center gap-4 text-sm">
          <Link href="/automation" className="text-amber-600 dark:text-amber-400 hover:underline">
            Automation
          </Link>
          <Link href="/flow" className="text-amber-600 dark:text-amber-400 hover:underline">
            Flow
          </Link>
          <Link href="/specs" className="text-amber-600 dark:text-amber-400 hover:underline">
            Specs
          </Link>
        </div>
      </nav>
    </main>
  );
}
