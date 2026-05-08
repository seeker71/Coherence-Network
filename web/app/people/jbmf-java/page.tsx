import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getJbmfJavaContent } from "@/content/people/jbmf-java";

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getJbmfJavaContent(lang).metadata;
}

export default async function JbmfJavaProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getJbmfJavaContent(lang);
  return (
    <PersonProfileTemplate
      content={content}
      lang={lang}
      graphSlug="jbmf-java"
    />
  );
}
