import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getBacktrackingModelLanguagesContent } from "@/content/people/backtracking-model-languages";

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getBacktrackingModelLanguagesContent(lang).metadata;
}

export default async function BacktrackingModelLanguagesProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getBacktrackingModelLanguagesContent(lang);
  return (
    <PersonProfileTemplate
      content={content}
      lang={lang}
      graphSlug="backtracking-model-languages"
    />
  );
}
