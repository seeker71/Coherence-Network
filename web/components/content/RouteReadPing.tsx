"use client";

import { usePathname } from "next/navigation";

import { useReadPing } from "@/hooks/useViewTracking";
import { attributionTargetFromHref } from "@/lib/attribution-target";

export function RouteReadPing() {
  const pathname = usePathname() || "/";
  const target = attributionTargetFromHref(pathname);

  useReadPing({
    assetId: target?.assetId,
    conceptId: target?.conceptId || undefined,
    entityType: target?.entityType,
    entityId: target?.entityId,
    sourcePage: pathname,
  });

  return null;
}
