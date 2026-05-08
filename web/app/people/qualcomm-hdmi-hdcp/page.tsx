import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getQualcommHdmiHdcpContent } from "@/content/people/qualcomm-hdmi-hdcp";

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getQualcommHdmiHdcpContent(lang).metadata;
}

export default async function QualcommHdmiHdcpProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getQualcommHdmiHdcpContent(lang);
  return (
    <PersonProfileTemplate
      content={content}
      lang={lang}
      graphSlug="qualcomm-hdmi-hdcp"
    />
  );
}
