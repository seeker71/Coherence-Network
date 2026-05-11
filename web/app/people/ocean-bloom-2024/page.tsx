import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getOceanBloom2024Content } from "@/content/people/ocean-bloom-2024";

/**
 * /people/ocean-bloom-2024 — the 2024 conscious-music gathering in
 * Downtown Boulder that wove Poranguí, Liquid Bloom, Samuel J, Shawn
 * Heinrichs, and Bloomurian into one configuration.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getOceanBloom2024Content(lang).metadata;
}

export default async function OceanBloom2024ProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getOceanBloom2024Content(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="ocean-bloom-2024" />;
}
