"use client";

/**
 * TemplateInfluenceWeb — surface the spectrum web + refine doorway
 * on hand-built /people/{slug} pages.
 *
 * Hand-built pages render rich curated content; this component
 * carries the live data layer alongside it: every relationship
 * edge from the graph node, painted with its family's spectrum
 * color, plus the doorway any visitor uses to refine the data.
 * Both surfaces stay in sync with the graph automatically — the
 * curated text updates take a code change; the data here updates
 * the moment a visitor saves a refinement.
 */

import { useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";
import { InfluenceWeb } from "@/components/presence/InfluenceWeb";
import { RefineDoorway } from "@/components/presence/RefineDoorway";
import type { PresenceIdentity } from "@/components/presence/PresencePage";

type GraphNode = {
  id: string;
  type: string;
  name?: string;
  slug?: string | null;
  presences?: { provider: string; url: string }[];
  claimed?: boolean;
};

export function TemplateInfluenceWeb({ graphSlug }: { graphSlug: string }) {
  const [node, setNode] = useState<GraphNode | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(
          `${getApiBase()}/api/graph/nodes/${encodeURIComponent(graphSlug)}`,
        );
        if (r.ok) setNode(await r.json());
      } catch {
        // page still renders — the data layer is just absent
      } finally {
        setLoaded(true);
      }
    })();
  }, [graphSlug]);

  if (!loaded || !node) return null;

  // Build a minimal PresenceIdentity for RefineDoorway. The fields
  // it actually reads are id, slug, name, claimed.
  const identity: PresenceIdentity = {
    id: node.id,
    slug: node.slug ?? null,
    name: node.name || node.id,
    category: node.type,
    canonical_url: "",
    provider: "",
    image_url: null,
    claimed: node.claimed,
    presences: [],
    creations: [],
  };

  return (
    <div className="space-y-10">
      <InfluenceWeb
        presenceId={node.id}
        externalPresences={node.presences || []}
      />
      <RefineDoorway identity={identity} />
    </div>
  );
}
