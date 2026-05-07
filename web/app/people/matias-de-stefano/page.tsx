import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getMatiasDeStefanoContent } from "@/content/people/matias-de-stefano";

/**
 * /people/matias-de-stefano — a welcome page for Matías De Stefano,
 * Argentine spiritual teacher and "memory keeper" whose work on
 * Akashic records, ancient civilizations, planetary lineage, and
 * the nine-dimensional consciousness model has been in this body's
 * awareness through long-form conversations with Robert Edward
 * Grant, Aubrey Marcus, and Gaia's Initiation series.
 *
 * Thin locale-router wrapper. Rich content lives at
 * `web/content/people/matias-de-stefano/{locale}.tsx`; chrome strings
 * (breadcrumb, edit-profile CTA, note eyebrow) come from
 * `web/messages/{locale}.json` via the shared template. See
 * `web/components/people/PersonProfileTemplate.tsx` for the rendering shape.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getMatiasDeStefanoContent(lang).metadata;
}

export default async function MatiasDeStefanoProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getMatiasDeStefanoContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="matias-de-stefano" />;
}
