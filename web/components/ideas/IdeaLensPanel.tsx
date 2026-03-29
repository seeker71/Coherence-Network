"use client";

import { useCallback, useEffect, useState } from "react";

import { getApiBase } from "@/lib/api";

type LensRow = { lens_id: string; name: string; description: string };

type Translation = {
  lens_id: string;
  translated_summary: string;
  emphasis: string[];
  risk_framing: string;
  opportunity_framing: string;
  resonance_delta?: number | null;
};

export default function IdeaLensPanel({
  ideaId,
  defaultLens = "libertarian",
}: {
  ideaId: string;
  defaultLens?: string;
}) {
  const [lenses, setLenses] = useState<LensRow[]>([]);
  const [lensId, setLensId] = useState(defaultLens);
  const [translation, setTranslation] = useState<Translation | null>(null);
  const [txLoading, setTxLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const api = getApiBase();

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(`${api}/api/lenses`, { cache: "no-store" });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data = await r.json();
        const rows: LensRow[] = (data.lenses ?? []).map(
          (x: { lens_id: string; name: string; description: string }) => ({
            lens_id: x.lens_id,
            name: x.name,
            description: x.description,
          }),
        );
        if (!cancelled) {
          setLenses(rows);
          if (rows.length && !rows.some((l) => l.lens_id === defaultLens)) {
            setLensId(rows[0].lens_id);
          }
        }
      } catch (e) {
        if (!cancelled) setErr(String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [api, defaultLens]);

  const loadTranslation = useCallback(async () => {
    setErr(null);
    setTxLoading(true);
    try {
      const r = await fetch(
        `${api}/api/ideas/${encodeURIComponent(ideaId)}/translations/${encodeURIComponent(lensId)}`,
        { cache: "no-store" },
      );
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const t = await r.json();
      setTranslation(t);
    } catch (e) {
      setErr(String(e));
      setTranslation(null);
    } finally {
      setTxLoading(false);
    }
  }, [api, ideaId, lensId]);

  useEffect(() => {
    if (!lensId) return;
    void loadTranslation();
  }, [lensId, loadTranslation]);

  return (
    <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-4 text-sm">
      <div>
        <h2 className="text-xl font-semibold">See this idea through a worldview</h2>
        <p className="text-muted-foreground mt-1">
          Same idea, different emphasis — not a rewrite of facts, but a bridge across perspectives.
        </p>
      </div>
      <div className="flex flex-wrap gap-2 items-center">
        <label htmlFor={`lens-select-${ideaId}`} className="text-muted-foreground">
          Lens
        </label>
        <select
          id={`lens-select-${ideaId}`}
          className="rounded-md border border-border bg-background px-3 py-2 text-foreground min-w-[200px]"
          value={lensId}
          onChange={(e) => setLensId(e.target.value)}
        >
          {lenses.map((l) => (
            <option key={l.lens_id} value={l.lens_id}>
              {l.name}
            </option>
          ))}
        </select>
        <button
          type="button"
          className="rounded-md border border-border px-3 py-2 hover:bg-muted/60"
          onClick={() => void loadTranslation()}
        >
          Refresh
        </button>
      </div>
      {txLoading && <p className="text-muted-foreground">Loading translation…</p>}
      {err && <p className="text-destructive text-sm">{err}</p>}
      {translation && !txLoading && (
        <div className="space-y-3 text-foreground">
          <p className="leading-relaxed">{translation.translated_summary}</p>
          {translation.emphasis?.length ? (
            <div>
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Emphasis</p>
              <p className="text-sm">{translation.emphasis.join(", ")}</p>
            </div>
          ) : null}
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-xl border border-border/40 bg-background/50 p-3">
              <p className="text-xs font-medium text-muted-foreground mb-1">Risk framing</p>
              <p className="text-sm">{translation.risk_framing}</p>
            </div>
            <div className="rounded-xl border border-border/40 bg-background/50 p-3">
              <p className="text-xs font-medium text-muted-foreground mb-1">Opportunity framing</p>
              <p className="text-sm">{translation.opportunity_framing}</p>
            </div>
          </div>
          {translation.resonance_delta != null && (
            <p className="text-xs text-muted-foreground">
              Resonance delta (belief alignment hint): {translation.resonance_delta.toFixed(3)}
            </p>
          )}
        </div>
      )}
    </section>
  );
}
