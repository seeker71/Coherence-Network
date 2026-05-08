import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getMindtouchWikiInABoxContent } from "@/content/people/mindtouch-wiki-in-a-box";

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getMindtouchWikiInABoxContent(lang).metadata;
}

export default async function MindtouchWikiInABoxProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getMindtouchWikiInABoxContent(lang);
  return (
    <PersonProfileTemplate
      content={content}
      lang={lang}
      graphSlug="mindtouch-wiki-in-a-box"
    />
  );
}
