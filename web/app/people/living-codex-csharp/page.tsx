import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getLivingCodexCsharpContent } from "@/content/people/living-codex-csharp";

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getLivingCodexCsharpContent(lang).metadata;
}

export default async function LivingCodexCsharpProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getLivingCodexCsharpContent(lang);
  return (
    <PersonProfileTemplate
      content={content}
      lang={lang}
      graphSlug="living-codex-csharp"
    />
  );
}
