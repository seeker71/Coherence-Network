import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getAmandaWalshContent } from "@/content/people/amanda-walsh";

/**
 * /people/amanda-walsh — founder of Astrology Hub.
 *
 * The Inspired Evolution conversation with Amrit Sandhu (2026)
 * carried four teachings into this body's vocabulary:
 * tend-the-flame, dance-card-and-sovereign-response, ground-harder
 * -when-the-field-quickens, and Zach Bush's numbness-has-its-own-pain.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getAmandaWalshContent(lang).metadata;
}

export default async function AmandaWalshProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getAmandaWalshContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="amanda-walsh" />;
}
