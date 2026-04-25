"use client";

import { useReadPing } from "@/hooks/useViewTracking";

/**
 * ReadPing — the felt moment of the body noticing a reader.
 *
 * The vision concept page server-renders its data, so the contributor's
 * identity headers never reach the read-tracking middleware. This small
 * client island fires a single ping on mount with the X-Contributor-Id
 * from localStorage, so the reader's trail becomes visible to them on
 * /me and to the organism in trending + discovery surfaces.
 */
export function ReadPing({ conceptId }: { conceptId: string }) {
  useReadPing({ conceptId, sourcePage: `/vision/${conceptId}` });
  return null;
}
