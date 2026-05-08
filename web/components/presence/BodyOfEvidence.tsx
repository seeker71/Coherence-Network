"use client";

/**
 * BodyOfEvidence — the unified surface of every contribution and
 * influence flowing through a presence, from any source.
 *
 * Three sections, all reading from the same edge fetch:
 *
 *   1. Emits into the field — outgoing `contributes-to` edges, the
 *      works this presence has put into the world. Each weighted
 *      by its own creation_hours / view_count when available.
 *
 *   2. Shaped by — outgoing `inspired-by` edges, the influences that
 *      shaped this presence. Grouped by source (Audible, YouTube,
 *      physical reading, named lineage, manual) so the visitor can
 *      read which stream of attention each tie comes from. Within
 *      each source, sorted by strength.
 *
 *   3. Field connections — every other relational edge (resonates-with,
 *      at-place, analogous-to, etc.) grouped by the seven canonical
 *      edge-type families. The spectrum-colored view from the earlier
 *      InfluenceWeb is preserved here as the third lens.
 *
 *   4. Inbound recognition — incoming `inspired-by` edges, the
 *      contributors who claim this presence as one of theirs.
 *
 * Sections collapse independently. Each chip carries the spectrum
 * color of its relationship family; the strength bar carries the
 * weight (cumulative hours, watch count, view count, depending on
 * source).
 */

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { getApiBase } from "@/lib/api";
import { brandFor } from "./brand";
import { SpectrumLink } from "./SpectrumLink";
import {
  EDGE_FAMILIES,
  edgeTypeLabel,
  EDGE_TYPE_TO_FAMILY,
  familyForEdgeType,
  hsl,
  type EdgeFamily,
  type EdgeFamilySlug,
} from "@/lib/edge-spectrum";

type EdgeRow = {
  id: string;
  from_id: string;
  to_id: string;
  type: string;
  strength?: number | null;
  properties?: Record<string, unknown> | null;
  from_node?: NodeStub;
  to_node?: NodeStub;
};

type NodeStub = {
  id: string;
  name: string;
  type: string;
  image_url?: string | null;
  slug?: string | null;
};

type ExternalPresence = { provider: string; url: string };

type Props = {
  presenceId: string;
  externalPresences?: ExternalPresence[];
};

// Source labels — readable names for the edge-property `source` values
// the various ingest paths write. Unknown sources fall through to the
// raw label so we don't hide what the body is carrying.
const SOURCE_LABELS: Record<string, string> = {
  audible_listening_history: "Audible",
  youtube_watch_history_cluster: "YouTube",
  physical_book_reading: "Physical reading",
  lineage_seed: "Named lineage",
  lineage_seed_cleanup: "Named lineage",
  inspired_by_resolver: "Manual",
  watch_history_clusterer: "YouTube",
  thesis_seed: "Authored work",
};

const SOURCE_ORDER = [
  "Authored work",
  "Audible",
  "YouTube",
  "Physical reading",
  "Named lineage",
  "Manual",
];

function sourceLabelFor(props: Record<string, unknown> | null | undefined): string {
  const raw = props?.source;
  if (typeof raw !== "string" || !raw) return "Other";
  return SOURCE_LABELS[raw] ?? raw;
}

// ── System tissue (visitors, runners, fixtures) — never render ───────

const SYSTEM_PATTERNS = [
  ":wanderer-", ":presence-visitor", ":test-", ":smoke-", "-smoke-", "-bot",
  ":external-proof", "decomposition-verify", ":friend-", "-placeholder",
  ":claude-opus-mac-node", ":coherence-runner", ":e-m-t-", ":email-",
  ":qa-", ":ci-",
];
const SYSTEM_EXACT = new Set([
  "contributor:claude", "contributor:codex", "contributor:codex-agent",
  "contributor:cursor-agent", "contributor:grok", "contributor:gemini",
  "person:codex-smoke-human", "contributor:presence-visitor",
  "person:presence-visitor",
]);

function isSystem(id: string): boolean {
  if (SYSTEM_EXACT.has(id)) return true;
  return SYSTEM_PATTERNS.some((p) => id.includes(p));
}

// ── Component ─────────────────────────────────────────────────────────

export function BodyOfEvidence({ presenceId, externalPresences = [] }: Props) {
  const [edges, setEdges] = useState<EdgeRow[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!presenceId) return;
    (async () => {
      try {
        const r = await fetch(
          `${getApiBase()}/api/graph/nodes/${encodeURIComponent(
            presenceId,
          )}/edges?direction=both`,
        );
        if (r.ok) {
          const body = await r.json();
          setEdges(Array.isArray(body) ? body : body?.items ?? []);
        }
      } catch {
        // empty body — the rest of the page still renders
      } finally {
        setLoaded(true);
      }
    })();
  }, [presenceId]);

  const sections = useMemo(() => composeSections(edges, presenceId), [edges, presenceId]);

  if (!loaded) {
    return (
      <section className="space-y-3">
        <h2 className="text-xs uppercase tracking-[0.18em] font-semibold text-muted-foreground">
          Body of evidence
        </h2>
        <div className="h-12 animate-pulse rounded-lg bg-muted/40" />
      </section>
    );
  }

  const totalEdges =
    sections.emissions.length +
    sections.shapedBy.length +
    sections.fieldConnections.length +
    sections.recognition.length;

  if (totalEdges === 0 && externalPresences.length === 0) {
    return (
      <section className="space-y-3">
        <h2 className="text-xs uppercase tracking-[0.18em] font-semibold text-muted-foreground">
          Body of evidence
        </h2>
        <p className="text-sm text-muted-foreground/80 italic">
          The web around this presence is just beginning to weave. Add
          relationships, public presences, or works to surface the threads.
        </p>
      </section>
    );
  }

  return (
    <section className="space-y-8">
      <header className="space-y-1">
        <h2 className="text-xs uppercase tracking-[0.18em] font-semibold text-[hsl(var(--primary))]">
          Body of evidence
        </h2>
        <p className="text-xs text-muted-foreground/80">
          {totalEdges} threads woven through this presence
          {externalPresences.length > 0 && ` · ${externalPresences.length} doorways beyond the network`}
        </p>
      </header>

      {sections.emissions.length > 0 && (
        <Emissions items={sections.emissions} />
      )}

      {sections.shapedBy.length > 0 && (
        <ShapedBy items={sections.shapedBy} />
      )}

      {sections.fieldConnections.length > 0 && (
        <FieldConnections items={sections.fieldConnections} />
      )}

      {sections.recognition.length > 0 && (
        <Recognition items={sections.recognition} />
      )}

      {externalPresences.length > 0 && (
        <BeyondTheNetwork presences={externalPresences} />
      )}
    </section>
  );
}

// ── Section 1: Emissions ──────────────────────────────────────────────

type EmissionRow = {
  id: string;
  name: string;
  href: string;
  imageUrl?: string | null;
  strength: number;
  kind: string;
  hours: number | null;
};

function Emissions({ items }: { items: EmissionRow[] }) {
  const [showAll, setShowAll] = useState(false);
  const visible = showAll ? items : items.slice(0, 8);
  return (
    <SectionShell
      title="Emits into the field"
      hint={`${items.length} ${items.length === 1 ? "creation" : "creations"} this presence has put into the world`}
      familyHue={40} // attribution-gold
    >
      <ul className="space-y-1.5">
        {visible.map((it) => (
          <RowChip
            key={it.id}
            href={it.href}
            name={it.name}
            imageUrl={it.imageUrl}
            strength={it.strength}
            tag={it.kind}
            metric={it.hours ? `${it.hours.toFixed(0)}h created` : null}
            hue={40}
          />
        ))}
      </ul>
      {items.length > 8 && (
        <ShowAllToggle
          showAll={showAll}
          total={items.length}
          onClick={() => setShowAll((v) => !v)}
        />
      )}
    </SectionShell>
  );
}

// ── Section 2: Shaped By (influences) ─────────────────────────────────

type ShapedRow = {
  id: string;
  name: string;
  href: string;
  imageUrl?: string | null;
  strength: number;
  source: string;
  metric: string | null;
};

function ShapedBy({ items }: { items: ShapedRow[] }) {
  // Group by source, sort each group by strength desc
  const grouped = useMemo(() => {
    const map: Record<string, ShapedRow[]> = {};
    for (const it of items) {
      (map[it.source] ||= []).push(it);
    }
    for (const src of Object.keys(map)) {
      map[src].sort((a, b) => b.strength - a.strength);
    }
    return map;
  }, [items]);

  const orderedSources = [
    ...SOURCE_ORDER.filter((s) => grouped[s]?.length),
    ...Object.keys(grouped).filter((s) => !SOURCE_ORDER.includes(s)),
  ];

  return (
    <SectionShell
      title="Shaped by"
      hint={`${items.length} influences across ${orderedSources.length} ${orderedSources.length === 1 ? "stream" : "streams"} of attention`}
      familyHue={270} // ontological violet
    >
      <div className="space-y-5">
        {orderedSources.map((src) => (
          <SourceGroup key={src} source={src} rows={grouped[src]} />
        ))}
      </div>
    </SectionShell>
  );
}

function SourceGroup({ source, rows }: { source: string; rows: ShapedRow[] }) {
  const [showAll, setShowAll] = useState(false);
  const visible = showAll ? rows : rows.slice(0, 8);
  const totalHours = rows.reduce((sum, r) => {
    const m = r.metric?.match(/^([\d.]+)h/);
    return m ? sum + parseFloat(m[1]) : sum;
  }, 0);
  return (
    <div className="space-y-2">
      <div className="flex items-baseline gap-2">
        <h4 className="text-[10px] uppercase tracking-[0.15em] font-semibold text-muted-foreground">
          {source}
        </h4>
        <span className="text-[10px] text-muted-foreground/60">
          · {rows.length}
          {totalHours > 0 ? ` · ${Math.round(totalHours)}h` : ""}
        </span>
      </div>
      <ul className="space-y-1.5">
        {visible.map((it) => (
          <RowChip
            key={it.id}
            href={it.href}
            name={it.name}
            imageUrl={it.imageUrl}
            strength={it.strength}
            metric={it.metric}
            hue={270}
          />
        ))}
      </ul>
      {rows.length > 8 && (
        <ShowAllToggle
          showAll={showAll}
          total={rows.length}
          onClick={() => setShowAll((v) => !v)}
        />
      )}
    </div>
  );
}

// ── Section 3: Field Connections ──────────────────────────────────────

type FieldRow = {
  id: string;
  name: string;
  href: string;
  imageUrl?: string | null;
  strength: number;
  edgeType: string;
  family: EdgeFamilySlug;
};

function FieldConnections({ items }: { items: FieldRow[] }) {
  const grouped = useMemo(() => {
    const map: Partial<Record<EdgeFamilySlug, FieldRow[]>> = {};
    for (const it of items) {
      (map[it.family] ||= []).push(it);
    }
    return map;
  }, [items]);

  return (
    <SectionShell
      title="Field connections"
      hint="Concepts, places, kindred presences — the relational threads"
      familyHue={158}
    >
      <div className="space-y-4">
        {EDGE_FAMILIES.map((fam) => {
          const list = grouped[fam.slug];
          if (!list?.length) return null;
          return <FamilyBand key={fam.slug} family={fam} items={list} />;
        })}
      </div>
    </SectionShell>
  );
}

function FamilyBand({ family, items }: { family: EdgeFamily; items: FieldRow[] }) {
  const tone = useFamilyTone(family);
  const fg = hsl(tone, "fg");
  return (
    <div className="space-y-2">
      <div className="flex items-baseline gap-2" title={family.feeling}>
        <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: fg }} />
        <h4 className="text-[10px] uppercase tracking-[0.15em] font-semibold" style={{ color: fg }}>
          {family.name}
        </h4>
        <span className="text-[10px] text-muted-foreground/60">· {items.length}</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {items.slice(0, 30).map((it, i) => (
          <SpectrumLink
            key={`${it.id}-${i}`}
            edgeType={it.edgeType}
            href={it.href}
            name={it.name}
            imageUrl={it.imageUrl}
            strength={it.strength}
          />
        ))}
      </div>
    </div>
  );
}

// ── Section 4: Inbound Recognition ────────────────────────────────────

type RecRow = { id: string; name: string; href: string; imageUrl?: string | null; strength: number };

function Recognition({ items }: { items: RecRow[] }) {
  const [showAll, setShowAll] = useState(false);
  const visible = showAll ? items : items.slice(0, 8);
  return (
    <SectionShell
      title="Recognized by"
      hint={`${items.length} ${items.length === 1 ? "presence claims" : "presences claim"} this one as part of their lineage`}
      familyHue={340}
    >
      <ul className="space-y-1.5">
        {visible.map((it) => (
          <RowChip
            key={it.id}
            href={it.href}
            name={it.name}
            imageUrl={it.imageUrl}
            strength={it.strength}
            hue={340}
          />
        ))}
      </ul>
      {items.length > 8 && (
        <ShowAllToggle
          showAll={showAll}
          total={items.length}
          onClick={() => setShowAll((v) => !v)}
        />
      )}
    </SectionShell>
  );
}

// ── Beyond the network ────────────────────────────────────────────────

function BeyondTheNetwork({ presences }: { presences: ExternalPresence[] }) {
  return (
    <SectionShell
      title="Beyond the network"
      hint="Public URLs the world reaches them through"
      familyHue={215}
    >
      <div className="flex flex-wrap gap-2">
        {presences.map((p, i) => {
          const tone = brandFor(p.provider);
          return (
            <a
              key={`${p.provider}-${i}`}
              href={p.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs transition-all hover:scale-[1.02]"
              style={{
                background: tone.gradient || tone.bg,
                color: tone.fg,
                borderColor: `color-mix(in oklch, ${tone.fg} 30%, transparent)`,
              }}
              title={`${tone.label} · ${p.url}`}
            >
              <span className="font-medium">{tone.label}</span>
              <span className="opacity-60">↗</span>
            </a>
          );
        })}
      </div>
    </SectionShell>
  );
}

// ── Reusable shells ───────────────────────────────────────────────────

function SectionShell({
  title,
  hint,
  familyHue,
  children,
}: {
  title: string;
  hint?: string;
  familyHue: number;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3">
      <header className="space-y-0.5">
        <div className="flex items-baseline gap-2">
          <span
            className="inline-block w-2.5 h-2.5 rounded-full"
            style={{ background: `hsl(${familyHue} 70% 60%)` }}
          />
          <h3 className="text-[11px] uppercase tracking-[0.15em] font-semibold text-foreground/80">
            {title}
          </h3>
        </div>
        {hint && <p className="text-[11px] text-muted-foreground/70 ml-4">{hint}</p>}
      </header>
      <div className="ml-4">{children}</div>
    </section>
  );
}

function RowChip({
  href,
  name,
  imageUrl,
  strength,
  tag,
  metric,
  hue,
}: {
  href: string;
  name: string;
  imageUrl?: string | null;
  strength: number;
  tag?: string | null;
  metric?: string | null;
  hue: number;
}) {
  const pct = Math.round(Math.max(0.02, Math.min(1, strength)) * 100);
  return (
    <li>
      <Link
        href={href}
        className="group flex items-center gap-3 rounded-md py-1.5 px-2 hover:bg-card/60 transition-colors"
      >
        {imageUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={imageUrl}
            alt=""
            className="w-8 h-8 rounded-full object-cover shrink-0 border border-border/40"
          />
        ) : (
          <span
            className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium shrink-0 border"
            style={{
              background: `hsl(${hue} 60% 92% / 0.15)`,
              color: `hsl(${hue} 70% 70%)`,
              borderColor: `hsl(${hue} 50% 40% / 0.4)`,
            }}
          >
            {(name || "·").charAt(0).toUpperCase()}
          </span>
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-2">
            <span className="text-sm text-foreground/90 group-hover:text-foreground truncate">
              {name}
            </span>
            {tag && (
              <span className="text-[10px] uppercase tracking-[0.1em] text-muted-foreground/70 shrink-0">
                {tag}
              </span>
            )}
            {metric && (
              <span className="text-[10px] text-muted-foreground/70 ml-auto shrink-0 tabular-nums">
                {metric}
              </span>
            )}
          </div>
          <div
            className="mt-1 h-[3px] rounded-full overflow-hidden"
            style={{ background: `hsl(${hue} 60% 50% / 0.12)` }}
          >
            <div
              className="h-full rounded-full transition-all"
              style={{
                width: `${pct}%`,
                background: `hsl(${hue} 70% 60%)`,
              }}
            />
          </div>
        </div>
      </Link>
    </li>
  );
}

function ShowAllToggle({
  showAll,
  total,
  onClick,
}: {
  showAll: boolean;
  total: number;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="text-[11px] text-[hsl(var(--primary))] hover:opacity-80 mt-1 ml-2"
    >
      {showAll ? "← show fewer" : `show all ${total} →`}
    </button>
  );
}

// ── Composition ───────────────────────────────────────────────────────

function composeSections(edges: EdgeRow[], selfId: string) {
  const emissions: EmissionRow[] = [];
  const shapedBy: ShapedRow[] = [];
  const fieldConnections: FieldRow[] = [];
  const recognition: RecRow[] = [];

  for (const e of edges) {
    const isOutgoing = e.from_id === selfId;
    const other = isOutgoing ? e.to_node : e.from_node;
    if (!other || other.id === selfId) continue;
    if (isSystem(other.id)) continue;
    const strength = e.strength ?? 0;
    const props = e.properties || {};

    if (e.type === "contributes-to" && isOutgoing) {
      const hours = numberFrom(props.creation_hours) ?? null;
      emissions.push({
        id: e.id,
        name: other.name || other.id,
        href: hrefFor(other),
        imageUrl: other.image_url,
        strength,
        kind: ((props.kind as string) || "work").toLowerCase(),
        hours,
      });
    } else if (e.type === "inspired-by" && isOutgoing) {
      // Per-work inspired-by edges (audible book listens, individual
      // video watches) collapse into their author/channel chip in
      // Shaped By. The work-level traceability stays in the graph —
      // it surfaces when the visitor walks to the author's page,
      // where the books appear in Emits — but doesn't multiply the
      // rolled-up Shaped By view by 30 per author.
      if (other.type === "asset") continue;
      shapedBy.push({
        id: e.id,
        name: other.name || other.id,
        href: hrefFor(other),
        imageUrl: other.image_url,
        strength,
        source: sourceLabelFor(props),
        metric: metricFor(props),
      });
    } else if (e.type === "inspired-by" && !isOutgoing) {
      recognition.push({
        id: e.id,
        name: other.name || other.id,
        href: hrefFor(other),
        imageUrl: other.image_url,
        strength,
      });
    } else {
      fieldConnections.push({
        id: e.id,
        name: other.name || other.id,
        href: hrefFor(other),
        imageUrl: other.image_url,
        strength,
        edgeType: e.type,
        family: (EDGE_TYPE_TO_FAMILY[e.type] ?? "attribution") as EdgeFamilySlug,
      });
    }
  }

  emissions.sort((a, b) => b.strength - a.strength);
  shapedBy.sort((a, b) => b.strength - a.strength);
  fieldConnections.sort((a, b) => b.strength - a.strength);
  recognition.sort((a, b) => b.strength - a.strength);

  return { emissions, shapedBy, fieldConnections, recognition };
}

function metricFor(props: Record<string, unknown>): string | null {
  const ah = numberFrom(props.audible_hours);
  const ab = numberFrom(props.audible_books);
  if (ah != null) return ab ? `${ah.toFixed(0)}h · ${ab} books` : `${ah.toFixed(0)}h`;
  const wh = numberFrom(props.watch_hours);
  const wc = numberFrom(props.watch_count);
  if (wh != null) return wc ? `${wh.toFixed(0)}h · ${wc} watches` : `${wh.toFixed(0)}h`;
  const ph = numberFrom(props.physical_read_hours);
  if (ph != null) return `${ph.toFixed(0)}h read`;
  return null;
}

function numberFrom(v: unknown): number | null {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string") {
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

function hrefFor(other: NodeStub): string {
  if (other.type === "concept") return `/vision/${encodeURIComponent(other.id)}`;
  if (other.slug) return `/people/${other.slug}`;
  return `/people/${encodeURIComponent(other.id)}`;
}

function useFamilyTone(family: EdgeFamily) {
  const [isLight, setIsLight] = useState(false);
  useEffect(() => {
    const update = () => setIsLight(document.documentElement.classList.contains("light"));
    update();
    const mo = new MutationObserver(update);
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    return () => mo.disconnect();
  }, []);
  return isLight ? family.light : family.dark;
}
