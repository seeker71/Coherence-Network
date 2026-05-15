import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getPortalContent } from "@/content/people/portal";

/**
 * /people/portal — PORTAL (Partnership of Responsible Trippers Advocating
 * for Legalization), the Denver psychedelic-community initiative.
 *
 * Thin locale-router wrapper. Rich content lives at
 * `web/content/people/portal/{locale}.tsx`; chrome strings (breadcrumb,
 * edit-profile CTA, note eyebrow) come from `web/messages/{locale}.json`
 * via the shared template. See `web/components/people/PersonProfileTemplate.tsx`
 * for the rendering shape.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getPortalContent(lang).metadata;
}

export default async function PortalProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getPortalContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} />;
}
