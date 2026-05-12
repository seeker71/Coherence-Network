import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getYaimaContent } from "@/content/people/yaima";

/**
 * /people/yaima — Masaru Higasa + Pepper Proud, the elemental album arc.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getYaimaContent(lang).metadata;
}

export default async function YaimaProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getYaimaContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="yaima" />;
}
