"use client";

import { useReadPing } from "@/hooks/useViewTracking";

export function IdeaReadPing({ ideaId }: { ideaId: string }) {
  useReadPing({
    assetId: ideaId,
    entityType: "idea",
    entityId: ideaId,
    sourcePage: `/ideas/${ideaId}`,
  });
  return null;
}
