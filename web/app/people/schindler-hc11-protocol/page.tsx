import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getSchindlerHc11ProtocolContent } from "@/content/people/schindler-hc11-protocol";

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getSchindlerHc11ProtocolContent(lang).metadata;
}

export default async function SchindlerHc11ProtocolProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getSchindlerHc11ProtocolContent(lang);
  return (
    <PersonProfileTemplate
      content={content}
      lang={lang}
      graphSlug="schindler-hc11-protocol"
    />
  );
}
