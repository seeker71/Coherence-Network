import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";
import { withWorkspaceScope } from "@/lib/workspace";
import { getActiveWorkspaceFromCookie } from "@/lib/workspace-server";

export const metadata: Metadata = {
  title: "Projects",
  description: "Workspace projects grouping ideas.",
};

type WorkspaceProject = {
  id: string;
  name: string;
  description: string | null;
  workspace_id: string;
  idea_count: number;
  created_by: string | null;
  created_at: string;
};

type ProjectListResponse = {
  projects: WorkspaceProject[];
  total: number;
};

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

export default async function ProjectsPage() {
  const API = getApiBase();
  const workspaceId = await getActiveWorkspaceFromCookie();
  let data: ProjectListResponse | null = null;
  let error: string | null = null;

  try {
    const url = withWorkspaceScope(
      `${API}/api/workspaces/coherence-network/projects`,
      workspaceId,
    );
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    data = (await res.json()) as ProjectListResponse;
  } catch (e) {
    error = String(e);
  }

  const projects = data?.projects ?? [];

  return (
    <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-8 max-w-5xl mx-auto space-y-8">
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 sm:p-7 space-y-3">
        <p className="text-sm text-muted-foreground">Workspace</p>
        <h1 className="text-3xl md:text-4xl font-light tracking-tight">
          Projects
        </h1>
        <p className="max-w-3xl text-muted-foreground">
          Projects group related ideas within the workspace. Each project
          collects ideas around a shared theme or goal.
        </p>
        <div className="flex flex-wrap gap-2">
          <Link
            href="/ideas"
            className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200"
          >
            Ideas
          </Link>
          <Link
            href="/teams"
            className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200"
          >
            Team
          </Link>
          <Link
            href="/activity"
            className="rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200"
          >
            Activity
          </Link>
        </div>
      </section>

      {error ? (
        <p className="text-sm text-destructive">
          Could not load projects: {error}
        </p>
      ) : null}

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-3">
        <p className="text-sm text-muted-foreground">
          {projects.length} {projects.length === 1 ? "project" : "projects"}
        </p>

        {projects.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No projects created in this workspace yet.
          </p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {projects.map((proj) => (
              <Link
                key={proj.id}
                href={`/projects/${encodeURIComponent(proj.id)}`}
                className="rounded-xl border border-border/20 bg-background/40 p-5 space-y-2 hover:border-border/50 transition-all duration-200"
              >
                <h3 className="font-medium text-foreground">{proj.name}</h3>
                {proj.description ? (
                  <p className="text-sm text-muted-foreground line-clamp-2">
                    {proj.description}
                  </p>
                ) : (
                  <p className="text-sm text-muted-foreground italic">
                    No description
                  </p>
                )}
                <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground pt-1">
                  <span className="inline-flex items-center rounded-full bg-blue-500/10 px-2 py-0.5 text-blue-500 font-medium">
                    {proj.idea_count}{" "}
                    {proj.idea_count === 1 ? "idea" : "ideas"}
                  </span>
                  <span>Created {formatDate(proj.created_at)}</span>
                  {proj.created_by ? <span>by {proj.created_by}</span> : null}
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
