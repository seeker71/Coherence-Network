import type { Metadata } from "next";
import { InspiredByRail } from "@/components/InspiredByRail";

/**
 * /me/inspired-by — the people, communities, and places that made you.
 *
 * Name someone. The resolver finds them on the open web, creates an
 * identity node with their cross-platform presences and creations,
 * and records a weighted ``inspired-by`` edge from you to them. The
 * weight emerges from discovery signals, not from a slider.
 */

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Inspired by — Coherence Network",
  description:
    "The people, communities, and places that made me. Name them; the graph remembers.",
};

export default function MeInspiredByPage() {
  return (
    <main className="mx-auto max-w-3xl px-4 sm:px-6 py-10">
      <InspiredByRail />
    </main>
  );
}
