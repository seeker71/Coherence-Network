import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getValiSoulSanctuaryContent } from "@/content/people/vali-soul-sanctuary";

/**
 * /people/vali-soul-sanctuary — the sanctuary that turned a
 * once-attended ceremonial floor into a regular practice.
 *
 * Thin locale-router wrapper. Rich content lives at
 * `web/content/people/vali-soul-sanctuary/{locale}.tsx`; chrome
 * strings (breadcrumb, edit-profile CTA, note eyebrow) come from
 * `web/messages/{locale}.json` via the shared template.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getValiSoulSanctuaryContent(lang).metadata;
}

export default async function ValiSoulSanctuaryPage() {
  const lang = await resolveRequestLocale();
  const content = getValiSoulSanctuaryContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="vali-soul-sanctuary" />;
}
