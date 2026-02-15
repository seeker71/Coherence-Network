"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface IdeaQuestionRow {
  idea_id: string;
  idea_name: string;
  question: string;
  value_to_whole: number;
  estimated_cost: number;
  question_roi?: number;
  answer: string | null;
  measured_delta: number | null;
  answer_roi?: number;
}

interface RuntimeIdeaRow {
  idea_id: string;
  event_count: number;
  total_runtime_ms: number;
  runtime_cost_estimate: number;
}

interface RuntimeEventRow {
  endpoint: string;
  runtime_ms: number;
  runtime_cost_estimate: number;
  status_code: number;
}

interface LineageLinkRow {
  lineage_id: string;
  idea_id: string;
  spec_id: string;
  implementation_refs: string[];
  estimated_cost: number;
  valuation: {
    measured_value_total: number;
    estimated_cost: number;
    roi_ratio: number;
    usage_events_count: number;
  } | null;
}

interface ContributorAttributionRow {
  lineage_id: string;
  idea_id: string;
  spec_id: string;
  role: string;
  contributor: string;
  perspective: "human" | "machine" | "unknown";
  estimated_cost: number;
  measured_value_total: number;
  roi_ratio: number;
}

interface RoiIdeaRow {
  idea_id: string;
  idea_name: string;
  manifestation_status: string;
  potential_value: number;
  actual_value: number;
  estimated_cost: number;
  actual_cost: number;
  estimated_roi: number;
  actual_roi: number | null;
  missing_actual_roi: boolean;
}

interface InventoryResponse {
  ideas: {
    summary: {
      total_ideas: number;
      total_potential_value: number;
      total_actual_value: number;
      total_value_gap: number;
    };
    items: Array<{
      id: string;
      name: string;
      description: string;
      manifestation_status: string;
      free_energy_score: number;
      potential_value: number;
      actual_value: number;
      estimated_cost: number;
      actual_cost: number;
      value_gap: number;
      interfaces: string[];
    }>;
  };
  manifestations: {
    total: number;
    by_status: Record<string, number>;
    missing_count: number;
    missing: Array<{
      idea_id: string;
      idea_name: string;
      manifestation_status: string;
      actual_value: number;
      actual_cost: number;
    }>;
    items: Array<{
      idea_id: string;
      idea_name: string;
      manifestation_status: string;
      actual_value: number;
      actual_cost: number;
    }>;
  };
  questions: {
    answered_count: number;
    unanswered_count: number;
    answered: IdeaQuestionRow[];
    unanswered: IdeaQuestionRow[];
  };
  runtime: {
    ideas: RuntimeIdeaRow[];
  };
  implementation_usage: {
    lineage_links_count: number;
    usage_events_count: number;
    lineage_links: LineageLinkRow[];
  };
  assets: {
    total: number;
    by_type: Record<string, number>;
    coverage: {
      api_routes_total: number;
      web_api_usage_paths_total: number;
      api_web_gap_count: number;
    };
    items: Array<{
      asset_id: string;
      asset_type: string;
      name: string;
      linked_id: string;
      status: string;
      estimated_value: number;
      estimated_cost: number;
      machine_path: string;
      human_path: string;
    }>;
  };
  contributors: {
    attribution_count: number;
    by_perspective: {
      human: number;
      machine: number;
      unknown: number;
    };
    attributions: ContributorAttributionRow[];
  };
  roi_insights: {
    most_estimated_roi: RoiIdeaRow[];
    least_estimated_roi: RoiIdeaRow[];
    most_actual_roi: RoiIdeaRow[];
    least_actual_roi: RoiIdeaRow[];
    missing_actual_roi_high_potential: RoiIdeaRow[];
  };
  next_roi_work: {
    selection_basis: string;
    item: (IdeaQuestionRow & { idea_estimated_roi?: number }) | null;
  };
  operating_console: {
    idea_id: string;
    estimated_roi: number;
    estimated_roi_rank: number | null;
    is_next: boolean;
  };
  evidence_contract: {
    checks: Array<{
      subsystem_id: string;
      standing_question: string;
      claim: string;
      falsifier: string;
      owner_role: string;
      auto_action: string;
      status: "ok" | "needs_attention";
    }>;
    violations_count: number;
    violations: Array<{
      subsystem_id: string;
      claim: string;
      falsifier: string;
      owner_role: string;
      auto_action: string;
      status: "needs_attention";
    }>;
  };
}

export default function PortfolioPage() {
  const [inventory, setInventory] = useState<InventoryResponse | null>(null);
  const [runtimeEvents, setRuntimeEvents] = useState<RuntimeEventRow[]>([]);
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [error, setError] = useState<string | null>(null);
  const [draftAnswers, setDraftAnswers] = useState<Record<string, string>>({});
  const [draftDeltas, setDraftDeltas] = useState<Record<string, string>>({});
  const [submittingKey, setSubmittingKey] = useState<string | null>(null);
  const [ideaQuery, setIdeaQuery] = useState("");
  const [ideaStatusFilter, setIdeaStatusFilter] = useState<"all" | "none" | "partial" | "validated">("all");
  const [selectedIdeaId, setSelectedIdeaId] = useState<string>("");
  const [ideaPage, setIdeaPage] = useState(1);

  async function loadInventory() {
    setStatus("loading");
    setError(null);
    try {
      const [inventoryRes, eventsRes] = await Promise.all([
        fetch(`${API_URL}/api/inventory/system-lineage?runtime_window_seconds=86400`, {
          cache: "no-store",
        }),
        fetch(`${API_URL}/api/runtime/events?limit=1000`, {
          cache: "no-store",
        }),
      ]);
      const inventoryJson = await inventoryRes.json();
      const eventsJson = await eventsRes.json();
      if (!inventoryRes.ok) throw new Error(JSON.stringify(inventoryJson));
      if (!eventsRes.ok) throw new Error(JSON.stringify(eventsJson));
      setInventory(inventoryJson);
      setRuntimeEvents(Array.isArray(eventsJson) ? eventsJson : []);
      setStatus("ok");
    } catch (e) {
      setStatus("error");
      setError(String(e));
    }
  }

  useEffect(() => {
    void loadInventory();
  }, []);

  useEffect(() => {
    if (!inventory) return;
    const hasSelected = inventory.ideas.items.some((i) => i.id === selectedIdeaId);
    if (!hasSelected && inventory.ideas.items.length > 0) {
      setSelectedIdeaId(inventory.ideas.items[0].id);
    }
  }, [inventory, selectedIdeaId]);

  const topRuntime = useMemo(() => {
    if (!inventory) return [];
    return [...inventory.runtime.ideas]
      .sort((a, b) => b.runtime_cost_estimate - a.runtime_cost_estimate)
      .slice(0, 5);
  }, [inventory]);

  const uiOpenQuestions = useMemo(() => {
    if (!inventory) return [];
    return inventory.questions.unanswered.filter((q) => q.idea_id === "web-ui-governance");
  }, [inventory]);

  const uiAnsweredQuestions = useMemo(() => {
    if (!inventory) return [];
    return inventory.questions.answered.filter((q) => q.idea_id === "web-ui-governance");
  }, [inventory]);

  const uiElementInsights = useMemo(() => {
    const uiEvents = runtimeEvents.filter((event) => {
      if (typeof event.endpoint !== "string" || event.endpoint.length < 1) return false;
      if (!event.endpoint.startsWith("/")) return false;
      if (event.endpoint.startsWith("/api/") && event.endpoint !== "/api/runtime-beacon") return false;
      return true;
    });

    const perEndpoint = new Map<
      string,
      { endpoint: string; event_count: number; total_cost: number; value_proxy: number }
    >();
    for (const event of uiEvents) {
      const key = event.endpoint;
      const current = perEndpoint.get(key) || {
        endpoint: key,
        event_count: 0,
        total_cost: 0,
        value_proxy: 0,
      };
      current.event_count += 1;
      current.total_cost += Number(event.runtime_cost_estimate || 0);
      if ((event.status_code || 500) < 400) current.value_proxy += 1;
      perEndpoint.set(key, current);
    }

    const rows = [...perEndpoint.values()].map((row) => {
      const valuePerCost = row.total_cost > 0 ? row.value_proxy / row.total_cost : 0;
      const costPerValue = row.value_proxy > 0 ? row.total_cost / row.value_proxy : row.total_cost;
      return {
        ...row,
        value_per_cost: valuePerCost,
        cost_per_value: costPerValue,
      };
    });

    if (rows.length === 0) {
      return { highestValueLeastCost: null, highestCostLeastValue: null, rows: [] };
    }

    const byValuePerCost = [...rows].sort((a, b) => b.value_per_cost - a.value_per_cost || a.total_cost - b.total_cost);
    const byCostPerValue = [...rows].sort(
      (a, b) => b.cost_per_value - a.cost_per_value || b.total_cost - a.total_cost
    );
    return {
      highestValueLeastCost: byValuePerCost[0],
      highestCostLeastValue: byCostPerValue[0],
      rows,
    };
  }, [runtimeEvents]);

  const ideaQuestionMap = useMemo(() => {
    if (!inventory) {
      return new Map<string, { answered: IdeaQuestionRow[]; unanswered: IdeaQuestionRow[] }>();
    }
    const map = new Map<string, { answered: IdeaQuestionRow[]; unanswered: IdeaQuestionRow[] }>();
    for (const q of inventory.questions.unanswered) {
      const row = map.get(q.idea_id) || { answered: [], unanswered: [] };
      row.unanswered.push(q);
      map.set(q.idea_id, row);
    }
    for (const q of inventory.questions.answered) {
      const row = map.get(q.idea_id) || { answered: [], unanswered: [] };
      row.answered.push(q);
      map.set(q.idea_id, row);
    }
    return map;
  }, [inventory]);

  const filteredIdeas = useMemo(() => {
    if (!inventory) return [];
    const q = ideaQuery.trim().toLowerCase();
    return inventory.ideas.items.filter((idea) => {
      if (ideaStatusFilter !== "all" && idea.manifestation_status !== ideaStatusFilter) return false;
      if (!q) return true;
      return (
        idea.id.toLowerCase().includes(q) ||
        idea.name.toLowerCase().includes(q) ||
        idea.description.toLowerCase().includes(q)
      );
    });
  }, [inventory, ideaQuery, ideaStatusFilter]);

  const pagedIdeas = useMemo(() => {
    const pageSize = 10;
    const start = (ideaPage - 1) * pageSize;
    return filteredIdeas.slice(start, start + pageSize);
  }, [filteredIdeas, ideaPage]);

  const totalIdeaPages = Math.max(1, Math.ceil(filteredIdeas.length / 10));

  useEffect(() => {
    if (ideaPage > totalIdeaPages) setIdeaPage(totalIdeaPages);
    if (ideaPage < 1) setIdeaPage(1);
  }, [ideaPage, totalIdeaPages]);

  const selectedIdea = useMemo(() => {
    if (!inventory) return null;
    return inventory.ideas.items.find((i) => i.id === selectedIdeaId) || null;
  }, [inventory, selectedIdeaId]);

  const selectedIdeaQuestions = useMemo(() => {
    if (!selectedIdea) return { answered: [] as IdeaQuestionRow[], unanswered: [] as IdeaQuestionRow[] };
    return ideaQuestionMap.get(selectedIdea.id) || { answered: [], unanswered: [] };
  }, [selectedIdea, ideaQuestionMap]);

  const selectedIdeaLineage = useMemo(() => {
    if (!inventory || !selectedIdea) return [];
    return inventory.implementation_usage.lineage_links.filter((l) => l.idea_id === selectedIdea.id);
  }, [inventory, selectedIdea]);

  const selectedIdeaManifestation = useMemo(() => {
    if (!inventory || !selectedIdea) return null;
    return inventory.manifestations.items.find((m) => m.idea_id === selectedIdea.id) || null;
  }, [inventory, selectedIdea]);

  const selectedIdeaRuntime = useMemo(() => {
    if (!inventory || !selectedIdea) return null;
    return inventory.runtime.ideas.find((r) => r.idea_id === selectedIdea.id) || null;
  }, [inventory, selectedIdea]);

  async function submitAnswer(question: IdeaQuestionRow) {
    const key = `${question.idea_id}::${question.question}`;
    const answer = (draftAnswers[key] || "").trim();
    if (!answer) return;
    const deltaRaw = (draftDeltas[key] || "").trim();
    const measuredDelta = deltaRaw ? Number(deltaRaw) : undefined;
    setSubmittingKey(key);
    try {
      const res = await fetch(`${API_URL}/api/ideas/${encodeURIComponent(question.idea_id)}/questions/answer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: question.question,
          answer,
          measured_delta: Number.isFinite(measuredDelta) ? measuredDelta : undefined,
        }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(JSON.stringify(json));
      setDraftAnswers((prev) => ({ ...prev, [key]: "" }));
      setDraftDeltas((prev) => ({ ...prev, [key]: "" }));
      await loadInventory();
    } catch (e) {
      setStatus("error");
      setError(String(e));
    } finally {
      setSubmittingKey(null);
    }
  }

  return (
    <main className="min-h-screen p-8 max-w-5xl mx-auto space-y-6">
      <div>
        <Link href="/" className="text-muted-foreground hover:text-foreground">
          ← Coherence Network
        </Link>
      </div>
      <h1 className="text-2xl font-bold">Portfolio Cockpit</h1>
      <p className="text-muted-foreground">
        Human interface for ROI-first idea governance: unanswered questions, runtime cost, and value gap.
      </p>

      {status === "loading" && <p className="text-muted-foreground">Loading portfolio data…</p>}
      {status === "error" && error && <p className="text-destructive">Error: {error}</p>}

      {status === "ok" && inventory && (
        <>
          <section className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            <div className="rounded border p-3">
              <p className="text-muted-foreground">Ideas</p>
              <p className="text-lg font-semibold">{inventory.ideas.summary.total_ideas}</p>
            </div>
            <div className="rounded border p-3">
              <p className="text-muted-foreground">Value gap</p>
              <p className="text-lg font-semibold">{inventory.ideas.summary.total_value_gap}</p>
            </div>
            <div className="rounded border p-3">
              <p className="text-muted-foreground">Questions unanswered</p>
              <p className="text-lg font-semibold">{inventory.questions.unanswered_count}</p>
            </div>
            <div className="rounded border p-3">
              <p className="text-muted-foreground">Lineage links</p>
              <p className="text-lg font-semibold">{inventory.implementation_usage.lineage_links_count}</p>
            </div>
            <div className="rounded border p-3">
              <p className="text-muted-foreground">Registered assets</p>
              <p className="text-lg font-semibold">{inventory.assets.total}</p>
            </div>
          </section>

          <section className="rounded border p-4 space-y-3">
            <h2 className="font-semibold">System Asset Registry</h2>
            <p className="text-sm text-muted-foreground">
              All system parts are registered as assets for machine and human inspection.
            </p>
            <div className="grid md:grid-cols-3 gap-3 text-sm">
              <div className="rounded border p-3">
                <p className="text-muted-foreground">API routes tracked</p>
                <p className="text-lg font-semibold">{inventory.assets.coverage.api_routes_total}</p>
              </div>
              <div className="rounded border p-3">
                <p className="text-muted-foreground">Web API usage tracked</p>
                <p className="text-lg font-semibold">{inventory.assets.coverage.web_api_usage_paths_total}</p>
              </div>
              <div className="rounded border p-3">
                <p className="text-muted-foreground">API↔Web gaps</p>
                <p className="text-lg font-semibold">{inventory.assets.coverage.api_web_gap_count}</p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2 text-xs">
              {Object.entries(inventory.assets.by_type).map(([k, v]) => (
                <span key={`assettype:${k}`} className="rounded border px-2 py-1">
                  {k}: {v}
                </span>
              ))}
            </div>
            <ul className="space-y-2 text-sm max-h-72 overflow-auto pr-1">
              {inventory.assets.items.slice(0, 120).map((row) => (
                <li key={row.asset_id} className="rounded border p-2">
                  <p className="font-medium">
                    {row.name} <span className="text-muted-foreground">({row.asset_type})</span>
                  </p>
                  <p className="text-muted-foreground">
                    status {row.status} | est value {row.estimated_value.toFixed(2)} | est cost {row.estimated_cost.toFixed(2)}
                  </p>
                  <p className="text-muted-foreground">
                    machine <code>{row.machine_path}</code> | human <code>{row.human_path}</code>
                  </p>
                </li>
              ))}
            </ul>
          </section>

          <section className="rounded border p-4 space-y-3">
            <h2 className="font-semibold">Idea Explorer</h2>
            <p className="text-sm text-muted-foreground">
              Browse every idea, inspect questions and answers, implementation/manifestation process evidence, and cost-benefit signals.
            </p>
            <div className="grid md:grid-cols-3 gap-2">
              <Input
                placeholder="Search idea id, name, description"
                value={ideaQuery}
                onChange={(e) => {
                  setIdeaQuery(e.target.value);
                  setIdeaPage(1);
                }}
              />
              <select
                className="rounded border bg-background px-3 py-2 text-sm"
                value={ideaStatusFilter}
                onChange={(e) => {
                  setIdeaStatusFilter(e.target.value as "all" | "none" | "partial" | "validated");
                  setIdeaPage(1);
                }}
              >
                <option value="all">All manifestations</option>
                <option value="none">None</option>
                <option value="partial">Partial</option>
                <option value="validated">Validated</option>
              </select>
              <div className="flex items-center justify-end text-sm text-muted-foreground">
                {filteredIdeas.length} ideas
              </div>
            </div>

            <div className="grid md:grid-cols-12 gap-3">
              <div className="md:col-span-4 space-y-2">
                <ul className="space-y-2 max-h-[28rem] overflow-auto pr-1">
                  {pagedIdeas.map((idea) => (
                    <li key={idea.id}>
                      <button
                        type="button"
                        onClick={() => setSelectedIdeaId(idea.id)}
                        className={`w-full text-left rounded border p-2 ${
                          selectedIdeaId === idea.id ? "border-foreground" : "border-border"
                        }`}
                      >
                        <p className="font-medium">{idea.name}</p>
                        <p className="text-xs text-muted-foreground">{idea.id}</p>
                        <p className="text-xs text-muted-foreground">
                          {idea.manifestation_status} | est ROI{" "}
                          {(idea.estimated_cost > 0 ? idea.potential_value / idea.estimated_cost : 0).toFixed(2)}
                        </p>
                      </button>
                    </li>
                  ))}
                </ul>
                <div className="flex items-center justify-between text-sm">
                  <Button variant="outline" disabled={ideaPage <= 1} onClick={() => setIdeaPage((p) => Math.max(1, p - 1))}>
                    Prev
                  </Button>
                  <span className="text-muted-foreground">
                    Page {ideaPage} / {totalIdeaPages}
                  </span>
                  <Button
                    variant="outline"
                    disabled={ideaPage >= totalIdeaPages}
                    onClick={() => setIdeaPage((p) => Math.min(totalIdeaPages, p + 1))}
                  >
                    Next
                  </Button>
                </div>
              </div>

              <div className="md:col-span-8 rounded border p-3 space-y-3">
                {!selectedIdea ? (
                  <p className="text-sm text-muted-foreground">Select an idea to inspect details.</p>
                ) : (
                  <>
                    <div>
                      <p className="text-lg font-semibold">{selectedIdea.name}</p>
                      <p className="text-sm text-muted-foreground">{selectedIdea.id}</p>
                      <p className="text-sm text-muted-foreground">{selectedIdea.description}</p>
                    </div>

                    <div className="grid md:grid-cols-3 gap-2 text-sm">
                      <div className="rounded border p-2">
                        <p className="text-muted-foreground">Manifestation</p>
                        <p className="font-medium">{selectedIdea.manifestation_status}</p>
                      </div>
                      <div className="rounded border p-2">
                        <p className="text-muted-foreground">Value / Cost</p>
                        <p className="font-medium">
                          est {selectedIdea.potential_value.toFixed(2)} / {selectedIdea.estimated_cost.toFixed(2)}
                        </p>
                        <p className="text-muted-foreground">
                          act {selectedIdea.actual_value.toFixed(2)} / {selectedIdea.actual_cost.toFixed(2)}
                        </p>
                      </div>
                      <div className="rounded border p-2">
                        <p className="text-muted-foreground">ROI</p>
                        <p className="font-medium">
                          est {(selectedIdea.estimated_cost > 0 ? selectedIdea.potential_value / selectedIdea.estimated_cost : 0).toFixed(2)}
                        </p>
                        <p className="text-muted-foreground">
                          act {(selectedIdea.actual_cost > 0 ? selectedIdea.actual_value / selectedIdea.actual_cost : 0).toFixed(2)}
                        </p>
                      </div>
                    </div>

                    <div className="rounded border p-2 text-sm">
                      <p className="font-medium">Questions</p>
                      <p className="text-muted-foreground">
                        unanswered {selectedIdeaQuestions.unanswered.length} | answered {selectedIdeaQuestions.answered.length}
                      </p>
                      <ul className="mt-2 space-y-2">
                        {selectedIdeaQuestions.unanswered.slice(0, 8).map((q) => (
                          <li key={`open:${q.idea_id}:${q.question}`} className="rounded border p-2">
                            <p>{q.question}</p>
                            <p className="text-xs text-muted-foreground">
                              value {q.value_to_whole} | cost {q.estimated_cost} | ROI{" "}
                              {(q.estimated_cost > 0 ? q.value_to_whole / q.estimated_cost : 0).toFixed(2)}
                            </p>
                          </li>
                        ))}
                        {selectedIdeaQuestions.answered.slice(0, 8).map((q) => (
                          <li key={`ans:${q.idea_id}:${q.question}`} className="rounded border p-2">
                            <p>{q.question}</p>
                            <p className="text-xs text-muted-foreground">{q.answer || "No answer text"}</p>
                            <p className="text-xs text-muted-foreground">
                              measured delta {q.measured_delta === null ? "n/a" : q.measured_delta} | answer ROI{" "}
                              {(q.answer_roi || 0).toFixed(2)}
                            </p>
                          </li>
                        ))}
                        {selectedIdeaQuestions.unanswered.length === 0 && selectedIdeaQuestions.answered.length === 0 && (
                          <li className="text-muted-foreground">No question rows found for this idea.</li>
                        )}
                      </ul>
                    </div>

                    <div className="rounded border p-2 text-sm">
                      <p className="font-medium">Implementation / Manifestation Process</p>
                      <p className="text-muted-foreground">
                        lineage links {selectedIdeaLineage.length} | interfaces {selectedIdea.interfaces.join(", ")}
                      </p>
                      <ul className="mt-2 space-y-2">
                        {selectedIdeaLineage.map((link) => (
                          <li key={link.lineage_id} className="rounded border p-2">
                            <p className="font-medium">spec {link.spec_id}</p>
                            <p className="text-xs text-muted-foreground">
                              refs: {link.implementation_refs.length > 0 ? link.implementation_refs.join(", ") : "none"}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              est cost {link.estimated_cost.toFixed(2)} | measured value{" "}
                              {(link.valuation?.measured_value_total || 0).toFixed(2)} | lineage ROI{" "}
                              {(link.valuation?.roi_ratio || 0).toFixed(2)}
                            </p>
                          </li>
                        ))}
                        {selectedIdeaLineage.length === 0 && (
                          <li className="text-muted-foreground">No lineage links yet for this idea.</li>
                        )}
                      </ul>
                    </div>

                    <div className="grid md:grid-cols-2 gap-2 text-sm">
                      <div className="rounded border p-2">
                        <p className="font-medium">Manifestation Runtime</p>
                        {selectedIdeaRuntime ? (
                          <p className="text-muted-foreground">
                            events {selectedIdeaRuntime.event_count} | runtime {selectedIdeaRuntime.total_runtime_ms.toFixed(2)}ms | cost $
                            {selectedIdeaRuntime.runtime_cost_estimate.toFixed(6)}
                          </p>
                        ) : (
                          <p className="text-muted-foreground">No runtime rows in selected window.</p>
                        )}
                      </div>
                      <div className="rounded border p-2">
                        <p className="font-medium">Manifestation Snapshot</p>
                        {selectedIdeaManifestation ? (
                          <p className="text-muted-foreground">
                            {selectedIdeaManifestation.manifestation_status} | value {selectedIdeaManifestation.actual_value.toFixed(2)} | cost{" "}
                            {selectedIdeaManifestation.actual_cost.toFixed(2)}
                          </p>
                        ) : (
                          <p className="text-muted-foreground">No manifestation snapshot row found.</p>
                        )}
                      </div>
                    </div>
                  </>
                )}
              </div>
            </div>
          </section>

          <section className="rounded border p-4 space-y-3">
            <h2 className="font-semibold">Idea Manifestations</h2>
            <div className="grid md:grid-cols-4 gap-3 text-sm">
              <div className="rounded border p-3">
                <p className="text-muted-foreground">None</p>
                <p className="text-lg font-semibold">{inventory.manifestations.by_status.none || 0}</p>
              </div>
              <div className="rounded border p-3">
                <p className="text-muted-foreground">Partial</p>
                <p className="text-lg font-semibold">{inventory.manifestations.by_status.partial || 0}</p>
              </div>
              <div className="rounded border p-3">
                <p className="text-muted-foreground">Validated</p>
                <p className="text-lg font-semibold">{inventory.manifestations.by_status.validated || 0}</p>
              </div>
              <div className="rounded border p-3">
                <p className="text-muted-foreground">Missing manifestations</p>
                <p className="text-lg font-semibold">{inventory.manifestations.missing_count}</p>
              </div>
            </div>
            <ul className="space-y-2 text-sm">
              {inventory.manifestations.items.map((row) => (
                <li key={`manifest:${row.idea_id}`} className="rounded border p-2 flex justify-between">
                  <span>{row.idea_id}</span>
                  <span className="text-muted-foreground">
                    {row.manifestation_status} | value {row.actual_value.toFixed(2)} | cost {row.actual_cost.toFixed(2)}
                  </span>
                </li>
              ))}
            </ul>
          </section>

          <section className="rounded border p-4 space-y-3">
            <h2 className="font-semibold">Operating Console ROI Queue</h2>
            <div className="grid md:grid-cols-2 gap-3 text-sm">
              <div className="rounded border p-3">
                <p className="font-medium">Operating Console Estimated ROI</p>
                <p className="text-muted-foreground">
                  {inventory.operating_console.estimated_roi.toFixed(2)} (rank{" "}
                  {inventory.operating_console.estimated_roi_rank ?? "n/a"})
                </p>
                <p className="text-muted-foreground">
                  next in queue: {inventory.operating_console.is_next ? "yes" : "no"}
                </p>
              </div>
              <div className="rounded border p-3">
                <p className="font-medium">Next ROI Work Item</p>
                {inventory.next_roi_work.item ? (
                  <>
                    <p className="text-muted-foreground">{inventory.next_roi_work.item.question}</p>
                    <p className="text-muted-foreground">
                      idea {inventory.next_roi_work.item.idea_id} | idea ROI{" "}
                      {(inventory.next_roi_work.item.idea_estimated_roi || 0).toFixed(2)} | question ROI{" "}
                      {(inventory.next_roi_work.item.question_roi || 0).toFixed(2)}
                    </p>
                  </>
                ) : (
                  <p className="text-muted-foreground">No queued ROI work item</p>
                )}
              </div>
            </div>
          </section>

          <section className="rounded border p-4 space-y-3">
            <h2 className="font-semibold">Evidence Contract</h2>
            <p className="text-sm text-muted-foreground">
              Regularly ask: what evidence supports this claim, what falsifies it, and who acts when it drifts.
            </p>
            <div className="grid md:grid-cols-2 gap-3 text-sm">
              <div className="rounded border p-3">
                <p className="font-medium">Violations</p>
                <p className="text-muted-foreground">{inventory.evidence_contract.violations_count}</p>
              </div>
              <div className="rounded border p-3">
                <p className="font-medium">Checks</p>
                <p className="text-muted-foreground">{inventory.evidence_contract.checks.length}</p>
              </div>
            </div>
            <ul className="space-y-2 text-sm">
              {inventory.evidence_contract.violations.length === 0 ? (
                <li className="rounded border p-2 text-muted-foreground">No evidence violations detected.</li>
              ) : (
                inventory.evidence_contract.violations.map((row) => (
                  <li key={`evidence:${row.subsystem_id}`} className="rounded border p-2">
                    <p className="font-medium">{row.subsystem_id}</p>
                    <p className="text-muted-foreground">{row.claim}</p>
                    <p className="text-muted-foreground">
                      falsifier: {row.falsifier} | owner: {row.owner_role}
                    </p>
                  </li>
                ))
              )}
            </ul>
          </section>

          <section className="rounded border p-4 space-y-3">
            <h2 className="font-semibold">Contributor Attribution (Human vs Machine)</h2>
            <div className="grid md:grid-cols-3 gap-3 text-sm">
              <div className="rounded border p-3">
                <p className="text-muted-foreground">Human attributions</p>
                <p className="text-lg font-semibold">{inventory.contributors.by_perspective.human}</p>
              </div>
              <div className="rounded border p-3">
                <p className="text-muted-foreground">Machine attributions</p>
                <p className="text-lg font-semibold">{inventory.contributors.by_perspective.machine}</p>
              </div>
              <div className="rounded border p-3">
                <p className="text-muted-foreground">Unknown attributions</p>
                <p className="text-lg font-semibold">{inventory.contributors.by_perspective.unknown}</p>
              </div>
            </div>
            <ul className="space-y-2 text-sm">
              {inventory.contributors.attributions.slice(0, 6).map((row) => (
                <li key={`${row.lineage_id}:${row.role}:${row.contributor}`} className="rounded border p-2">
                  <p className="font-medium">
                    {row.role}: {row.contributor} ({row.perspective})
                  </p>
                  <p className="text-muted-foreground">
                    idea {row.idea_id} | spec {row.spec_id} | lineage ROI {row.roi_ratio.toFixed(2)}
                  </p>
                </li>
              ))}
            </ul>
          </section>

          <section className="rounded border p-4 space-y-3">
            <h2 className="font-semibold">Idea ROI Rankings</h2>
            <div className="grid md:grid-cols-3 gap-3 text-sm">
              <div className="rounded border p-3">
                <p className="font-medium">Most estimated ROI</p>
                {inventory.roi_insights.most_estimated_roi[0] ? (
                  <p className="text-muted-foreground">
                    {inventory.roi_insights.most_estimated_roi[0].idea_id} (
                    {inventory.roi_insights.most_estimated_roi[0].estimated_roi.toFixed(2)})
                  </p>
                ) : (
                  <p className="text-muted-foreground">n/a</p>
                )}
              </div>
              <div className="rounded border p-3">
                <p className="font-medium">Least estimated ROI</p>
                {inventory.roi_insights.least_estimated_roi[0] ? (
                  <p className="text-muted-foreground">
                    {inventory.roi_insights.least_estimated_roi[0].idea_id} (
                    {inventory.roi_insights.least_estimated_roi[0].estimated_roi.toFixed(2)})
                  </p>
                ) : (
                  <p className="text-muted-foreground">n/a</p>
                )}
              </div>
              <div className="rounded border p-3">
                <p className="font-medium">Missing actual ROI, highest potential</p>
                {inventory.roi_insights.missing_actual_roi_high_potential[0] ? (
                  <p className="text-muted-foreground">
                    {inventory.roi_insights.missing_actual_roi_high_potential[0].idea_id} (
                    est ROI {inventory.roi_insights.missing_actual_roi_high_potential[0].estimated_roi.toFixed(2)})
                  </p>
                ) : (
                  <p className="text-muted-foreground">n/a</p>
                )}
              </div>
            </div>
          </section>

          <section className="rounded border p-4 space-y-3">
            <h2 className="font-semibold">Web UI Standing Questions</h2>
            <p className="text-sm text-muted-foreground">
              Keep the UI measurable and improvable. These are the standing web UI questions.
            </p>
            {uiOpenQuestions.length === 0 && (
              <p className="text-sm text-muted-foreground">
                No open web UI questions. Answered items are tracked below.
              </p>
            )}
            <ul className="space-y-3">
              {uiOpenQuestions.map((q) => {
                const key = `${q.idea_id}::${q.question}`;
                const roi = q.estimated_cost > 0 ? q.value_to_whole / q.estimated_cost : 0;
                return (
                  <li key={key} className="rounded border p-3 space-y-2">
                    <p className="font-medium">{q.question}</p>
                    <p className="text-sm text-muted-foreground">
                      idea: {q.idea_id} | value: {q.value_to_whole} | cost: {q.estimated_cost} | ROI:{" "}
                      {roi.toFixed(2)}
                    </p>
                    <div className="flex flex-col md:flex-row gap-2">
                      <Input
                        placeholder="Answer"
                        value={draftAnswers[key] || ""}
                        onChange={(e) => setDraftAnswers((prev) => ({ ...prev, [key]: e.target.value }))}
                      />
                      <Input
                        placeholder="Measured delta (optional)"
                        value={draftDeltas[key] || ""}
                        onChange={(e) => setDraftDeltas((prev) => ({ ...prev, [key]: e.target.value }))}
                      />
                      <Button
                        disabled={submittingKey === key || !(draftAnswers[key] || "").trim()}
                        onClick={() => void submitAnswer(q)}
                      >
                        {submittingKey === key ? "Saving…" : "Answer"}
                      </Button>
                    </div>
                  </li>
                );
              })}
            </ul>
            {uiAnsweredQuestions.length > 0 && (
              <ul className="space-y-2 text-sm">
                {uiAnsweredQuestions.slice(0, 5).map((q) => (
                  <li key={`${q.idea_id}::answered::${q.question}`} className="rounded border p-2">
                    <p className="font-medium">{q.question}</p>
                    <p className="text-muted-foreground">
                      answer ROI: {(q.answer_roi || 0).toFixed(2)} | measured delta:{" "}
                      {q.measured_delta === null ? "n/a" : q.measured_delta}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="rounded border p-4 space-y-3">
            <h2 className="font-semibold">UI Element Value/Cost Signals</h2>
            <p className="text-sm text-muted-foreground">
              Actual value is estimated from successful interaction volume in runtime telemetry.
            </p>
            {!uiElementInsights.highestValueLeastCost || !uiElementInsights.highestCostLeastValue ? (
              <p className="text-sm text-muted-foreground">
                Not enough UI runtime events yet to rank UI elements.
              </p>
            ) : (
              <div className="grid md:grid-cols-2 gap-3 text-sm">
                <div className="rounded border p-3">
                  <p className="font-medium">Highest actual value, least cost</p>
                  <p className="text-muted-foreground">{uiElementInsights.highestValueLeastCost.endpoint}</p>
                  <p>
                    value/cost {uiElementInsights.highestValueLeastCost.value_per_cost.toFixed(2)} | events{" "}
                    {uiElementInsights.highestValueLeastCost.event_count}
                  </p>
                </div>
                <div className="rounded border p-3">
                  <p className="font-medium">Highest cost, least value</p>
                  <p className="text-muted-foreground">{uiElementInsights.highestCostLeastValue.endpoint}</p>
                  <p>
                    cost/value {uiElementInsights.highestCostLeastValue.cost_per_value.toFixed(6)} | events{" "}
                    {uiElementInsights.highestCostLeastValue.event_count}
                  </p>
                </div>
              </div>
            )}
          </section>

          <section className="rounded border p-4 space-y-3">
            <h2 className="font-semibold">Top Unanswered Questions (ROI-ordered)</h2>
            {inventory.questions.unanswered.length === 0 && (
              <p className="text-sm text-muted-foreground">No open questions. Add new high-value questions.</p>
            )}
            <ul className="space-y-3">
              {inventory.questions.unanswered.map((q) => {
                const key = `${q.idea_id}::${q.question}`;
                const roi = q.estimated_cost > 0 ? q.value_to_whole / q.estimated_cost : 0;
                return (
                  <li key={key} className="rounded border p-3 space-y-2">
                    <p className="font-medium">{q.question}</p>
                    <p className="text-sm text-muted-foreground">
                      idea: {q.idea_id} | value: {q.value_to_whole} | cost: {q.estimated_cost} | ROI:{" "}
                      {roi.toFixed(2)}
                    </p>
                    <div className="flex flex-col md:flex-row gap-2">
                      <Input
                        placeholder="Answer"
                        value={draftAnswers[key] || ""}
                        onChange={(e) => setDraftAnswers((prev) => ({ ...prev, [key]: e.target.value }))}
                      />
                      <Input
                        placeholder="Measured delta (optional)"
                        value={draftDeltas[key] || ""}
                        onChange={(e) => setDraftDeltas((prev) => ({ ...prev, [key]: e.target.value }))}
                      />
                      <Button
                        disabled={submittingKey === key || !(draftAnswers[key] || "").trim()}
                        onClick={() => void submitAnswer(q)}
                      >
                        {submittingKey === key ? "Saving…" : "Answer"}
                      </Button>
                    </div>
                  </li>
                );
              })}
            </ul>
          </section>

          <section className="rounded border p-4 space-y-2">
            <h2 className="font-semibold">Runtime Cost by Idea (24h)</h2>
            <ul className="space-y-2 text-sm">
              {topRuntime.map((row) => (
                <li key={row.idea_id} className="flex justify-between rounded border p-2">
                  <span>{row.idea_id}</span>
                  <span className="text-muted-foreground">
                    events {row.event_count} | runtime {row.total_runtime_ms.toFixed(2)}ms | cost $
                    {row.runtime_cost_estimate.toFixed(6)}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
    </main>
  );
}
