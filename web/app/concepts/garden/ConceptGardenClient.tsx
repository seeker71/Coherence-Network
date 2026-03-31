"use client";

import { useState, useMemo } from "react";
import Link from "next/link";

type GardenCard = {
  id: string;
  name: string;
  description: string;
  level: number;
  domains: string[];
  keywords: string[];
  userDefined: boolean;
  contributor?: string;
};

type SuggestResponse = {
  suggested_id: string;
  name: string;
  keywords: string[];
  domains: string[];
  related_concepts: Array<{
    id: string;
    name: string;
    score: number;
    relationship_hint: string;
  }>;
  suggested_relationships: string[];
  ready_to_submit: {
    id: string;
    name: string;
    description: string;
    type_id: string;
    level: number;
    keywords: string[];
    domains: string[];
    parent_concepts: string[];
    child_concepts: string[];
    axes: string[];
    contributor: string;
  };
  message: string;
};

type SubmitResponse = {
  concept: GardenCard;
  edges_created: unknown[];
  message: string;
};

type Props = {
  initialCards: GardenCard[];
  domainGroups: Record<string, string[]>;
  total: number;
  hint: string;
};

const LEVEL_COLORS: Record<number, string> = {
  0: "border-violet-200 bg-violet-50",
  1: "border-blue-200 bg-blue-50",
  2: "border-teal-200 bg-teal-50",
  3: "border-green-200 bg-green-50",
};
const LEVEL_LABELS: Record<number, string> = {
  0: "Core",
  1: "Primary",
  2: "Secondary",
  3: "Community",
};

function ConceptCard({ card }: { card: GardenCard }) {
  const colors = LEVEL_COLORS[card.level] ?? "border-gray-200 bg-gray-50";
  const label = LEVEL_LABELS[card.level] ?? `L${card.level}`;
  return (
    <Link
      href={`/concepts/${card.id}`}
      className={`group rounded-xl border-2 ${colors} p-4 flex flex-col gap-2 hover:shadow-md transition-all`}
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-semibold text-sm group-hover:text-primary transition-colors leading-snug">
          {card.name}
        </h3>
        <span className="text-[10px] font-medium text-muted-foreground shrink-0 mt-0.5">
          {label}
        </span>
      </div>
      {card.description && (
        <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
          {card.description}
        </p>
      )}
      <div className="flex flex-wrap gap-1 mt-auto">
        {card.domains.slice(0, 3).map((d) => (
          <span
            key={d}
            className="text-[10px] bg-white/70 border px-1.5 py-0.5 rounded-full text-muted-foreground"
          >
            {d}
          </span>
        ))}
        {card.keywords.slice(0, 2).map((kw) => (
          <span key={kw} className="text-[10px] text-muted-foreground/60">
            #{kw}
          </span>
        ))}
      </div>
      {card.userDefined && (
        <div className="text-[10px] text-amber-600 font-medium">
          {card.contributor ? `by ${card.contributor}` : "community contribution"}
        </div>
      )}
    </Link>
  );
}

export default function ConceptGardenClient({
  initialCards,
  domainGroups,
  total,
  hint,
}: Props) {
  // --- filter state ---
  const [search, setSearch] = useState("");
  const [activeDomain, setActiveDomain] = useState<string | null>(null);
  const [showContributed, setShowContributed] = useState(false);

  // --- submission form state ---
  const [plainText, setPlainText] = useState("");
  const [domainsText, setDomainsText] = useState("");
  const [contributor, setContributor] = useState("");
  const [suggestion, setSuggestion] = useState<SuggestResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [suggesting, setSuggesting] = useState(false);
  const [submitted, setSubmitted] = useState<SubmitResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cards, setCards] = useState<GardenCard[]>(initialCards);

  const domains = useMemo(
    () => Object.keys(domainGroups).sort(),
    [domainGroups]
  );

  const filtered = useMemo(() => {
    let result = cards;
    if (showContributed) result = result.filter((c) => c.userDefined);
    if (activeDomain)
      result = result.filter((c) => c.domains.includes(activeDomain));
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (c) =>
          c.name.toLowerCase().includes(q) ||
          c.description.toLowerCase().includes(q) ||
          c.keywords.some((k) => k.includes(q))
      );
    }
    return result;
  }, [cards, search, activeDomain, showContributed]);

  async function handleSuggest() {
    if (!plainText.trim()) return;
    setSuggesting(true);
    setError(null);
    setSuggestion(null);
    try {
      const res = await fetch("/api/concepts/suggest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          plain_text: plainText.trim(),
          domains: domainsText
            .split(",")
            .map((d) => d.trim())
            .filter(Boolean),
          contributor: contributor.trim() || "anonymous",
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? "Suggestion failed");
      }
      setSuggestion(await res.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setSuggesting(false);
    }
  }

  async function handleSubmit() {
    if (!suggestion) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch("/api/concepts/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(suggestion.ready_to_submit),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? "Submit failed");
      }
      const result: SubmitResponse = await res.json();
      setSubmitted(result);
      // Add to local card list immediately
      setCards((prev) => [result.concept, ...prev]);
      setPlainText("");
      setDomainsText("");
      setSuggestion(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-8">
      {/* Submission form */}
      <div className="rounded-2xl border-2 border-dashed border-primary/30 bg-primary/5 p-6">
        <h2 className="text-base font-semibold mb-1">Share an idea</h2>
        <p className="text-xs text-muted-foreground mb-4">
          {hint ||
            "Describe a concept in your own words. The system finds where it fits."}
        </p>

        <div className="space-y-3">
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1 block">
              Your idea (plain language)
            </label>
            <textarea
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary/30"
              rows={2}
              placeholder="e.g. the way rivers remember their paths through stone"
              value={plainText}
              onChange={(e) => setPlainText(e.target.value)}
              disabled={submitting}
            />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">
                Domains you know (comma-separated, optional)
              </label>
              <input
                type="text"
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                placeholder="ecology, memory, geology"
                value={domainsText}
                onChange={(e) => setDomainsText(e.target.value)}
                disabled={submitting}
              />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">
                Your name or handle (optional)
              </label>
              <input
                type="text"
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                placeholder="anonymous"
                value={contributor}
                onChange={(e) => setContributor(e.target.value)}
                disabled={submitting}
              />
            </div>
          </div>

          <button
            onClick={handleSuggest}
            disabled={!plainText.trim() || suggesting || submitting}
            className="rounded-lg bg-primary text-primary-foreground px-4 py-2 text-sm font-medium disabled:opacity-50 hover:opacity-90 transition-opacity"
          >
            {suggesting ? "Finding where it fits..." : "Find placement"}
          </button>
        </div>

        {/* Error */}
        {error && (
          <div className="mt-3 text-xs text-destructive bg-destructive/10 rounded-lg px-3 py-2">
            {error}
          </div>
        )}

        {/* Success */}
        {submitted && (
          <div className="mt-3 text-xs text-green-700 bg-green-50 border border-green-200 rounded-lg px-3 py-2">
            <strong>Added!</strong> &quot;{submitted.concept.name}&quot; is now
            part of the ontology.{" "}
            {submitted.edges_created.length > 0 &&
              `${submitted.edges_created.length} connection(s) created automatically.`}
          </div>
        )}

        {/* Suggestion panel */}
        {suggestion && !submitted && (
          <div className="mt-4 rounded-xl border bg-background p-4 space-y-3">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-0.5">
                  Suggested placement
                </p>
                <p className="text-sm font-semibold">{suggestion.name}</p>
                <p className="text-xs text-muted-foreground font-mono">
                  {suggestion.suggested_id}
                </p>
              </div>
              <span className="text-[10px] bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">
                Ready to add
              </span>
            </div>

            {suggestion.keywords.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {suggestion.keywords.map((kw) => (
                  <span
                    key={kw}
                    className="text-[10px] bg-muted px-1.5 py-0.5 rounded text-muted-foreground"
                  >
                    #{kw}
                  </span>
                ))}
              </div>
            )}

            {suggestion.related_concepts.length > 0 && (
              <div>
                <p className="text-[11px] font-medium text-muted-foreground mb-1.5">
                  Related concepts found:
                </p>
                <div className="space-y-1">
                  {suggestion.related_concepts.map((rel) => (
                    <div
                      key={rel.id}
                      className="flex items-center gap-2 text-xs"
                    >
                      <span className="text-muted-foreground/60">
                        {rel.relationship_hint}
                      </span>
                      <span className="font-medium">{rel.name}</span>
                      <span className="text-muted-foreground/40 ml-auto tabular-nums">
                        {Math.round(rel.score * 100)}% match
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <p className="text-xs text-muted-foreground">{suggestion.message}</p>

            <div className="flex gap-2">
              <button
                onClick={handleSubmit}
                disabled={submitting}
                className="rounded-lg bg-primary text-primary-foreground px-4 py-2 text-sm font-medium disabled:opacity-50 hover:opacity-90 transition-opacity"
              >
                {submitting ? "Adding..." : "Add to ontology"}
              </button>
              <button
                onClick={() => setSuggestion(null)}
                className="rounded-lg border px-4 py-2 text-sm text-muted-foreground hover:bg-muted transition-colors"
              >
                Revise
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="text"
          placeholder="Search concepts..."
          className="rounded-lg border bg-background px-3 py-1.5 text-sm w-48 focus:outline-none focus:ring-2 focus:ring-primary/30"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <button
          onClick={() => setShowContributed((v) => !v)}
          className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
            showContributed
              ? "bg-amber-100 border-amber-300 text-amber-700"
              : "hover:bg-muted text-muted-foreground"
          }`}
        >
          Community only
        </button>
        <div className="flex flex-wrap gap-1.5 ml-1">
          {domains.map((d) => (
            <button
              key={d}
              onClick={() => setActiveDomain(activeDomain === d ? null : d)}
              className={`rounded-full border px-2.5 py-0.5 text-[11px] font-medium transition-colors ${
                activeDomain === d
                  ? "bg-primary text-primary-foreground border-primary"
                  : "hover:bg-muted text-muted-foreground"
              }`}
            >
              {d}
            </button>
          ))}
        </div>
        <span className="text-xs text-muted-foreground ml-auto">
          {filtered.length} of {total}
        </span>
      </div>

      {/* Cards grid */}
      {filtered.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground">
          <p className="text-sm">No concepts match your filter.</p>
          <p className="text-xs mt-1">Try sharing your idea above.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filtered.map((card) => (
            <ConceptCard key={card.id} card={card} />
          ))}
        </div>
      )}
    </div>
  );
}
