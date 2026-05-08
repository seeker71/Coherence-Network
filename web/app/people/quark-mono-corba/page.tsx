import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getQuarkMonoCorbaContent } from "@/content/people/quark-mono-corba";

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getQuarkMonoCorbaContent(lang).metadata;
}

export default async function QuarkMonoCorbaProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getQuarkMonoCorbaContent(lang);
  return (
    <PersonProfileTemplate
      content={content}
      lang={lang}
      graphSlug="quark-mono-corba"
    />
  );
}
