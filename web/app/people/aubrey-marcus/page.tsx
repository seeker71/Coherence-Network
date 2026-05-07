import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getAubreyMarcusContent } from "@/content/people/aubrey-marcus";

/**
 * /people/aubrey-marcus — connecting tissue · long-form embodied/psychedelic room.
 *
 * Thin locale-router wrapper. Rich content lives at
 * `web/content/people/aubrey-marcus/{locale}.tsx`; chrome strings come from
 * `web/messages/{locale}.json` via the shared template.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getAubreyMarcusContent(lang).metadata;
}

export default async function AubreyMarcusProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getAubreyMarcusContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="aubrey-marcus" />;
}
