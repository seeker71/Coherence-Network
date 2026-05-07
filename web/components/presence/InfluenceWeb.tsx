"use client";

/**
 * InfluenceWeb — every related influence around a presence, inside
 * and outside the network, rendered with the spectrum color of each
 * connection's family.
 *
 * Inside the network: every graph edge from this node, grouped by
 * the seven canonical edge families (Being, Transformation, Structure,
 * Scale, Time, Tension, Attribution). Each chip walks to the related
 * presence, painted in the family's color so the visitor reads the
 * frequency at a glance.
 *
 * Outside the network: every external presence URL the node carries
 * — YouTube, Instagram, podcasts, the canonical website — colored by
 * the platform brand. These are doorways out of the network into the
 * public-facing voice this presence already broadcasts.
 *
 * The visitor should be able to feel the shape of a presence by the
 * spread of color and density of chips alone.
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
  from_node?: { id: string; name: string; type: string; image_url?: string | null; slug?: string | null };
  to_node?: { id: string; name: string; type: string; image_url?: string | null; slug?: string | null };
};

type ExternalPresence = {
  provider: string;
  url: string;
};

type Props = {
  /** Graph node id of the presence whose web we're rendering. */
  presenceId: string;
  /** External presence links (presences[] on the graph node). */
  externalPresences?: ExternalPresence[];
};

type GroupedRelative = {
  edgeType: string;
  href: string;
  name: string;
  imageUrl?: string | null;
  strength?: number | null;
};

export function InfluenceWeb({ presenceId, externalPresences = [] }: Props) {
  const [edges, setEdges] = useState<EdgeRow[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!presenceId) return;
    const apiBase = getApiBase();
    (async () => {
      try {
        const r = await fetch(
          `${apiBase}/api/graph/nodes/${encodeURIComponent(
            presenceId,
          )}/edges?direction=both`,
        );
        if (r.ok) {
          const body = await r.json();
          const items: EdgeRow[] = Array.isArray(body)
            ? body
            : body?.items ?? [];
          setEdges(items);
        }
      } catch {
        // network failure → empty web; the rest of the page still renders
      } finally {
        setLoaded(true);
      }
    })();
  }, [presenceId]);

  // Group edges by family, preserving direction so "X resonates with
  // Y" and "Y resonates with X" both surface the OTHER node from
  // this presence's point of view.
  const grouped = useMemo(
    () => groupByFamily(edges, presenceId),
    [edges, presenceId],
  );

  const totalRelatives = Object.values(grouped).reduce(
    (sum, list) => sum + list.length,
    0,
  );

  // Empty state: a presence newly woven into the field. Surface the
  // doorway so the visitor knows the web isn't broken — it's young.
  if (loaded && totalRelatives === 0 && externalPresences.length === 0) {
    return (
      <section className="space-y-3">
        <h2 className="text-xs uppercase tracking-[0.18em] font-semibold text-muted-foreground">
          Influences and connections
        </h2>
        <p className="text-sm text-muted-foreground/80 italic">
          The web around this presence is just beginning to weave. Add a
          relationship or a public presence link to surface the threads.
        </p>
      </section>
    );
  }

  if (!loaded) {
    return (
      <section className="space-y-3">
        <h2 className="text-xs uppercase tracking-[0.18em] font-semibold text-muted-foreground">
          Influences and connections
        </h2>
        <div className="h-12 animate-pulse rounded-lg bg-muted/40" />
      </section>
    );
  }

  return (
    <section className="space-y-6">
      <header className="space-y-1">
        <h2 className="text-xs uppercase tracking-[0.18em] font-semibold text-[hsl(var(--primary))]">
          Influences and connections
        </h2>
        <p className="text-xs text-muted-foreground/80">
          {totalRelatives} relationship{totalRelatives === 1 ? "" : "s"}{" "}
          inside the field
          {externalPresences.length > 0 && (
            <>
              {" · "}
              {externalPresences.length} presence
              {externalPresences.length === 1 ? "" : "s"} beyond it
            </>
          )}
        </p>
      </header>

      {/* Inside the network — grouped by family, colored by spectrum */}
      {EDGE_FAMILIES.map((family) => {
        const list = grouped[family.slug] || [];
        if (list.length === 0) return null;
        return (
          <FamilySection key={family.slug} family={family} relatives={list} />
        );
      })}

      {/* Outside the network — public presences across platforms */}
      {externalPresences.length > 0 && (
        <ExternalPresenceRow presences={externalPresences} />
      )}
    </section>
  );
}

function FamilySection({
  family,
  relatives,
}: {
  family: EdgeFamily;
  relatives: GroupedRelative[];
}) {
  const [tone, setTone] = useState(family.dark);
  useEffect(() => {
    const update = () =>
      setTone(
        document.documentElement.classList.contains("light")
          ? family.light
          : family.dark,
      );
    update();
    const mo = new MutationObserver(update);
    mo.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    });
    return () => mo.disconnect();
  }, [family]);
  const fg = hsl(tone, "fg");

  return (
    <div className="space-y-2">
      <div className="flex items-baseline gap-2" title={family.feeling}>
        <span
          aria-hidden="true"
          className="inline-block w-2.5 h-2.5 rounded-full"
          style={{ background: fg }}
        />
        <h3
          className="text-[11px] uppercase tracking-[0.15em] font-semibold"
          style={{ color: fg }}
        >
          {family.name}
        </h3>
        <span className="text-[10px] text-muted-foreground/60">
          · {relatives.length}
        </span>
      </div>
      <div className="flex flex-wrap gap-2">
        {relatives.map((r, i) => (
          <SpectrumLink
            key={`${r.edgeType}-${r.href}-${i}`}
            edgeType={r.edgeType}
            href={r.href}
            name={r.name}
            imageUrl={r.imageUrl}
            strength={r.strength}
          />
        ))}
      </div>
    </div>
  );
}

function ExternalPresenceRow({ presences }: { presences: ExternalPresence[] }) {
  return (
    <div className="space-y-2 pt-2 border-t border-border/30">
      <h3 className="text-[11px] uppercase tracking-[0.15em] font-semibold text-muted-foreground">
        Beyond the network
      </h3>
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
                background: tone.bg,
                color: tone.fg,
                borderColor: `color-mix(in oklch, ${tone.fg} 30%, transparent)`,
                ...(tone.gradient ? { background: tone.gradient } : {}),
              }}
              title={`${tone.label} · ${p.url}`}
            >
              <span className="font-medium">{tone.label}</span>
              <span className="opacity-60">↗</span>
            </a>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Patterns in graph node ids that mark system tissue — runners, test
 * fixtures, visitors, agent identities. These never render as
 * relationship chips on a public presence page.
 *
 * Mirrors the filter rules used by the /people directory in
 * `web/content/presence-walk/en.json`. The list lives in two places
 * for now; consolidating into a shared lib is future-breath work.
 */
const SYSTEM_ID_PATTERNS = [
  ":wanderer-",
  ":presence-visitor",
  ":test-",
  ":smoke-",
  "-smoke-",
  "-bot",
  ":external-proof",
  "decomposition-verify",
  ":friend-",
  "-placeholder",
  ":claude-opus-mac-node",
  ":coherence-runner",
  ":e-m-t-",
  ":email-",
  ":qa-",
  ":ci-",
];
const SYSTEM_EXACT_IDS = new Set([
  "contributor:claude",
  "contributor:codex",
  "contributor:codex-agent",
  "contributor:cursor-agent",
  "contributor:grok",
  "contributor:gemini",
  "person:codex-smoke-human",
  "contributor:presence-visitor",
  "person:presence-visitor",
]);

function isSystemNode(id: string | undefined | null): boolean {
  if (!id) return false;
  if (SYSTEM_EXACT_IDS.has(id)) return true;
  return SYSTEM_ID_PATTERNS.some((p) => id.includes(p));
}

function groupByFamily(
  edges: EdgeRow[],
  selfId: string,
): Partial<Record<EdgeFamilySlug, GroupedRelative[]>> {
  const acc: Partial<Record<EdgeFamilySlug, GroupedRelative[]>> = {};
  for (const e of edges) {
    const familySlug = EDGE_TYPE_TO_FAMILY[e.type] ?? "attribution";
    const isOutgoing = e.from_id === selfId;
    const other = isOutgoing ? e.to_node : e.from_node;
    if (!other) continue;
    // Hide self-loops, assets, and system tissue (visitors, runners,
    // test fixtures). Assets render as creations elsewhere on the
    // page, not as relationship chips.
    if (other.id === selfId) continue;
    if (other.type === "asset") continue;
    if (isSystemNode(other.id)) continue;
    const slug = (other as { slug?: string | null }).slug;
    const href = slug
      ? `/people/${slug}`
      : nodeHrefFor(other.id, other.type);
    if (!acc[familySlug]) acc[familySlug] = [];
    acc[familySlug]!.push({
      edgeType: e.type,
      href,
      name: other.name || other.id,
      imageUrl: other.image_url ?? null,
      strength: e.strength ?? null,
    });
  }
  // Sort within each family by strength desc → name asc
  for (const slug of Object.keys(acc) as EdgeFamilySlug[]) {
    acc[slug]!.sort((a, b) => {
      const sa = a.strength ?? 0;
      const sb = b.strength ?? 0;
      if (sb !== sa) return sb - sa;
      return a.name.localeCompare(b.name);
    });
  }
  return acc;
}

function nodeHrefFor(id: string, type: string): string {
  // Concepts live in /vision; everything else flows through /people
  // by id (which the graph resolves slug-or-id alike).
  if (type === "concept") return `/vision/${encodeURIComponent(id)}`;
  return `/people/${encodeURIComponent(id)}`;
}
