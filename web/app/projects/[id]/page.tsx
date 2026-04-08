import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";

export const metadata: Metadata = {
  title: "Project Detail",
  description: "A single project with its linked ideas.",
};

type ProjectIdea = {
  id: string;
  name?: string;
  description?: string;
  status?: string;
};

type WorkspaceProjectDetail = {
  id: string;
  name: string;
  description: string | null;
  workspace_id: string;
  idea_count: number;
  created_by: string | null;
  created_at: string;
  ideas: ProjectIdea[];
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

type ProjectDetailPageProps = {
  params: Promise<{ id: string }>;
};

export default async function ProjectDetailPage({
  params,
}: ProjectDetailPageProps) {
  const { id } = await params;
  const API = getApiBase();
  let project: WorkspaceProjectDetail | null = null;
  let error: string | null = null;

  try {
    const res = await fetch(
      `${API}/api/projects/${encodeURIComponent(id)}`,
      { cache: "no-store" },
    );
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    project = (await res.json()) as WorkspaceProjectDetail;
  } catch (e) {
    error = String(e);
  }

  if (error || !project) {
    return (
      <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-8 max-w-5xl mx-auto space-y-8">
        <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 sm:p-7 space-y-3">
          <p className="text-sm text-muted-foreground">Project</p>
          <h1 className="text-3xl md:text-4xl font-light tracking-tight">
            Project Not Found
          </h1>
          <p className="text-muted-foreground">
            {error || "The requested project could not be loaded."}
          </p>
          <Link
            href="/projects"
            className="inline-block rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200"
          >
            Back to Projects
          </Link>
        </section>
      </main>
    );
  }

  const ideas = project.ideas ?? [];

  return (
    <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-8 max-w-5xl mx-auto space-y-8">
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 sm:p-7 space-y-3">
        <p className="text-sm text-muted-foreground">Project</p>
        <h1 className="text-3xl md:text-4xl font-light tracking-tight">
          {project.name}
        </h1>
        {project.description ? (
          <p className="max-w-3xl text-muted-foreground">
            {project.description}
          </p>
        ) : null}
        <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
          <span>Created {formatDate(project.created_at)}</span>
          {project.created_by ? <span>by {project.created_by}</span> : null}
          <span className="inline-flex items-center rounded-full bg-blue-500/10 px-2 py-0.5 text-xs text-blue-500 font-medium">
            {project.idea_count}{" "}
            {project.idea_count === 1 ? "idea" : "ideas"}
          </span>
        </div>
        <Link
          href="/projects"
          className="inline-block rounded-lg border border-border/30 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200"
        >
          All Projects
        </Link>
      </section>

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-3">
        <h2 className="text-lg font-medium">Linked Ideas</h2>
        <p className="text-sm text-muted-foreground">
          {ideas.length} {ideas.length === 1 ? "idea" : "ideas"} in this
          project
        </p>

        {ideas.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No ideas linked to this project yet.
          </p>
        ) : (
          <ul className="space-y-2 text-sm">
            {ideas.map((idea) => (
              <li
                key={idea.id}
                className="rounded-xl border border-border/20 bg-background/40 p-4 space-y-1"
              >
                <div className="flex items-center gap-2">
                  <Link
                    href={`/ideas/${encodeURIComponent(idea.id)}`}
                    className="font-medium hover:underline"
                  >
                    {idea.name || idea.id}
                  </Link>
                  {idea.status ? (
                    <span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                      {idea.status}
                    </span>
                  ) : null}
                </div>
                {idea.description ? (
                  <p className="text-muted-foreground line-clamp-2">
                    {idea.description}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
