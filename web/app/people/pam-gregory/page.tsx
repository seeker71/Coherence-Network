import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getPamGregoryContent } from "@/content/people/pam-gregory";

/**
 * /people/pam-gregory — British astrologer with 45+ years of practice.
 *
 * The May 2026 Scorpio full-moon forecast deposited the plan-to-be-
 * proud teaching, the Pluto-in-Aquarius power-to-the-people frame,
 * and the observe-at-distance-compassion register into this body's
 * 2026 navigation vocabulary.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getPamGregoryContent(lang).metadata;
}

export default async function PamGregoryProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getPamGregoryContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="pam-gregory" />;
}
