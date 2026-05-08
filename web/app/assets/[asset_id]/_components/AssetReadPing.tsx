"use client";

/**
 * AssetReadPing — leaves a witness trace whenever an asset detail
 * page is viewed. Composes useReadPing so the asset surface participates
 * in the same view-tracking + attention-attribution machinery the
 * concept and idea pages already use.
 *
 * Anonymous viewers contribute a session-fingerprinted view event;
 * graduated contributors are credited explicitly via X-Contributor-Id
 * so /me can reflect their own trail back to them.
 *
 * Returns null — the only side-effect is the network's awareness that
 * this asset has been seen.
 */

import { useReadPing } from "@/hooks/useViewTracking";

export function AssetReadPing({ assetId }: { assetId: string }) {
  useReadPing({
    assetId,
    entityType: "asset",
    entityId: assetId,
    sourcePage: `/assets/${assetId}`,
  });
  return null;
}
