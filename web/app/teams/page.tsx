import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";
import { withWorkspaceScope } from "@/lib/workspace";
import { getActiveWorkspaceFromCookie } from "@/lib/workspace-server";

export const metadata: Metadata = {
  title: "Teams",
  description: "Workspace members and their roles.",
};

type WorkspaceMember = {
  contributor_id: string;
  contributor_name: string;
  role: string;
  status: string;
  joined_at: string | null;
};

type WorkspaceMembersResponse = {
  workspace_id: string;
  members: WorkspaceMember[];
  total: number;
};

function formatDate(iso: string | null): string {
  if (!iso) return "\u2014";
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return iso || "\u2014";
  }
}

function roleBadgeClass(role: string): string {
  switch (role) {
    case "owner":
      return "bg-amber-500/10 text-amber-500";
    case "admin":
      return "bg-blue-500/10 text-blue-500";
    case "member":
      return "bg-green-500/10 text-green-500";
    case "viewer":
      return "bg-muted text-muted-foreground";
    default:
      return "bg-muted text-muted-foreground";
  }
}

function statusBadgeClass(status: string): string {
  switch (status) {
    case "active":
      return "bg-green-500/10 text-green-500";
    case "pending":
      return "bg-amber-500/10 text-amber-500";
    default:
      return "bg-muted text-muted-foreground";
  }
}

export default async function TeamsPage() {
  const API = getApiBase();
  const workspaceId = await getActiveWorkspaceFromCookie();
  let data: WorkspaceMembersResponse | null = null;
  let error: string | null = null;

  try {
    const url = withWorkspaceScope(
      `${API}/api/workspaces/coherence-network/members`,
      workspaceId,
    );
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    data = (await res.json()) as WorkspaceMembersResponse;
  } catch (e) {
    error = String(e);
  }

  const members = data?.members ?? [];

  return (
    <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-8 max-w-5xl mx-auto space-y-8">
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 sm:p-7 space-y-3">
        <p className="text-sm text-muted-foreground">Workspace</p>
        <h1 className="text-3xl md:text-4xl font-light tracking-tight">
          Team Members
        </h1>
        <p className="max-w-3xl text-muted-foreground">
          Contributors who belong to this workspace, with their roles and
          membership status.
        </p>
        <div className="flex flex-wrap gap-2">
          <Link
            href="/contributors"
            className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200"
          >
            All Contributors
          </Link>
          <Link
            href="/activity"
            className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200"
          >
            Activity
          </Link>
          <Link
            href="/messages"
            className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200"
          >
            Messages
          </Link>
        </div>
      </section>

      {error ? (
        <p className="text-sm text-destructive">
          Could not load team members: {error}
        </p>
      ) : null}

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-3">
        <p className="text-sm text-muted-foreground">
          {members.length} {members.length === 1 ? "member" : "members"}
        </p>

        {members.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No team members found for this workspace.
          </p>
        ) : (
          <ul className="space-y-2 text-sm">
            {members.map((m) => (
              <li
                key={m.contributor_id}
                className="rounded-xl border border-border/20 bg-background/40 p-4 flex flex-wrap items-center justify-between gap-3"
              >
                <div className="flex items-center gap-3">
                  <Link
                    href={`/contributors?contributor_id=${encodeURIComponent(m.contributor_id)}`}
                    className="font-medium hover:underline"
                  >
                    {m.contributor_name || m.contributor_id}
                  </Link>
                  <span
                    className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${roleBadgeClass(m.role)}`}
                  >
                    {m.role}
                  </span>
                  <span
                    className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${statusBadgeClass(m.status)}`}
                  >
                    {m.status}
                  </span>
                </div>
                <span className="text-xs text-muted-foreground">
                  Joined {formatDate(m.joined_at)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
