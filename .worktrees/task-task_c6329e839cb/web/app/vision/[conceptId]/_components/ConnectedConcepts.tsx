import Link from "next/link";
import { displayName, EDGE_LABELS } from "@/lib/vision-utils";
import type { Edge } from "@/lib/types/vision";

/* ── Multi-dimensional routing + grouping ─────────────────────────────── */

type GroupKey =
  | "concepts"
  | "people"
  | "communities"
  | "places"
  | "gatherings"
  | "practices"
  | "works"
  | "ideas"
  | "specs"
  | "other";

/**
 * Extract the type prefix from a node id. The graph uses two shapes:
 * - colon-separated: `contributor:xxx`, `community:xxx`, `event:xxx`
 * - hyphen-separated: `asset-xxx`, `scene-xxx`, `network-xxx`
 * Both are canonical; we normalise here so grouping catches every form.
 */
function idPrefix(id: string): string {
  if (id.startsWith("lc-")) return "lc";
  const colonIdx = id.indexOf(":");
  if (colonIdx > 0) return id.slice(0, colonIdx);
  const hyphenIdx = id.indexOf("-");
  if (hyphenIdx > 0) return id.slice(0, hyphenIdx);
  return id;
}

function groupFor(id: string): GroupKey {
  const p = idPrefix(id);
  switch (p) {
    case "lc": return "concepts";
    case "contributor": return "people";
    case "community":
    case "network":
    case "network-org": return "communities";
    case "scene":
    case "venue":
    case "place": return "places";
    case "event":
    case "gathering": return "gatherings";
    case "practice":
    case "skill": return "practices";
    case "asset": return "works";
    case "idea": return "ideas";
    case "spec": return "specs";
    default:
      // Living Codex concepts arrive as bare lowercase ids (e.g. "wisdom",
      // "consciousness", "memory") with no colon or hyphen prefix. They're
      // the same kind of thing as lc-* concepts — same ontology layer, same
      // kind of entity to a visitor — so they fold into the "concepts"
      // group rather than splitting into a separate "other" bucket.
      if (/^[a-z][a-z0-9-]*$/.test(id) && !id.includes(":")) return "concepts";
      return "other";
  }
}

function hrefFor(id: string): string {
  // Every node id — lc concept, bare Codex concept, contributor, asset,
  // scene, event, idea, spec — routes through the universal /nodes/[id]
  // viewer, which picks the right typed page inline. Callers don't need
  // to know a node's shape to link to it.
  return `/nodes/${encodeURIComponent(id)}`;
}

const GROUP_META: Record<GroupKey, { label: string; accent: string }> = {
  concepts: { label: "Concepts", accent: "amber" },
  people: { label: "People", accent: "rose" },
  communities: { label: "Communities", accent: "purple" },
  places: { label: "Places", accent: "teal" },
  gatherings: { label: "Gatherings", accent: "purple" },
  practices: { label: "Practices", accent: "emerald" },
  works: { label: "Works", accent: "blue" },
  ideas: { label: "Ideas", accent: "emerald" },
  specs: { label: "Specs", accent: "cyan" },
  other: { label: "Other", accent: "stone" },
};

const GROUP_ORDER: GroupKey[] = [
  "concepts",
  "people",
  "communities",
  "places",
  "gatherings",
  "practices",
  "works",
  "ideas",
  "specs",
  "other",
];

const ACCENT_CLASSES: Record<string, { bg: string; text: string; border: string; hover: string }> = {
  amber: {
    bg: "bg-amber-500/10",
    text: "text-amber-300/80",
    border: "border-amber-500/20",
    hover: "hover:text-amber-300 hover:border-amber-500/40",
  },
  rose: {
    bg: "bg-rose-500/10",
    text: "text-rose-300/80",
    border: "border-rose-500/20",
    hover: "hover:text-rose-300 hover:border-rose-500/40",
  },
  purple: {
    bg: "bg-purple-500/10",
    text: "text-purple-300/80",
    border: "border-purple-500/20",
    hover: "hover:text-purple-300 hover:border-purple-500/40",
  },
  teal: {
    bg: "bg-teal-500/10",
    text: "text-teal-300/80",
    border: "border-teal-500/20",
    hover: "hover:text-teal-300 hover:border-teal-500/40",
  },
  emerald: {
    bg: "bg-emerald-500/10",
    text: "text-emerald-300/80",
    border: "border-emerald-500/20",
    hover: "hover:text-emerald-300 hover:border-emerald-500/40",
  },
  blue: {
    bg: "bg-blue-500/10",
    text: "text-blue-300/80",
    border: "border-blue-500/20",
    hover: "hover:text-blue-300 hover:border-blue-500/40",
  },
  cyan: {
    bg: "bg-cyan-500/10",
    text: "text-cyan-300/80",
    border: "border-cyan-500/20",
    hover: "hover:text-cyan-300 hover:border-cyan-500/40",
  },
  stone: {
    bg: "bg-stone-500/10",
    text: "text-stone-400/80",
    border: "border-stone-700/30",
    hover: "hover:text-stone-300 hover:border-stone-600/40",
  },
};

function edgeLabel(edgeType: string): string {
  return EDGE_LABELS[edgeType] || edgeType;
}

/* ── Component ────────────────────────────────────────────────────────── */

type Touch = {
  targetId: string;
  edgeType: string;
  direction: "out" | "in";
};

export function ConnectedConcepts({
  outgoing,
  incoming,
  nameMap,
  mode,
}: {
  outgoing: Edge[];
  incoming: Edge[];
  nameMap: Record<string, string>;
  mode: "full" | "compact";
}) {
  // Fold outgoing + incoming into a single "touches" list keyed by target.
  // A visitor doesn't need to reason about edge direction to understand
  // that two concepts are connected; direction only matters for the
  // edge-type label (extends vs. extended-by, etc.).
  const touchesByTarget = new Map<string, Touch[]>();
  const addTouch = (target: string, edgeType: string, direction: "out" | "in") => {
    if (!touchesByTarget.has(target)) touchesByTarget.set(target, []);
    touchesByTarget.get(target)!.push({ targetId: target, edgeType, direction });
  };
  for (const e of outgoing) addTouch(e.to, e.type, "out");
  for (const e of incoming) addTouch(e.from, e.type, "in");

  // Group targets by kind (concept / person / place / ...).
  const grouped: Record<GroupKey, string[]> = {
    concepts: [],
    people: [],
    communities: [],
    places: [],
    gatherings: [],
    practices: [],
    works: [],
    ideas: [],
    specs: [],
    other: [],
  };
  for (const target of touchesByTarget.keys()) {
    grouped[groupFor(target)].push(target);
  }
  // Sort targets alphabetically by display name inside each group.
  for (const key of Object.keys(grouped) as GroupKey[]) {
    grouped[key].sort((a, b) =>
      displayName(a, nameMap).localeCompare(displayName(b, nameMap)),
    );
  }

  if (touchesByTarget.size === 0) return null;

  if (mode === "compact") {
    // Compact mode: single row of chips across all groups, lightly
    // color-coded by group so the eye can still sort them at a glance.
    const allTargets: string[] = [];
    for (const key of GROUP_ORDER) allTargets.push(...grouped[key]);
    return (
      <div className="flex flex-wrap gap-2 p-4 rounded-xl border border-stone-800/30 bg-stone-900/20">
        <span className="text-xs text-stone-600 mr-2">Connected:</span>
        {allTargets.map((id) => {
          const accent = GROUP_META[groupFor(id)].accent;
          const c = ACCENT_CLASSES[accent];
          return (
            <Link
              key={id}
              href={hrefFor(id)}
              className={`text-xs px-2 py-1 rounded-full border transition-colors ${c.text} ${c.border} ${c.hover}`}
            >
              {displayName(id, nameMap)}
            </Link>
          );
        })}
      </div>
    );
  }

  return (
    <section className="rounded-2xl border border-stone-800/40 bg-stone-900/30 p-6 space-y-5">
      <div>
        <h2 className="text-lg font-light text-stone-300">Connected Frequencies</h2>
        <p className="text-xs text-stone-500 mt-1">
          The people, places, works, and concepts the graph shows connected to this one.
        </p>
      </div>

      <div className="space-y-5">
        {GROUP_ORDER.map((key) => {
          const targets = grouped[key];
          if (targets.length === 0) return null;
          const meta = GROUP_META[key];
          const c = ACCENT_CLASSES[meta.accent];
          return (
            <div key={key} className="space-y-2">
              <p
                className={`text-[11px] uppercase tracking-[0.18em] font-medium ${c.text}`}
              >
                {meta.label} · {targets.length}
              </p>
              <div className="flex flex-wrap gap-2">
                {targets.map((id) => {
                  const touches = touchesByTarget.get(id) || [];
                  // Prefer outgoing edge-type as the primary label; fall
                  // back to incoming. Multiple edge types between the same
                  // two nodes are rare; if present, show the first.
                  const primary = touches[0];
                  const label = edgeLabel(primary.edgeType);
                  return (
                    <Link
                      key={id}
                      href={hrefFor(id)}
                      className={`group inline-flex items-center gap-2 px-3 py-1.5 rounded-full border transition-colors ${c.border} ${c.bg} ${c.hover}`}
                      title={label}
                    >
                      <span className={`text-sm ${c.text}`}>
                        {displayName(id, nameMap)}
                      </span>
                      <span className="text-[10px] text-stone-500 group-hover:text-stone-400">
                        {label}
                      </span>
                    </Link>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
