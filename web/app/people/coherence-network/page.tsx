import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getCoherenceNetworkContent } from "@/content/people/coherence-network";

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getCoherenceNetworkContent(lang).metadata;
}

export default async function CoherenceNetworkProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getCoherenceNetworkContent(lang);
  return (
    <PersonProfileTemplate
      content={content}
      lang={lang}
      graphSlug="coherence-network"
    />
  );
}
