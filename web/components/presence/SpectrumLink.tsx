"use client";

/**
 * SpectrumLink — a relationship rendered with the color of its family.
 *
 * Every edge between two presences carries a frequency. The chip's
 * fill, border, and text are sampled from the edge's family color
 * (see `web/lib/edge-spectrum.ts`). The label above the chip names
 * the relationship verb ("resonates with", "inspired by"); the chip
 * itself names the other presence.
 *
 * On hover the chip brightens; on tap it walks the visitor to the
 * other presence. The colored line between two adjacent chips —
 * when rendered side-by-side in a row — reads as a small spectrum
 * arc, the band the relationship occupies in the field.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  edgeTypeLabel,
  familyForEdgeType,
  hsl,
  type EdgeFamily,
} from "@/lib/edge-spectrum";

type Props = {
  /** The canonical edge type (e.g., "resonates-with", "at-place"). */
  edgeType: string;
  /** href the chip walks the visitor to. */
  href: string;
  /** Display name of the other presence. */
  name: string;
  /** Optional thumbnail (square) for the other presence. */
  imageUrl?: string | null;
  /** When the relationship has a strength score [0..1], the chip
   *  brightens with it. Otherwise the chip uses the family's full
   *  saturation. */
  strength?: number | null;
  /** When true, the verb label is suppressed — useful in a list
   *  already grouped by edge type. */
  verbInline?: boolean;
};

export function SpectrumLink({
  edgeType,
  href,
  name,
  imageUrl,
  strength,
  verbInline = false,
}: Props) {
  const family = familyForEdgeType(edgeType);
  const tone = useFamilyTone(family);
  const fg = hsl(tone, "fg");
  const bg = hsl(tone, "bg");
  // Strength bows the chip's emphasis: low-strength edges sit quieter
  // so the eye finds the high-strength weave first.
  const opacity =
    typeof strength === "number" && Number.isFinite(strength)
      ? Math.max(0.55, Math.min(1, strength))
      : 0.95;

  return (
    <Link
      href={href}
      title={`${edgeTypeLabel(edgeType)} · ${name}`}
      className="group inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs transition-all hover:scale-[1.02] hover:shadow-sm"
      style={{
        background: bg,
        borderColor: `color-mix(in oklch, ${fg} 35%, transparent)`,
        color: fg,
        opacity,
      }}
    >
      {imageUrl ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={imageUrl}
          alt=""
          className="w-5 h-5 rounded-full object-cover"
          style={{ borderColor: fg, borderWidth: 1, borderStyle: "solid" }}
        />
      ) : (
        <span
          aria-hidden="true"
          className="w-2 h-2 rounded-full shrink-0"
          style={{ background: fg }}
        />
      )}
      <span className="truncate max-w-[12rem] font-medium">{name}</span>
      {!verbInline && (
        <span
          className="text-[10px] tracking-[0.05em] opacity-70 hidden sm:inline"
          style={{ color: fg }}
        >
          · {edgeTypeLabel(edgeType).toLowerCase()}
        </span>
      )}
    </Link>
  );
}

/**
 * Pick the light or dark tone based on the document's current mode.
 * Re-evaluates when the `light` class on `<html>` is toggled by the
 * theme switcher.
 */
function useFamilyTone(family: EdgeFamily) {
  const [isLight, setIsLight] = useState(false);
  useEffect(() => {
    const update = () =>
      setIsLight(document.documentElement.classList.contains("light"));
    update();
    const mo = new MutationObserver(update);
    mo.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    });
    return () => mo.disconnect();
  }, []);
  return isLight ? family.light : family.dark;
}
