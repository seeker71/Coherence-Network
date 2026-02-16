"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { getApiBase } from "@/lib/api";

const API_URL = getApiBase();

interface Project {
  name: string;
  ecosystem: string;
  version: string;
  description: string;
  dependency_count: number;
}

interface CoherenceResponse {
  score: number;
  components_with_data?: number; // 0–8; when < 8, score is preliminary (spec 020)
  components: Record<string, number>;
}

export default function ProjectPage() {
  const params = useParams();
  const ecosystem = params.ecosystem as string;
  const name = params.name as string;

  const [project, setProject] = useState<Project | null>(null);
  const [coherence, setCoherence] = useState<CoherenceResponse | null>(null);
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ecosystem || !name) return;
    let cancelled = false;
    async function fetchData() {
      try {
        const [projRes, cohRes] = await Promise.all([
          fetch(`${API_URL}/api/projects/${ecosystem}/${name}`),
          fetch(`${API_URL}/api/projects/${ecosystem}/${name}/coherence`),
        ]);
        if (cancelled) return;
        if (!projRes.ok) {
          if (projRes.status === 404) setError("Project not found");
          else setError(`HTTP ${projRes.status}`);
          setStatus("error");
          return;
        }
        const proj = await projRes.json();
        const coh = cohRes.ok ? await cohRes.json() : null;
        setProject(proj);
        setCoherence(coh);
        setStatus("ok");
      } catch (e) {
        if (!cancelled) {
          setError(String(e));
          setStatus("error");
        }
      }
    }
    fetchData();
    return () => {
      cancelled = true;
    };
  }, [ecosystem, name]);

  return (
    <main className="min-h-screen p-8 max-w-2xl mx-auto">
      <div className="mb-6">
        <Link href="/search" className="text-muted-foreground hover:text-foreground">
          ← Search
        </Link>
      </div>
      {status === "loading" && <p className="text-muted-foreground">Loading…</p>}
      {status === "error" && (
        <p className="text-destructive">
          {error}. Is the API running? Does this project exist?
        </p>
      )}
      {status === "ok" && project && (
        <article>
          <h1 className="text-2xl font-bold">
            {project.name}
            <span className="text-muted-foreground text-base font-normal ml-2">
              {project.ecosystem} @ {project.version}
            </span>
          </h1>
          {project.description && (
            <p className="mt-2 text-muted-foreground">{project.description}</p>
          )}
          <dl className="mt-6 space-y-2">
            <div>
              <dt className="text-sm text-muted-foreground">Dependencies</dt>
              <dd className="font-medium">{project.dependency_count}</dd>
            </div>
            {coherence && (
              <div>
                <dt className="text-sm text-muted-foreground">Coherence score</dt>
                <dd className="flex items-center gap-2">
                  <span className="font-medium">{coherence.score}</span>
                  <span className="text-xs text-muted-foreground">
                    (0.0–1.0)
                    {coherence.components_with_data != null &&
                      coherence.components_with_data < 8 && (
                        <> — preliminary ({coherence.components_with_data} of 8 signals)</>
                      )}
                  </span>
                </dd>
                <ul className="mt-2 text-sm text-muted-foreground space-y-0.5">
                  {Object.entries(coherence.components).map(([k, v]) => (
                    <li key={k}>
                      {k.replace(/_/g, " ")}: {v}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </dl>
        </article>
      )}
    </main>
  );
}
