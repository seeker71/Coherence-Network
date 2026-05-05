import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getAlyConstantineContent } from "@/content/people/aly-constantine";

/**
 * /people/aly-constantine — co-host of Boulder Ecstatic Dance.
 *
 * Thin locale-router wrapper. Rich content lives at
 * `web/content/people/aly-constantine/{locale}.tsx`; chrome strings come
 * from `web/messages/{locale}.json` via the shared template.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getAlyConstantineContent(lang).metadata;
}

export default async function AlyConstantineProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getAlyConstantineContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} />;
}
