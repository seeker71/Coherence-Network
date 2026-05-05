"use client";

import { usePathname } from "next/navigation";

import { EditablePageMarkdown } from "@/components/content/EditablePageContent";
import { attributionTargetFromHref } from "@/lib/attribution-target";

const ROUTES_WITH_INLINE_EDITABLE_CONTENT = new Set([
  "come-in",
  "contribute",
  "ideas",
  "invest",
  "nodes",
  "pipeline",
  "resonance",
  "silence",
  "vision",
  "with-us",
]);

export function RouteEditablePageContent() {
  const pathname = usePathname() || "/";
  const target = attributionTargetFromHref(pathname);
  if (target?.entityType !== "page") return null;
  if (ROUTES_WITH_INLINE_EDITABLE_CONTENT.has(target.entityId)) return null;

  return (
    <EditablePageMarkdown
      pageId={target.entityId}
      containerClassName="px-4 sm:px-6 lg:px-8 py-10 mx-auto max-w-3xl"
      className="space-y-4 text-sm text-muted-foreground leading-relaxed"
    />
  );
}
