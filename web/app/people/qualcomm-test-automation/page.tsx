import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getQualcommTestAutomationContent } from "@/content/people/qualcomm-test-automation";

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getQualcommTestAutomationContent(lang).metadata;
}

export default async function QualcommTestAutomationProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getQualcommTestAutomationContent(lang);
  return (
    <PersonProfileTemplate
      content={content}
      lang={lang}
      graphSlug="qualcomm-test-automation"
    />
  );
}
