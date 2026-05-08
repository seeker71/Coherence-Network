import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getBmlLanguageContent } from "@/content/people/bml-language";

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getBmlLanguageContent(lang).metadata;
}

export default async function BmlLanguageProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getBmlLanguageContent(lang);
  return (
    <PersonProfileTemplate
      content={content}
      lang={lang}
      graphSlug="bml-language"
    />
  );
}
