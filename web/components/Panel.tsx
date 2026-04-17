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
 * Panel reduces the surface to four variants × four slots:
 *
 *   Variants (tone):
 *     • "warm"      — amber-on-stone, used for the viewer's own
 *                     moments (morning greeting, their contribution
 *                     reflected). The hero.
 *     • "cool"      — teal-on-stone, used for the organism's own
 *                     moments (invitations, breath, kin activity).
 *     • "neutral"   — stone-only, used for quieter content.
 *     • "empty"     — same surface as neutral but dimmer, used for
 *                     empty states that want to recede.
 *
 *   Slots:
 *     • eyebrow     — small uppercase tracking-wide caption (time of
 *                     day, section label).
 *     • heading     — near-white body in a readable size (the main
 *                     sentence addressing the viewer).
 *     • body        — the content itself — children allows any JSX
 *                     (paragraphs, quotes, lists, forms).
 *     • cta         — an amber-tinted link or button at the foot.
 *
 *   Other props:
 *     • icon        — optional emoji or small element at the left,
 *                     vertically aligned to the heading's optical
 *                     center (uses a flex row with items-start + mt-0.5
 *                     trim — standard across every panel).
 *     • onDismiss   — renders the × in the top-right at a consistent
 *                     position, size, and hover affordance.
 *
 * Every shared value (radius, padding, border color, gradient stops,
 * eyebrow scale, heading scale, icon size, dismiss size) is defined
 * once below. Future consistency improvements happen in one place.
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
// Changing a token here changes every panel everywhere; that is the
// point of the primitive.
const PANEL_BASE =
  "relative max-w-3xl mx-3 sm:mx-auto rounded-2xl px-5 py-4 " +
  "shadow-[0_1px_0_0_rgba(255,255,255,0.02)_inset]";

const VARIANT_CLASSES: Record<PanelVariant, string> = {
  warm:
    "border border-amber-600/20 " +
    "bg-gradient-to-br from-stone-900/95 via-stone-900/90 to-amber-950/25",
  cool:
    "border border-teal-600/25 " +
    "bg-gradient-to-br from-stone-900/95 via-stone-900/90 to-teal-950/30",
  neutral:
    "border border-stone-700/40 " +
    "bg-gradient-to-br from-stone-900/95 via-stone-900/90 to-stone-900/80",
  empty:
    "border border-stone-800/60 " +
    "bg-gradient-to-br from-stone-900/70 via-stone-900/60 to-stone-900/50",
};

const EYEBROW_CLASSES: Record<PanelVariant, string> = {
  warm: "text-amber-400",
  cool: "text-teal-300",
  neutral: "text-stone-400",
  empty: "text-stone-500",
};

const EYEBROW_BASE =
  "text-[11px] uppercase tracking-[0.18em] font-medium mb-1.5";

const HEADING_BASE =
  "text-base md:text-lg font-light leading-snug mb-2";

const HEADING_TONE: Record<PanelVariant, string> = {
  warm: "text-stone-50",
  cool: "text-stone-50",
  neutral: "text-stone-100",
  empty: "text-stone-300",
};

const DISMISS_BASE =
  "absolute top-2.5 right-2.5 w-7 h-7 rounded-full flex items-center " +
  "justify-center text-stone-500 hover:text-stone-200 " +
  "hover:bg-stone-800/40 transition-colors";

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
          // Icons carry a single standard sizing and an mt-0.5 trim so
          // the optical center sits with the heading's cap-height even
          // when the heading wraps to multiple lines.
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
          {children && <div className="text-sm text-stone-300 leading-relaxed space-y-3">{children}</div>}
          {cta && <div className="mt-3">{cta}</div>}
        </div>
      </div>
    </section>
  );
}

/**
 * A viewer-voice blockquote — when the panel's body needs to hold the
 * viewer's own words (or anyone's voice) as the hero element. Warm
 * amber italic with a gold left-border. Imported by MorningNudge +
 * SinceLastVisit + the blog-reaction-summary panels.
 */
interface VoiceQuoteProps {
  children: ReactNode;
  attribution?: ReactNode;
}

export function VoiceQuote({ children, attribution }: VoiceQuoteProps) {
  return (
    <blockquote
      className={
        "text-[15px] md:text-base italic text-amber-50/90 " +
        "border-l-2 border-amber-500/60 pl-3.5 pr-1 leading-relaxed"
      }
    >
      <span>“{children}…”</span>
      {attribution && (
        <footer className="mt-1.5 text-xs not-italic text-stone-400">
          {attribution}
        </footer>
      )}
    </blockquote>
  );
}

/**
 * A Panel-consistent CTA link. Matches the panel's tone by default.
 * Use for "Open your corner →", "See all voices →" style affordances.
 */
interface PanelLinkProps {
  href: string;
  tone?: "warm" | "cool";
  children: ReactNode;
  external?: boolean;
}

export function PanelLink({ href, tone = "warm", children, external = false }: PanelLinkProps) {
  const color =
    tone === "warm"
      ? "text-amber-300 hover:text-amber-200"
      : "text-teal-300 hover:text-teal-200";
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
