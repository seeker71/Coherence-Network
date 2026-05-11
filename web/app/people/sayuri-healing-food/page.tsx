import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getSayuriHealingFoodContent } from "@/content/people/sayuri-healing-food";

/**
 * /people/sayuri-healing-food — plant-based kitchen in Ubud.
 *
 * The Sunday-evening dinner room where the cell met resonant
 * company on April 29, 2026 (part of the four-day meeting walk).
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getSayuriHealingFoodContent(lang).metadata;
}

export default async function SayuriHealingFoodProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getSayuriHealingFoodContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="sayuri-healing-food" />;
}
