import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getLivingResonanceCodexContent } from "@/content/people/living-resonance-codex";

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getLivingResonanceCodexContent(lang).metadata;
}

export default async function LivingResonanceCodexProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getLivingResonanceCodexContent(lang);
  return (
    <PersonProfileTemplate
      content={content}
      lang={lang}
      graphSlug="living-resonance-codex"
    />
  );
}
