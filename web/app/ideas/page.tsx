import Link from "next/link";

import { getApiBase } from "@/lib/api";

type IdeaQuestion = {
  question: string;
  value_to_whole: number;
  estimated_cost: number;
  answer?: string | null;
  measured_delta?: number | null;
};

type IdeaWithScore = {
  id: string;
  name: string;
  description: string;
  potential_value: number;
  actual_value: number;
  estimated_cost: number;
  actual_cost: number;
  confidence: number;
  resistance_risk: number;
  manifestation_status: string;
  interfaces: string[];
  open_questions: IdeaQuestion[];
  free_energy_score: number;
  value_gap: number;
};

type IdeasResponse = {
  ideas: IdeaWithScore[];
  summary: {
    total_ideas: number;
    unvalidated_ideas: number;
    validated_ideas: number;
    total_potential_value: number;
    total_actual_value: number;
    total_value_gap: number;
  };
};

async function loadIdeas(): Promise<IdeasResponse> {
  const API = getApiBase();
  const res = await fetch(`${API}/api/ideas`, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as IdeasResponse;
}

export default async function IdeasPage() {
  const data = await loadIdeas();

  const ideas = [...data.ideas].sort((a, b) => b.free_energy_score - a.free_energy_score);

  return (
    <main className="min-h-screen p-8 max-w-5xl mx-auto space-y-6">
      <div className="flex flex-wrap gap-3 text-sm">
        <Link href="/" className="text-muted-foreground hover:text-foreground">
          ← Home
        </Link>
        <Link href="/portfolio" className="text-muted-foreground hover:text-foreground">
          Portfolio
        </Link>
        <Link href="/specs" className="text-muted-foreground hover:text-foreground">
          Specs
        </Link>
        <Link href="/usage" className="text-muted-foreground hover:text-foreground">
          Usage
        </Link>
        <Link href="/flow" className="text-muted-foreground hover:text-foreground">
          Flow
        </Link>
        <Link href="/contributors" className="text-muted-foreground hover:text-foreground">
          Contributors
        </Link>
        <Link href="/contributions" className="text-muted-foreground hover:text-foreground">
          Contributions
        </Link>
        <Link href="/assets" className="text-muted-foreground hover:text-foreground">
          Assets
        </Link>
        <Link href="/tasks" className="text-muted-foreground hover:text-foreground">
          Tasks
        </Link>
        <Link href="/gates" className="text-muted-foreground hover:text-foreground">
          Gates
        </Link>
      </div>

      <h1 className="text-2xl font-bold">Ideas</h1>
      <p className="text-muted-foreground">Human interface for `GET /api/ideas`.</p>

      <section className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
        <div className="rounded border p-3">
          <p className="text-muted-foreground">Total ideas</p>
          <p className="text-lg font-semibold">{data.summary.total_ideas}</p>
        </div>
        <div className="rounded border p-3">
          <p className="text-muted-foreground">Actual value</p>
          <p className="text-lg font-semibold">{data.summary.total_actual_value}</p>
        </div>
        <div className="rounded border p-3">
          <p className="text-muted-foreground">Value gap</p>
          <p className="text-lg font-semibold">{data.summary.total_value_gap}</p>
        </div>
      </section>

      <section className="rounded border p-4 space-y-3">
        <p className="text-sm text-muted-foreground">Sorted by free energy score (higher first).</p>
        <ul className="space-y-2">
          {ideas.map((idea) => (
            <li key={idea.id} className="rounded border p-3 space-y-1">
              <div className="flex justify-between gap-3">
                <Link href={`/ideas/${encodeURIComponent(idea.id)}`} className="font-medium hover:underline">
                  {idea.name}
                </Link>
                <span className="text-muted-foreground">{idea.manifestation_status}</span>
              </div>
              <p className="text-sm text-muted-foreground">{idea.id}</p>
              <p className="text-sm">{idea.description}</p>
              <p className="text-sm text-muted-foreground">
                free_energy {idea.free_energy_score.toFixed(2)} | value_gap {idea.value_gap.toFixed(2)} | cost_est {idea.estimated_cost}
              </p>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
