import type { Metadata } from "next";
import { InfluencesRail } from "@/components/InfluencesRail";

/**
 * /me/influences — what shapes you, made into nodes.
 *
 * One input, one gesture: paste a URL or type a name. The resolver
 * fetches metadata, classifies the type (person, community, project,
 * work), and creates a claimable node with an inspired-by edge from
 * you to them. Re-pasting the same URL is a no-op (idempotent on
 * canonical URL); removing the link leaves the node alive for the
 * real person to claim.
 */

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "What shapes me — Coherence Network",
  description:
    "Name a person, a community, a place, a song. The system makes a place for them.",
};

export default function MeInfluencesPage() {
  return (
    <main className="mx-auto max-w-3xl px-4 sm:px-6 py-10">
      <InfluencesRail />
    </main>
  );
}
