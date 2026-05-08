import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getTrimbleGlueLayerContent } from "@/content/people/trimble-glue-layer";

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getTrimbleGlueLayerContent(lang).metadata;
}

export default async function TrimbleGlueLayerProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getTrimbleGlueLayerContent(lang);
  return (
    <PersonProfileTemplate
      content={content}
      lang={lang}
      graphSlug="trimble-glue-layer"
    />
  );
}
