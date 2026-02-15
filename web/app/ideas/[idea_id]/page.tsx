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

async function loadIdea(ideaId: string): Promise<IdeaWithScore> {
  const API = getApiBase();
  const res = await fetch(`${API}/api/ideas/${encodeURIComponent(ideaId)}`, { cache: "no-store" });
  if (res.status === 404) throw new Error("Idea not found");
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as IdeaWithScore;
}

export default async function IdeaDetailPage({ params }: { params: Promise<{ idea_id: string }> }) {
  const resolved = await params;
  const ideaId = decodeURIComponent(resolved.idea_id);
  const idea = await loadIdea(ideaId);

  return (
    <main className="min-h-screen p-8 max-w-5xl mx-auto space-y-6">
      <div className="flex gap-3">
        <Link href="/" className="text-muted-foreground hover:text-foreground">
          ← Home
        </Link>
        <Link href="/ideas" className="text-muted-foreground hover:text-foreground">
          Ideas
        </Link>
        <Link href="/portfolio" className="text-muted-foreground hover:text-foreground">
          Portfolio
        </Link>
      </div>

      <div className="space-y-1">
        <h1 className="text-2xl font-bold">{idea.name}</h1>
        <p className="text-muted-foreground">{idea.id}</p>
      </div>

      <p>{idea.description}</p>

      <section className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
        <div className="rounded border p-3">
          <p className="text-muted-foreground">Manifestation</p>
          <p className="text-lg font-semibold">{idea.manifestation_status}</p>
        </div>
        <div className="rounded border p-3">
          <p className="text-muted-foreground">Free energy</p>
          <p className="text-lg font-semibold">{idea.free_energy_score.toFixed(2)}</p>
        </div>
        <div className="rounded border p-3">
          <p className="text-muted-foreground">Value gap</p>
          <p className="text-lg font-semibold">{idea.value_gap.toFixed(2)}</p>
        </div>
        <div className="rounded border p-3">
          <p className="text-muted-foreground">Confidence</p>
          <p className="text-lg font-semibold">{idea.confidence.toFixed(2)}</p>
        </div>
      </section>

      <section className="rounded border p-4 space-y-3">
        <h2 className="font-semibold">Open Questions</h2>
        {idea.open_questions.length === 0 && <p className="text-sm text-muted-foreground">None</p>}
        <ul className="space-y-2 text-sm">
          {idea.open_questions.map((q) => {
            const roi = q.estimated_cost > 0 ? q.value_to_whole / q.estimated_cost : 0;
            return (
              <li key={q.question} className="rounded border p-3 space-y-1">
                <p className="font-medium">{q.question}</p>
                <p className="text-muted-foreground">
                  value {q.value_to_whole} | cost {q.estimated_cost} | ROI {roi.toFixed(2)}
                </p>
                {q.answer ? (
                  <p className="text-muted-foreground">answer: {q.answer}</p>
                ) : (
                  <p className="text-muted-foreground">answer: (unanswered)</p>
                )}
              </li>
            );
          })}
        </ul>
      </section>

      <section className="rounded border p-4 space-y-2 text-sm">
        <h2 className="font-semibold">API Links</h2>
        <p className="text-muted-foreground">Use these for machine inspection and automation.</p>
        <ul className="space-y-1">
          <li>
            <code>/api/ideas/{idea.id}</code>
          </li>
          <li>
            <code>/api/runtime/ideas/summary</code> (filter by <code>{idea.id}</code>)
          </li>
          <li>
            <code>/api/inventory/system-lineage</code>
          </li>
        </ul>
      </section>
    </main>
  );
}
