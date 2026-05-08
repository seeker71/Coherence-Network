import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getQuarkVirtualDomContent } from "@/content/people/quark-virtual-dom";

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getQuarkVirtualDomContent(lang).metadata;
}

export default async function QuarkVirtualDomProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getQuarkVirtualDomContent(lang);
  return (
    <PersonProfileTemplate
      content={content}
      lang={lang}
      graphSlug="quark-virtual-dom"
    />
  );
}
