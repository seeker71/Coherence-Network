import type { Metadata } from "next";
import { getApiBase } from "@/lib/api";

export const metadata: Metadata = {
  title: "Registry Status | Coherence Network",
  description: "MCP and skill registry submission status and npm download counts for coherence-mcp-server.",
};

type RegistryEntry = {
  name: string;
  status: "live" | "pending" | "unknown" | "rejected";
  listing_url: string | null;
  installs: number | null;
};

type RegistryStats = {
  npm_weekly_downloads: number;
  npm_total_downloads: number;
  registries: RegistryEntry[];
  fetched_at: string;
  fetched_error: string | null;
};

const REGISTRY_LABELS: Record<string, { label: string; url: string; type: string }> = {
  smithery:  { label: "Smithery",   url: "https://smithery.ai",   type: "MCP server" },
  glama:     { label: "Glama",      url: "https://glama.ai",      type: "MCP server" },
  pulsemcp:  { label: "PulseMCP",   url: "https://pulsemcp.com",  type: "MCP server" },
  mcp_so:    { label: "mcp.so",     url: "https://mcp.so",        type: "MCP server" },
  skills_sh: { label: "skills.sh",  url: "https://skills.sh",     type: "Skill" },
  askill_sh: { label: "askill.sh",  url: "https://askill.sh",     type: "Skill" },
};

const STATUS_CLASSES: Record<string, string> = {
  live:     "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
  pending:  "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
  unknown:  "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
  rejected: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
};

async function fetchRegistryStats(): Promise<RegistryStats | null> {
  try {
    const res = await fetch(`${getApiBase()}/api/registry/stats`, {
      next: { revalidate: 3600 },
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

function Badge({ status }: { status: string }) {
  const cls = STATUS_CLASSES[status] ?? STATUS_CLASSES.unknown;
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}>
      {status}
    </span>
  );
}

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 p-5 flex flex-col gap-1">
      <span className="text-xs text-zinc-500 uppercase tracking-wide">{label}</span>
      <span className="text-2xl font-bold text-zinc-900 dark:text-zinc-50">{value}</span>
      {sub && <span className="text-xs text-zinc-400">{sub}</span>}
    </div>
  );
}

export default async function RegistryPage() {
  const stats = await fetchRegistryStats();

  const liveCount = stats?.registries.filter((r) => r.status === "live").length ?? 0;

  return (
    <main className="max-w-4xl mx-auto px-4 py-10 space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-zinc-900 dark:text-zinc-50">Registry Status</h1>
        <p className="mt-2 text-zinc-500">
          Submission status for{" "}
          <a
            href="https://www.npmjs.com/package/coherence-mcp-server"
            target="_blank"
            rel="noopener noreferrer"
            className="underline"
          >
            coherence-mcp-server
          </a>{" "}
          across MCP and skill registries.
        </p>
      </div>

      {stats ? (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <StatCard
              label="npm weekly downloads"
              value={stats.npm_weekly_downloads.toLocaleString()}
            />
            <StatCard
              label="npm total downloads"
              value={stats.npm_total_downloads.toLocaleString()}
            />
            <StatCard
              label="registries live"
              value={`${liveCount} / ${stats.registries.length}`}
            />
            <StatCard
              label="last checked"
              value={new Date(stats.fetched_at).toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
                year: "numeric",
              })}
              sub={new Date(stats.fetched_at).toLocaleTimeString("en-US", {
                hour: "2-digit",
                minute: "2-digit",
                timeZoneName: "short",
              })}
            />
          </div>

          {stats.fetched_error && (
            <div className="rounded border border-yellow-300 bg-yellow-50 dark:bg-yellow-900/20 px-4 py-3 text-sm text-yellow-700 dark:text-yellow-300">
              npm fetch error: {stats.fetched_error}
            </div>
          )}

          <div className="rounded-lg border border-zinc-200 dark:border-zinc-700 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-zinc-50 dark:bg-zinc-800">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-zinc-600 dark:text-zinc-300">Registry</th>
                  <th className="text-left px-4 py-3 font-medium text-zinc-600 dark:text-zinc-300">Type</th>
                  <th className="text-left px-4 py-3 font-medium text-zinc-600 dark:text-zinc-300">Status</th>
                  <th className="text-right px-4 py-3 font-medium text-zinc-600 dark:text-zinc-300">Weekly installs</th>
                  <th className="text-left px-4 py-3 font-medium text-zinc-600 dark:text-zinc-300">Listing</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
                {stats.registries.map((entry) => {
                  const meta = REGISTRY_LABELS[entry.name];
                  return (
                    <tr key={entry.name} className="hover:bg-zinc-50 dark:hover:bg-zinc-800/50">
                      <td className="px-4 py-3 font-medium text-zinc-900 dark:text-zinc-100">
                        {meta ? (
                          <a
                            href={meta.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="hover:underline"
                          >
                            {meta.label}
                          </a>
                        ) : (
                          entry.name
                        )}
                      </td>
                      <td className="px-4 py-3 text-zinc-500">{meta?.type ?? "—"}</td>
                      <td className="px-4 py-3">
                        <Badge status={entry.status} />
                      </td>
                      <td className="px-4 py-3 text-right text-zinc-700 dark:text-zinc-300">
                        {entry.installs != null ? entry.installs.toLocaleString() : "—"}
                      </td>
                      <td className="px-4 py-3">
                        {entry.listing_url ? (
                          <a
                            href={entry.listing_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 dark:text-blue-400 hover:underline truncate max-w-[200px] block"
                          >
                            View listing
                          </a>
                        ) : (
                          <span className="text-zinc-400">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <div className="rounded-lg border border-zinc-200 dark:border-zinc-700 px-6 py-10 text-center text-zinc-500">
          Registry stats unavailable — API may be starting up.
        </div>
      )}

      <div className="rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 p-6 space-y-3">
        <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Install</h2>
        <div className="space-y-2 text-sm">
          <div>
            <span className="font-medium text-zinc-700 dark:text-zinc-300">MCP server:</span>
            <code className="ml-2 rounded bg-zinc-100 dark:bg-zinc-800 px-2 py-0.5 text-xs">
              npx coherence-mcp-server
            </code>
          </div>
          <div>
            <span className="font-medium text-zinc-700 dark:text-zinc-300">CLI:</span>
            <code className="ml-2 rounded bg-zinc-100 dark:bg-zinc-800 px-2 py-0.5 text-xs">
              npm i -g coherence-cli
            </code>
          </div>
        </div>
        <p className="text-xs text-zinc-400">
          Works with Claude, Cursor, Windsurf, and any MCP-compatible client.
        </p>
      </div>
    </main>
  );
}
