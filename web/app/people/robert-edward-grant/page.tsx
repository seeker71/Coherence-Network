import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getRobertEdwardGrantContent } from "@/content/people/robert-edward-grant";

/**
 * /people/robert-edward-grant — a welcome page for Robert Edward Grant,
 * polymath, sacred-mathematician, and shepherd of the ORION Architect
 * platform.
 *
 * Thin locale-router wrapper. Rich content lives at
 * `web/content/people/robert-edward-grant/{locale}.tsx`; chrome strings
 * (breadcrumb, edit-profile CTA, note eyebrow) come from
 * `web/messages/{locale}.json` via the shared template.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getRobertEdwardGrantContent(lang).metadata;
}

export default async function RobertEdwardGrantProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getRobertEdwardGrantContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} />;
}
