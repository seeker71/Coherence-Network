import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getBmcpuVmContent } from "@/content/people/bmcpu-vm";

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getBmcpuVmContent(lang).metadata;
}

export default async function BmcpuVmProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getBmcpuVmContent(lang);
  return (
    <PersonProfileTemplate
      content={content}
      lang={lang}
      graphSlug="bmcpu-vm"
    />
  );
}
