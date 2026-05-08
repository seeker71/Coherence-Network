"use client";

/**
 * PresencePage — the polished rendering of an identity in the graph.
 *
 * Mobile-first AND desktop-aware. The hero spans full width at every
 * viewport; the body lives in a centered 6xl canvas that splits into
 * a two-column grid (main + sidebar) at lg+. Built to match the
 * resonance of whatever was named: a bass-music artist doesn't look
 * like a sanctuary doesn't look like a festival. The *shape* is
 * shared across all of them, the *feel* comes from the hero image,
 * the accent colour sampled from the dominant platform, and the way
 * the creations are laid out.
 *
 * See docs/agents/presence-builder.md for the design contract this
 * component implements. Layout blocks (hero / platforms / works /
 * lineage / claim) map 1:1 to the wireframe there, with a desktop
 * variant that places platforms + concepts + lineage in a sidebar
 * to the right of the works/upcoming column.
 */

import type { ReactNode } from "react";
import Link from "next/link";
import { brandFor, type BrandTone } from "./brand";
import { UpcomingGatherings } from "./UpcomingGatherings";
import { KindredPresences } from "./KindredPresences";
import { BodyOfEvidence } from "./BodyOfEvidence";
import { RefineDoorway } from "./RefineDoorway";
import { LocationChip } from "./LocationChip";
import { CoLocated } from "./CoLocated";
import { RootedHere } from "./RootedHere";
import { HeldBy } from "./HeldBy";
import { WanderInto } from "./WanderInto";

export type Presence = {
  provider: string;
  url: string;
};

// Creation kinds — the vocabulary the renderer recognizes. This must
// stay in sync with the Python-side CREATION_KINDS in
// `api/app/services/creation_sources/base.py`. The graph already holds
// teachings, podcasts, books, courses, essays — not just music — so
// the type carries the full breadth of what people make in this field.
export type CreationKind =
  | "album"
  | "track"
  | "video"
  | "film"
  | "event"
  | "book"
  | "teaching"
  | "podcast"
  | "episode"
  | "essay"
  | "article"
  | "course"
  | "workshop"
  | "work";

export type Creation = {
  kind: CreationKind;
  name: string;
  url?: string | null;
  image_url?: string | null;
  /** When true, `url` is an internal Network route (same-tab nav); otherwise external (new tab). */
  internal?: boolean;
  /** Free-text era like "approximately 1984–1985 · age 13" or "2020 onwards".
   *  Drives chronological sort and the small marker at the top of the tile. */
  era?: string | null;
};

export type Lineage = {
  id: string;
  name: string;
  provider?: string;
};

export type PresenceIdentity = {
  id: string;
  /** Human-readable doorway slug from the graph node, when set.
   *  Drives `/people/{slug}` URL forms (refine, share, canonical). */
  slug?: string | null;
  name: string;
  category: string; // "Artist" | "Community" | "Project" | "Gathering" | ...
  tagline?: string;
  canonical_url: string;
  provider: string;
  image_url?: string | null;
  claimed?: boolean;
  presences: Presence[];
  creations: Creation[];
  inspired_by?: Lineage[];
  // Event-specific fields. When present, the hero adds a when/where
  // line under the tagline, and the body's lead block surfaces `note`
  // as a narrative paragraph. Without these, event nodes — which
  // almost never carry a canonical_url — would fall through to the
  // empty warm-garden view, hiding the rich `note` text that the
  // graph already holds.
  when_text?: string;
  where_text?: string;
  note?: string;
  // The graph's `description` field. When the body holds substantive
  // writing about a presence (not just a single-sentence og:description
  // fallback or a duplicate of name/tagline), render it as the lead
  // body block so the page carries who they are in their own voice.
  // Several presences (Liquid Bloom, Mose, Robert) hold thousands of
  // characters of beautiful description that was previously hidden
  // because the renderer never surfaced this slot.
  description?: string;
};

// ── Helpers ───────────────────────────────────────────────────────────

function heroGradient(image_url: string | null | undefined, accent: BrandTone) {
  // Multi-layer composition. The radial atmosphere ALWAYS lives at the
  // bottom of the stack; the image (when present) sits on top. If the
  // image url 404s or the host blocks hotlinking, the radials still
  // show through — so a broken image_url never produces an empty black
  // void on a 720px-tall hero.
  //
  // Layer order (top → bottom):
  //   1. bottomFade — soft to opaque toward the title baseline so the
  //      heading reads even over a busy photo
  //   2. image_url — only when set; when it loads, covers the radials
  //   3. radial atmosphere — branded glow + indigo undertone, always
  const bottomFade =
    "linear-gradient(to bottom," +
    "rgba(0,0,0,0) 0%," +
    "rgba(0,0,0,0) 35%," +
    "rgba(8,8,10,0.35) 55%," +
    "rgba(8,8,10,0.82) 75%," +
    "rgba(8,8,10,0.98) 100%)";
  // The atmospheric base. Two oppositional radials in the brand accent
  // (boosted to be visible even against slate-gray defaults), warmed by
  // an amber low-light wash, sitting on a deep indigo→near-black field.
  // Even without an image, the hero feels like a place rather than a
  // void.
  // `atmosphere` is FOUR composited radial layers — keep it as a list
  // so background-size / background-position cardinality matches.
  const atmosphereLayers = [
    `radial-gradient(ellipse 70% 55% at 22% 25%,${accent.bg}99,transparent 70%)`,
    `radial-gradient(ellipse 60% 45% at 78% 72%,${accent.bg}66,transparent 72%)`,
    `radial-gradient(ellipse 40% 35% at 50% 90%,rgba(245,158,11,0.18),transparent 72%)`,
    `radial-gradient(ellipse 100% 100% at 50% 50%,#11111e 0%,#070710 70%,#040408 100%)`,
  ];
  // Layer order (CSS background-image is painted FIRST → LAST as TOP →
  // BOTTOM), so the heading-fade goes first, the image (if present) on
  // top of the atmosphere, the atmosphere as the visible base.
  const layers: string[] = [bottomFade];
  if (image_url) layers.push(`url('${image_url}')`);
  layers.push(...atmosphereLayers);
  // Sizes / positions: bottomFade=100% 100%, image=cover, radials=cover
  // each. cover for radial works fine — they're auto-sized anyway, and
  // matching cardinality keeps the layer mapping unambiguous.
  const sizes = layers.map((_, i) => (i === 1 && image_url ? "cover" : "100% 100%")).join(", ");
  const positions = layers.map(() => "center").join(", ");
  return {
    backgroundImage: layers.join(","),
    backgroundSize: sizes,
    backgroundPosition: positions,
    backgroundRepeat: "no-repeat",
  } as const;
}

// Pull the first 4-digit year out of a free-text era string.
// "approximately 1984–1985 · age 13" → 1984; "~2003" → 2003; "" → null.
// Used to sort works chronologically when the body doesn't carry an
// explicit start_year field.
export function extractEraYear(era: string | null | undefined): number | null {
  if (!era) return null;
  const m = era.match(/(\d{4})/);
  return m ? Number(m[1]) : null;
}

// Coarse life-phase from a year. Tints the fallback gradient so the
// works walk a temperature arc — childhood warm amber, formation cool
// indigo, career teal-steel, network living green — even before any
// real image is attached. The phase is informational, not load-bearing;
// when no year can be parsed, we fall to the neutral near-black tail.
function eraPhaseTail(year: number | null): string {
  if (year === null) return "#0b0b12";
  if (year < 1990) return "#1a0d05"; // childhood — warm amber-black
  if (year < 2000) return "#0d0a1a"; // formation — deep indigo-black
  if (year < 2020) return "#051a17"; // career — teal-black
  return "#0a1505"; // network — living green-black
}

function creationArt(c: Creation, accent: BrandTone) {
  if (c.image_url) {
    return {
      backgroundImage: `url('${c.image_url}')`,
      backgroundSize: "cover",
      backgroundPosition: "center",
    } as const;
  }
  const tail = eraPhaseTail(extractEraYear(c.era));
  return {
    backgroundImage: `linear-gradient(135deg,${accent.bg}66,${tail})`,
  } as const;
}

function compactUrl(url: string | null | undefined): string {
  if (!url) return "";
  try {
    const parsed = new URL(url);
    const path = parsed.pathname === "/" ? "" : parsed.pathname.replace(/\/$/, "");
    return `${parsed.hostname.replace(/^www\./, "")}${path}`;
  } catch {
    return url.replace(/^https?:\/\//, "").replace(/\/$/, "");
  }
}

// Glyph carries the frequency of the creation. Music is rounded; text
// is angular; transmission is radiant; structured learning is a lattice.
// Read these at a glance — they're the only label on a creation tile
// when the image fails to load.
const KIND_GLYPH: Record<CreationKind, string> = {
  album: "◦",
  track: "♪",
  video: "▸",
  film: "▶",
  event: "✦",
  book: "▢",
  teaching: "✸",
  podcast: "◐",
  episode: "◗",
  essay: "¶",
  article: "❡",
  course: "⊞",
  workshop: "✻",
  work: "·",
};

// ── Sub-blocks ────────────────────────────────────────────────────────

/**
 * Render the graph's `description` as the body's lead narrative when it
 * holds substantive writing. Some presence descriptions in the graph
 * carry thousands of characters of body-of-fire prose; some carry only
 * a single-sentence og:description scrape. Both are valuable, but the
 * rendering should let either land as the page's voice.
 *
 * Lightweight handling of common markdown patterns: a leading `# Name`
 * heading is stripped (the page already shows the name in the hero);
 * `**bold**` runs render as <strong>; paragraphs split on blank lines.
 * Anything else passes through as plain text. No external markdown
 * dependency — this is intentional. Heavier rendering can come later
 * when a presence asks for it.
 */
function DescriptionBlock({ raw }: { raw: string }) {
  // Strip a leading "# Name" heading (and the blank line after it).
  // The hero already carries the name; repeating it here calcifies.
  const trimmed = raw
    .replace(/^\s*#\s+[^\n]+\n+/, "")
    .replace(/\r\n/g, "\n")
    .trim();
  const paragraphs = trimmed.split(/\n{2,}/).map((p) => p.trim()).filter(Boolean);
  if (paragraphs.length === 0) return null;
  return (
    <section>
      <div className="space-y-4 text-base sm:text-lg leading-relaxed text-white/90 max-w-[58ch]">
        {paragraphs.map((para, i) => (
          <p key={i}>{renderInline(para)}</p>
        ))}
      </div>
    </section>
  );
}

function renderInline(text: string): ReactNode {
  // Pull **bold** runs out so they render as <strong>; everything
  // else stays plain.
  const parts: ReactNode[] = [];
  const re = /\*\*([^*]+)\*\*/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let key = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    parts.push(<strong key={key++}>{m[1]}</strong>);
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts.length ? parts : text;
}

function PlatformChips({
  presences,
  identityName,
}: {
  presences: Presence[];
  identityName: string;
}) {
  if (presences.length === 0) return null;
  return (
    <section>
      <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-white/50 mb-3">
        Find them
      </p>
      <div className="flex flex-wrap gap-2.5">
        {presences.map((p) => {
          const tone = brandFor(p.provider);
          return (
            <a
              key={p.url}
              href={p.url}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={`${tone.label} — ${identityName}`}
              title={tone.label}
              className="shrink-0 inline-flex items-center justify-center rounded-full min-w-[44px] min-h-[44px] w-11 h-11 transition-transform hover:scale-105"
              style={{
                background: tone.gradient || tone.bg,
                color: tone.fg,
              }}
            >
              {tone.iconPath ? (
                <svg
                  viewBox="0 0 24 24"
                  width="20"
                  height="20"
                  fill="currentColor"
                  aria-hidden="true"
                >
                  <path d={tone.iconPath} />
                </svg>
              ) : (
                <span className="text-xs font-semibold tracking-tight px-1">
                  {tone.label.slice(0, 2)}
                </span>
              )}
            </a>
          );
        })}
      </div>
    </section>
  );
}

function PresenceOverview({
  identity,
  inspiredCount,
}: {
  identity: PresenceIdentity;
  inspiredCount: number;
}) {
  const canonicalDisplay = compactUrl(identity.canonical_url);
  const graphHref = `/nodes/${encodeURIComponent(identity.id)}`;
  const surfaces = [
    ...(identity.canonical_url
      ? [{ provider: identity.provider || "web", url: identity.canonical_url }]
      : []),
    ...identity.presences,
  ];
  const dedupedSurfaces = surfaces.filter(
    (surface, index, all) =>
      surface.url &&
      all.findIndex((candidate) => candidate.url.replace(/\/$/, "") === surface.url.replace(/\/$/, "")) === index,
  );

  return (
    <section className="rounded-2xl border border-white/10 bg-white/[0.035] p-5">
      <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-white/50 mb-4">
        At a glance
      </p>
      <dl className="space-y-3 text-sm">
        <div>
          <dt className="text-[10px] uppercase tracking-[0.14em] text-white/40">
            Category
          </dt>
          <dd className="mt-1 text-white/90">{identity.category}</dd>
        </div>
        {canonicalDisplay && (
          <div>
            <dt className="text-[10px] uppercase tracking-[0.14em] text-white/40">
              Home
            </dt>
            <dd className="mt-1 break-words text-white/90">{canonicalDisplay}</dd>
          </div>
        )}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <dt className="text-[10px] uppercase tracking-[0.14em] text-white/40">
              Works
            </dt>
            <dd className="mt-1 text-white/90">{identity.creations.length}</dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-[0.14em] text-white/40">
              Lineage
            </dt>
            <dd className="mt-1 text-white/90">{inspiredCount}</dd>
          </div>
        </div>
      </dl>

      {dedupedSurfaces.length > 0 && (
        <div className="mt-6">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-white/50 mb-3">
            Presence map
          </p>
          <div className="space-y-2">
            {dedupedSurfaces.map((surface) => {
              const tone = brandFor(surface.provider);
              return (
                <a
                  key={surface.url}
                  href={surface.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 hover:bg-white/[0.07]"
                >
                  <span className="block text-xs font-medium text-white/80">
                    {tone.label}
                  </span>
                  <span className="block truncate text-xs text-white/45">
                    {compactUrl(surface.url)}
                  </span>
                </a>
              );
            })}
          </div>
        </div>
      )}

      <div className="mt-6">
        <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-white/50 mb-3">
          Entry points
        </p>
        <div className="space-y-2">
          {identity.canonical_url && (
            <a
              href={identity.canonical_url}
              target="_blank"
              rel="noopener noreferrer"
              className="block rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-white/80 hover:bg-white/[0.07]"
            >
              Official source
            </a>
          )}
          <Link
            href={graphHref}
            className="block rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-white/80 hover:bg-white/[0.07]"
          >
            Graph node
          </Link>
        </div>
      </div>
    </section>
  );
}

// Compact era marker for the tile corner. Strips wordy prefixes
// ("approximately ", "~") so the year-shape lands clean. Falls back
// to the raw string if no year is parseable. Empty string → no marker.
function eraMarker(era: string | null | undefined): string {
  if (!era) return "";
  const compact = era
    .replace(/^\s*(approximately|approx\.?|circa|ca\.?|~)\s*/i, "")
    .replace(/\s+·\s+age\s+\d+\s*$/i, "")
    .trim();
  return compact;
}

function CreationsGrid({
  creations,
  accent,
}: {
  creations: Creation[];
  accent: BrandTone;
}) {
  const visible = creations.filter((c) => c.kind !== "event");
  if (visible.length === 0) return null;
  // Walk the lineage forward in time when an era year is parseable.
  // Works without a year sort to the end so they don't masquerade as
  // ancient. Stable on name as the secondary key for deterministic
  // ordering inside the same year-bucket.
  const ordered = [...visible].sort((a, b) => {
    const ay = extractEraYear(a.era);
    const by = extractEraYear(b.era);
    if (ay === null && by === null) return a.name.localeCompare(b.name);
    if (ay === null) return 1;
    if (by === null) return -1;
    if (ay !== by) return ay - by;
    return a.name.localeCompare(b.name);
  });
  return (
    <section>
      <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-white/50 mb-3">
        Works
      </p>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-3 xl:grid-cols-4 gap-3 sm:gap-4">
        {ordered.map((c) => {
          const Tag = (c.url ? "a" : "div") as "a" | "div";
          const extra = c.url
            ? c.internal
              ? { href: c.url }
              : { href: c.url, target: "_blank", rel: "noopener noreferrer" }
            : {};
          const eraText = eraMarker(c.era);
          return (
            <Tag
              key={`${c.kind}-${c.name}`}
              {...(extra as Record<string, string>)}
              className="block group"
            >
              <div
                className="aspect-square rounded-xl border border-white/10 relative overflow-hidden"
                style={creationArt(c, accent)}
              >
                {eraText && !c.image_url ? (
                  <span className="absolute top-2 left-2 right-2 text-white/70 text-[10px] uppercase tracking-[0.14em] leading-snug line-clamp-2">
                    {eraText}
                  </span>
                ) : null}
                <span
                  className="absolute bottom-1.5 right-2 text-white/70 text-xs"
                  aria-hidden="true"
                >
                  {KIND_GLYPH[c.kind] || "·"}
                </span>
              </div>
              <p className="mt-2 text-sm text-white/90 leading-snug line-clamp-2">
                {c.name}
              </p>
              <p className="text-[10px] uppercase tracking-[0.14em] text-white/40">
                {c.kind}
              </p>
            </Tag>
          );
        })}
      </div>
    </section>
  );
}

function HeldOpen({
  identity,
  accent,
}: {
  identity: PresenceIdentity;
  accent: BrandTone;
}) {
  if (identity.claimed !== false) return null;
  return (
    <section>
      <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
        <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-white/50 mb-1.5">
          Held open
        </p>
        <p className="text-sm text-white/80 leading-relaxed">
          This page is a door held open for {identity.name}. Nothing is
          asked; if this is you, you can take the page as-is or send any
          edits and they&apos;ll be applied same day.
        </p>
        <Link
          href={`/claim/${encodeURIComponent(identity.id)}`}
          className="mt-3 inline-flex items-center gap-1 text-sm font-medium"
          style={{ color: accent.bg }}
        >
          this is me →
        </Link>
      </div>
    </section>
  );
}

// ── Component ─────────────────────────────────────────────────────────

// Brand keys we have full color/icon support for. When the root
// `provider` (often a domain like "actualize.earth") isn't one of these
// but the presence carries one of them in its `presences[]`, prefer
// that — it gives the hero a vibrant atmosphere instead of the slate
// gray fallback.
const KNOWN_BRANDS = new Set([
  "spotify",
  "bandcamp",
  "youtube",
  "soundcloud",
  "apple-music",
  "substack",
  "patreon",
  "instagram",
  "tiktok",
  "x",
  "twitter",
  "facebook",
  "linktree",
  "linkedin",
  "vimeo",
  "imdb",
  "ecstaticdance",
  "beatport",
  "threads",
  "wikipedia",
]);

function pickAccentProvider(identity: PresenceIdentity): string {
  if (KNOWN_BRANDS.has(identity.provider)) return identity.provider;
  // Walk presences in order — first known brand wins. Order in the
  // `presences[]` array roughly mirrors which surface the contributor
  // emphasized when registering, so the first known one is a good
  // proxy for "the platform this person is most strongly known on".
  for (const p of identity.presences || []) {
    if (KNOWN_BRANDS.has(p.provider)) return p.provider;
  }
  return identity.provider;
}

export function PresencePage({ identity }: { identity: PresenceIdentity }) {
  const accent = brandFor(pickAccentProvider(identity));
  const hasImage = Boolean(identity.image_url);
  const inspired = identity.inspired_by || [];

  return (
    <main className="min-h-screen bg-[#08080a] text-white">
      {/* ── Hero — full-width, content centered to 6xl ────────────── */}
      {/* Height tuned so the hero feels present without dominating: the
          name + tagline sit roughly two-thirds down regardless of image
          state, and the body content begins above the fold on a 1440x900
          laptop. Earlier 80vh values reserved 720px of black void when
          the image_url 404'd. */}
      <section
        className="relative min-h-[44vh] sm:min-h-[52vh] lg:min-h-[58vh] flex flex-col justify-end"
        style={heroGradient(identity.image_url, accent)}
      >
        <div className="mx-auto w-full max-w-6xl px-6 sm:px-8 lg:px-12 pt-10 pb-8 sm:pb-12 lg:pb-16">
          <p
            className="text-[10px] uppercase tracking-[0.22em] font-semibold mb-3"
            style={{ color: accent.bg }}
          >
            · {identity.category} ·
          </p>
          <h1 className="text-4xl sm:text-5xl lg:text-6xl xl:text-7xl font-extralight tracking-tight leading-[1.05] max-w-4xl">
            {identity.name}
          </h1>
          {identity.tagline && (
            <p className="mt-3 sm:mt-4 text-[15px] sm:text-base lg:text-lg leading-relaxed italic text-white/80 max-w-[48ch]">
              {identity.tagline}
            </p>
          )}
          {(identity.when_text || identity.where_text) && (
            <p className="mt-3 sm:mt-4 text-[12px] sm:text-sm uppercase tracking-[0.18em] font-medium text-white/70">
              {[identity.when_text, identity.where_text]
                .filter(Boolean)
                .join(" · ")}
            </p>
          )}
          {/* Earlier this slot held an "image pending · art will appear
              when the resolver finds one" line. That was an internal TODO
              leaking onto the visitor's first impression. The radial
              atmosphere fallback already carries presence on its own; no
              text needed when the image hasn't landed yet. */}
        </div>
      </section>

      {/* ── Body — two-column grid at lg+ ─────────────────────────── */}
      <div className="mx-auto w-full max-w-6xl px-6 sm:px-8 lg:px-12 py-8 sm:py-12 lg:py-16 grid grid-cols-1 lg:grid-cols-[1fr_minmax(280px,340px)] gap-10 lg:gap-14">
        {/* Main column */}
        <div className="space-y-10 lg:space-y-12 min-w-0">
          {identity.note && (
            <section>
              <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-white/50 mb-3">
                What this gathering held
              </p>
              <p className="text-base sm:text-lg leading-relaxed text-white/90 max-w-[58ch]">
                {identity.note}
              </p>
            </section>
          )}
          {identity.description && !identity.note && (
            <DescriptionBlock raw={identity.description} />
          )}
          <UpcomingGatherings
            identityId={identity.id}
            identityName={identity.name}
            accent={accent}
          />
          <CreationsGrid creations={identity.creations} accent={accent} />
        </div>

        {/* Sidebar — collapses to full-width above the main column on
            small screens via lg:order, but here we just place it after
            so mobile stacking reads main → sidebar. For visitors who
            care about platforms/concepts before scrolling through
            works, the hero already shows the name+category+tagline and
            the platforms appear immediately after on mobile. */}
        <aside className="space-y-10 lg:space-y-8 min-w-0">
          <PresenceOverview identity={identity} inspiredCount={inspired.length} />
          {/* Every contribution and influence flowing through this
              presence, from any source — the unified body-of-evidence
              view. Emissions (works), Shaped-by (influences grouped
              by source: Audible, YouTube, Physical, Lineage), Field
              connections (concept resonances + relational threads
              colored by family), and Inbound recognition. */}
          <BodyOfEvidence
            presenceId={identity.id}
            externalPresences={identity.presences}
          />
          <RefineDoorway identity={identity} />
          <PlatformChips
            presences={identity.presences}
            identityName={identity.name}
          />
          <LocationChip presenceId={identity.id} />
          {/* When the page IS a place, show every presence rooted in
              it. The component renders nothing for non-place ids, so
              passing the id unconditionally is safe and keeps the
              place-vs-presence rendering unified. */}
          {identity.id.startsWith("place:") && (
            <RootedHere placeId={identity.id} />
          )}
          {/* When the page IS an event, surface the hosts as living
              doorways back into the lineage that held it. */}
          {identity.id.startsWith("event:") && (
            <HeldBy eventId={identity.id} />
          )}
          {/* `ResonatesWith` (concept resonance chips) and
              `InspiredByChips` (flat inspired-by list) composted —
              both surfaces fully covered by BodyOfEvidence above
              (Field connections → Being family; Shaped by sections
              grouped by source). KindredPresences and CoLocated
              carry distinct signals (shared-concept neighbors,
              co-location through places) so they remain. */}
          <KindredPresences presenceId={identity.id} />
          <CoLocated presenceId={identity.id} />
          <HeldOpen identity={identity} accent={accent} />
        </aside>
      </div>

      {/* ── Wander into — closing doorways into the body ─────────── */}
      <div className="mx-auto w-full max-w-6xl px-6 sm:px-8 lg:px-12 pb-12">
        <WanderInto presenceId={identity.id} />
      </div>

      {/* ── Canonical link ────────────────────────────────────────── */}
      {identity.canonical_url && (
        <footer className="px-6 pb-12 text-center">
          <a
            href={identity.canonical_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-white/50 hover:text-white/80 underline-offset-4 hover:underline break-all"
          >
            {compactUrl(identity.canonical_url)}
          </a>
        </footer>
      )}

      {/* ── Schema.org structured data — for machine readers ──────── */}
      {/* Helps search engines and LLM crawlers see the shape of each
          presence: their type, name, image, related URLs, and
          (where relevant) location. Inline JSON-LD keeps it
          server-rendered and crawlable on first paint. */}
      <SchemaOrgScript identity={identity} />
    </main>
  );
}

/**
 * Inline JSON-LD using schema.org vocabulary so machine readers
 * (Google, Bing, LLM crawlers) understand each presence's shape.
 *
 * Mapping graph node types → schema.org types:
 *   contributor / interested-person → Person
 *   community / network-org          → Organization
 *   event                             → Event
 *   place / scene                     → Place
 *   asset                             → CreativeWork
 *   practice                          → Course (closest schema type)
 *
 * Only fields the body actually carries are emitted. This is a
 * server-renderable component (no client effects, no state) so the
 * JSON-LD ships with the first HTML payload.
 */
function SchemaOrgScript({ identity }: { identity: PresenceIdentity }) {
  const id = identity.id;
  let schemaType: string;
  if (id.startsWith("event:")) schemaType = "Event";
  else if (id.startsWith("place:") || id.startsWith("scene:"))
    schemaType = "Place";
  else if (
    id.startsWith("community:") ||
    id.startsWith("community-") ||
    id.startsWith("network-")
  )
    schemaType = "Organization";
  else if (id.startsWith("asset:")) schemaType = "CreativeWork";
  else if (id.startsWith("practice:")) schemaType = "Course";
  else schemaType = "Person";

  const json: Record<string, unknown> = {
    "@context": "https://schema.org",
    "@type": schemaType,
    name: identity.name,
    url: `https://coherencycoin.com/people/${encodeURIComponent(id)}`,
  };
  if (identity.image_url) json.image = identity.image_url;
  if (identity.tagline || identity.note || identity.description) {
    json.description = (identity.tagline ||
      identity.note ||
      identity.description ||
      "")
      .substring(0, 500);
  }
  if (identity.canonical_url) json.sameAs = [identity.canonical_url];
  if (schemaType === "Event") {
    if (identity.when_text) json.startDate = identity.when_text;
    if (identity.where_text) json.location = { "@type": "Place", name: identity.where_text };
  }
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(json) }}
    />
  );
}
