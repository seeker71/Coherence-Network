import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getBmfGrammarContent } from "@/content/people/bmf-grammar";

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getBmfGrammarContent(lang).metadata;
}

export default async function BmfGrammarProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getBmfGrammarContent(lang);
  return (
    <PersonProfileTemplate
      content={content}
      lang={lang}
      graphSlug="bmf-grammar"
    />
  );
}
