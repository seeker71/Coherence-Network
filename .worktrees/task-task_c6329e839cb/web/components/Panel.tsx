"use client";

/**
 * Panel — one visual primitive for every panel on every screen.
 *
 * The arc through a new visitor's experience crosses a dozen panels —
 * morning nudge, invite banner, welcome, empty states, live-breath,
 * kin activity. Before Panel existed each one was hand-composed, with
 * its own gradient, its own eyebrow size, its own radius, its own
 * padding. The accumulation felt fragmented even when each choice
 * was defensible in isolation.
 *
 * Panel reduces the surface to four variants × four slots and binds
 * all color values to semantic theme tokens (bg-card, text-foreground,
 * border-border) so the panel adapts to dark + light modes instead of
 * hard-coding a single palette. The small warm/cool accents use
 * theme-aware opacity overlays on top of the semantic base.
 *
 *   Variants (tone):
 *     • "warm"     — the viewer's own moments (morning greeting, their
 *                    contribution reflected). Amber accents.
 *     • "cool"     — the organism's own moments (invitations, breath,
 *                    kin activity). Teal accents.
 *     • "neutral"  — quieter content, no accent color.
 *     • "empty"    — same surface as neutral but dimmer, for empty
 *                    states that want to recede.
 *
 *   Slots:
 *     • eyebrow    — small uppercase tracking-wide caption
 *     • heading    — foreground-tone body text, the main sentence
 *     • body       — children, any JSX (paragraphs, quotes, lists)
 *     • cta        — link or button at the foot
 *
 *   Other:
 *     • icon       — optional emoji or element, optically centered
 *     • onDismiss  — renders the × at a consistent position
 */

import type { ReactNode } from "react";

export type PanelVariant = "warm" | "cool" | "neutral" | "empty";

interface PanelProps {
  variant?: PanelVariant;
  icon?: string | ReactNode;
  eyebrow?: ReactNode;
  heading?: ReactNode;
  children?: ReactNode;
  cta?: ReactNode;
  onDismiss?: () => void;
  dismissLabel?: string;
  ariaLabel?: string;
  className?: string;
  id?: string;
}

// Shared tokens — the whole design system for panels lives here.
// Colors bind to semantic theme variables so dark + light both look
// considered. Accent tints are added as thin overlay layers so the
// base card color always wins on contrast.
const PANEL_BASE =
  "relative max-w-3xl mx-3 sm:mx-auto rounded-2xl px-5 py-4 " +
  "bg-card text-card-foreground border " +
  "transition-colors";

// Warm tint: amber ring on the border, faint warm overlay on the base.
// The ring-inset pseudo-background uses the chart-1 (gold) token which
// is defined for both themes with AA-compliant contrast.
const VARIANT_CLASSES: Record<PanelVariant, string> = {
  warm:
    "border-[hsl(var(--primary)/0.25)] " +
    "bg-[linear-gradient(135deg,hsl(var(--card))_0%,hsl(var(--card))_55%,hsl(var(--primary)/0.08)_100%)]",
  cool:
    "border-[hsl(var(--chart-2)/0.35)] " +
    "bg-[linear-gradient(135deg,hsl(var(--card))_0%,hsl(var(--card))_55%,hsl(var(--chart-2)/0.10)_100%)]",
  neutral: "border-border",
  empty:
    "border-[hsl(var(--border)/0.6)] " +
    "bg-[hsl(var(--card)/0.6)]",
};

// Eyebrow colors pick from theme-aware chart tokens that stay legible
// in both modes (primary = gold, chart-2 = teal, muted-foreground).
const EYEBROW_CLASSES: Record<PanelVariant, string> = {
  warm: "text-[hsl(var(--primary))]",
  cool: "text-[hsl(var(--chart-2))]",
  neutral: "text-muted-foreground",
  empty: "text-muted-foreground/80",
};

const EYEBROW_BASE =
  "text-[11px] uppercase tracking-[0.18em] font-semibold mb-1.5";

const HEADING_BASE = "text-base md:text-lg font-light leading-snug mb-2";

// Heading uses the theme foreground everywhere — it's the place where
// contrast discipline matters most.
const HEADING_TONE: Record<PanelVariant, string> = {
  warm: "text-foreground",
  cool: "text-foreground",
  neutral: "text-foreground",
  empty: "text-foreground/80",
};

const DISMISS_BASE =
  "absolute top-2.5 right-2.5 w-7 h-7 rounded-full flex items-center " +
  "justify-center text-muted-foreground hover:text-foreground " +
  "hover:bg-accent/40 transition-colors";

export function Panel({
  variant = "neutral",
  icon,
  eyebrow,
  heading,
  children,
  cta,
  onDismiss,
  dismissLabel = "Close",
  ariaLabel,
  className = "",
  id,
}: PanelProps) {
  const hasIcon = Boolean(icon);
  return (
    <section
      id={id}
      aria-label={ariaLabel}
      className={`${PANEL_BASE} ${VARIANT_CLASSES[variant]} ${className}`}
    >
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label={dismissLabel}
          className={DISMISS_BASE}
        >
          ×
        </button>
      )}
      <div className={hasIcon ? "flex items-start gap-3" : ""}>
        {hasIcon && (
          <span
            className="text-lg leading-none mt-0.5 shrink-0"
            aria-hidden="true"
          >
            {icon}
          </span>
        )}
        <div className="flex-1 min-w-0">
          {eyebrow && (
            <p className={`${EYEBROW_BASE} ${EYEBROW_CLASSES[variant]}`}>
              {eyebrow}
            </p>
          )}
          {heading && (
            <div className={`${HEADING_BASE} ${HEADING_TONE[variant]}`}>
              {heading}
            </div>
          )}
          {children && (
            <div className="text-sm text-muted-foreground leading-relaxed space-y-3">
              {children}
            </div>
          )}
          {cta && <div className="mt-3">{cta}</div>}
        </div>
      </div>
    </section>
  );
}

/**
 * VoiceQuote — the viewer's own words as hero element. Warm italic
 * with a gold left-border, theme-aware so it reads correctly against
 * both dark and light panel surfaces.
 */
interface VoiceQuoteProps {
  children: ReactNode;
  attribution?: ReactNode;
}

export function VoiceQuote({ children, attribution }: VoiceQuoteProps) {
  return (
    <blockquote
      className={
        "text-[15px] md:text-base italic " +
        "text-foreground/95 " +
        "border-l-2 border-[hsl(var(--primary)/0.6)] " +
        "pl-3.5 pr-1 leading-relaxed"
      }
    >
      <span>“{children}…”</span>
      {attribution && (
        <footer className="mt-1.5 text-xs not-italic text-muted-foreground">
          {attribution}
        </footer>
      )}
    </blockquote>
  );
}

/**
 * Panel-tone CTA link. Tone matches panel variant by default.
 */
interface PanelLinkProps {
  href: string;
  tone?: "warm" | "cool";
  children: ReactNode;
  external?: boolean;
}

export function PanelLink({
  href,
  tone = "warm",
  children,
  external = false,
}: PanelLinkProps) {
  const color =
    tone === "warm"
      ? "text-[hsl(var(--primary))] hover:opacity-80"
      : "text-[hsl(var(--chart-2))] hover:opacity-80";
  const externalProps = external
    ? { target: "_blank" as const, rel: "noopener noreferrer" as const }
    : {};
  return (
    <a
      href={href}
      {...externalProps}
      className={`inline-flex items-center gap-1 text-sm font-medium ${color}`}
    >
      {children}
    </a>
  );
}
