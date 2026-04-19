"use client";

/**
 * PresencePage — the polished rendering of an identity in the graph.
 *
 * Mobile-first, brand-aware. Built to match the resonance of whatever
 * was named: a bass-music artist doesn't look like a sanctuary
 * doesn't look like a festival. The *shape* is shared across all of
 * them, the *feel* comes from the hero image, the accent colour
 * sampled from the dominant platform, and the way the creations are
 * laid out.
 *
 * See docs/agents/presence-builder.md for the design contract this
 * component implements. Layout blocks (hero / platforms / works /
 * lineage / claim) map 1:1 to the wireframe there.
 */

import Link from "next/link";
import { brandFor, type BrandTone } from "./brand";

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
  // Two-layer: the image (or a brand-accent radial) + a bottom-weighted
  // dark fade. The fade starts soft at 40% so the subject's face and
  // shoulders stay lit, then deepens into near-solid #08080a where the
  // title + tagline sit. Works for portraits, album covers, venue
  // photos — any composition where the focal point lives in the upper
  // half.
  const bottomFade =
    "linear-gradient(to bottom," +
    "rgba(0,0,0,0) 0%," +
    "rgba(0,0,0,0) 35%," +
    "rgba(8,8,10,0.35) 55%," +
    "rgba(8,8,10,0.82) 75%," +
    "rgba(8,8,10,0.98) 100%)";
  if (image_url) {
    return {
      backgroundImage: `${bottomFade},url('${image_url}')`,
      backgroundSize: "cover, cover",
      backgroundPosition: "center, center",
    } as const;
  }
  // No image → evocative radial from the brand accent.
  return {
    backgroundImage:
      `${bottomFade},radial-gradient(ellipse at 30% 20%,${accent.bg}aa,transparent 70%),` +
      `radial-gradient(ellipse at 80% 80%,#0b0b12 0%,#050509 100%)`,
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

// ── Component ─────────────────────────────────────────────────────────

export function PresencePage({ identity }: { identity: PresenceIdentity }) {
  const accent = brandFor(identity.provider);
  const hasImage = Boolean(identity.image_url);

  return (
    <main className="mx-auto max-w-md min-h-screen bg-[#08080a] text-white">
      {/* ── Hero ───────────────────────────────────────────────────── */}
      <section
        className="relative min-h-[70vh] flex flex-col justify-end px-6 pt-10 pb-8"
        style={heroGradient(identity.image_url, accent)}
      >
        <p
          className="text-[10px] uppercase tracking-[0.22em] font-semibold mb-3"
          style={{ color: accent.bg }}
        >
          · {identity.category} ·
        </p>
        <h1 className="text-4xl md:text-5xl font-extralight tracking-tight leading-[1.05]">
          {identity.name}
        </h1>
        {identity.tagline && (
          <p className="mt-3 text-[15px] leading-relaxed italic text-white/80 max-w-[32ch]">
            {identity.tagline}
          </p>
        )}
        {!hasImage && (
          <p className="mt-4 text-[10px] uppercase tracking-[0.14em] text-white/40">
            image pending · art will appear when the resolver finds one
          </p>
        )}
      </section>

      {/* ── Platforms ─────────────────────────────────────────────── */}
      {identity.presences.length > 0 && (
        <section className="px-6 pt-6 pb-3">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-white/50 mb-3">
            Find them
          </p>
          <div
            className="flex gap-2 overflow-x-auto -mx-6 px-6 pb-2"
            style={{ scrollbarWidth: "none" }}
          >
            {identity.presences.map((p) => {
              const tone = brandFor(p.provider);
              return (
                <a
                  key={p.url}
                  href={p.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="shrink-0 inline-flex items-center gap-2 rounded-full px-4 py-2.5 text-sm font-medium min-h-[44px]"
                  style={{
                    background: tone.gradient || tone.bg,
                    color: tone.fg,
                  }}
                >
                  {tone.label}
                </a>
              );
            })}
          </div>
        </section>
      )}

      {/* ── Creations ─────────────────────────────────────────────── */}
      {identity.creations.length > 0 && (
        <section className="px-6 pt-6">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-white/50 mb-3">
            Works
          </p>
          <div className="grid grid-cols-2 gap-3">
            {identity.creations.map((c) => {
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
      )}

      {/* ── Lineage ───────────────────────────────────────────────── */}
      {identity.inspired_by && identity.inspired_by.length > 0 && (
        <section className="px-6 pt-8">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-white/50 mb-3">
            Inspired by
          </p>
          <div className="flex flex-wrap gap-1.5">
            {identity.inspired_by.map((l) => (
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
      )}

      {/* ── Claim ─────────────────────────────────────────────────── */}
      {identity.claimed === false && (
        <section className="px-6 pt-10 pb-2">
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
            <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-white/50 mb-1.5">
              Held open
            </p>
            <p className="text-sm text-white/80 leading-relaxed">
              This page is a door held open for {identity.name}. Nothing is
              asked; if this is you, you can take the page as-is or send any
              edits and they'll be applied same day.
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
      )}

      {/* ── Canonical link ────────────────────────────────────────── */}
      <footer className="px-6 pt-8 pb-12 text-center">
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
