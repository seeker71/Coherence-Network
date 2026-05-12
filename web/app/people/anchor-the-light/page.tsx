import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getAnchorTheLightContent } from "@/content/people/anchor-the-light";

/**
 * /people/anchor-the-light — the living spiritual path co-led by
 * Ubbe MacLean, Brigitte Mars, and Freya Aswynn. Trans-tradition
 * spiritual community: Norse Asatru, Reiki, psychotherapy, herbal
 * medicine, qi gong, sound healing, dance.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getAnchorTheLightContent(lang).metadata;
}

export default async function AnchorTheLightProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getAnchorTheLightContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="anchor-the-light" />;
}
