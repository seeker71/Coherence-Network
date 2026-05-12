import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getRudolfSteinerContent } from "@/content/people/rudolf-steiner";

/**
 * /people/rudolf-steiner — Austrian philosopher who founded Anthroposophy,
 * Waldorf education, biodynamic agriculture, and eurythmy.
 *
 * Honored here as the Central-European esoteric source of the
 * etheric-formative-forces frame this body reads alongside
 * Michael Levin's bioelectric pattern memory.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getRudolfSteinerContent(lang).metadata;
}

export default async function RudolfSteinerProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getRudolfSteinerContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="rudolf-steiner" />;
}
