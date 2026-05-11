import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getSacredSongCircleContent } from "@/content/people/sacred-song-circle";

/**
 * /people/sacred-song-circle — international kirtan teacher network
 * tending one shared website. Where Vasudev Baba's bio lives.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getSacredSongCircleContent(lang).metadata;
}

export default async function SacredSongCircleProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getSacredSongCircleContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="sacred-song-circle" />;
}
