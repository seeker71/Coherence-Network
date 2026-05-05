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

import Link from "next/link";
import { brandFor, type BrandTone } from "./brand";
import { UpcomingGatherings } from "./UpcomingGatherings";
import { ResonatesWith } from "./ResonatesWith";
import { KindredPresences } from "./KindredPresences";

export type Presence = {
  provider: string;
  url: string;
};

export type Creation = {
  kind: "album" | "track" | "video" | "event" | "book" | "work";
  name: string;
  url?: string | null;
  image_url?: string | null;
};

export type Lineage = {
  id: string;
  name: string;
  provider?: string;
};

export type PresenceIdentity = {
  id: string;
  name: string;
  category: string; // "Artist" | "Community" | "Project" | ...
  tagline?: string;
  canonical_url: string;
  provider: string;
  image_url?: string | null;
  claimed?: boolean;
  presences: Presence[];
  creations: Creation[];
  inspired_by?: Lineage[];
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

function creationArt(c: Creation, accent: BrandTone) {
  if (c.image_url) {
    return {
      backgroundImage: `url('${c.image_url}')`,
      backgroundSize: "cover",
      backgroundPosition: "center",
    } as const;
  }
  return {
    backgroundImage: `linear-gradient(135deg,${accent.bg}66,#0b0b12)`,
  } as const;
}

const KIND_GLYPH: Record<Creation["kind"], string> = {
  album: "◦",
  track: "♪",
  video: "▸",
  event: "✦",
  book: "▢",
  work: "·",
};

// ── Sub-blocks ────────────────────────────────────────────────────────

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

function CreationsGrid({
  creations,
  accent,
}: {
  creations: Creation[];
  accent: BrandTone;
}) {
  const visible = creations.filter((c) => c.kind !== "event");
  if (visible.length === 0) return null;
  return (
    <section>
      <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-white/50 mb-3">
        Works
      </p>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-3 xl:grid-cols-4 gap-3 sm:gap-4">
        {visible.map((c) => {
          const Tag = (c.url ? "a" : "div") as "a" | "div";
          const extra = c.url
            ? { href: c.url, target: "_blank", rel: "noopener noreferrer" }
            : {};
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

function InspiredByChips({
  inspired,
}: {
  inspired: Lineage[];
}) {
  if (inspired.length === 0) return null;
  return (
    <section>
      <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-white/50 mb-3">
        Inspired by
      </p>
      <div className="flex flex-wrap gap-1.5">
        {inspired.map((l) => (
          <Link
            key={l.id}
            href={`/people/${encodeURIComponent(l.id)}`}
            className="rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs text-white/80 hover:bg-white/10"
          >
            {l.name}
          </Link>
        ))}
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
          {!hasImage && (
            <p className="mt-4 text-[10px] uppercase tracking-[0.14em] text-white/40">
              image pending · art will appear when the resolver finds one
            </p>
          )}
        </div>
      </section>

      {/* ── Body — two-column grid at lg+ ─────────────────────────── */}
      <div className="mx-auto w-full max-w-6xl px-6 sm:px-8 lg:px-12 py-8 sm:py-12 lg:py-16 grid grid-cols-1 lg:grid-cols-[1fr_minmax(280px,340px)] gap-10 lg:gap-14">
        {/* Main column */}
        <div className="space-y-10 lg:space-y-12 min-w-0">
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
          <PlatformChips
            presences={identity.presences}
            identityName={identity.name}
          />
          <ResonatesWith presenceId={identity.id} />
          <KindredPresences presenceId={identity.id} />
          <InspiredByChips inspired={inspired} />
          <HeldOpen identity={identity} accent={accent} />
        </aside>
      </div>

      {/* ── Canonical link ────────────────────────────────────────── */}
      <footer className="px-6 pb-12 text-center">
        <a
          href={identity.canonical_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-white/50 hover:text-white/80 underline-offset-4 hover:underline break-all"
        >
          {identity.canonical_url.replace(/^https?:\/\//, "")}
        </a>
      </footer>
    </main>
  );
}
