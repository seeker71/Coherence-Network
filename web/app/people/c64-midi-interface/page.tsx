import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getC64MidiInterfaceContent } from "@/content/people/c64-midi-interface";

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getC64MidiInterfaceContent(lang).metadata;
}

export default async function C64MidiInterfaceProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getC64MidiInterfaceContent(lang);
  return (
    <PersonProfileTemplate
      content={content}
      lang={lang}
      graphSlug="c64-midi-interface"
    />
  );
}
