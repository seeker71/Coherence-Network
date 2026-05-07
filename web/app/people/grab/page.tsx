import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getGrabContent } from "@/content/people/grab";

/**
 * /people/grab — a service-provider profile rendered in the network's
 * lens. Grab is currently a centralized super-app extracting margin
 * between sovereigns who could meet directly. This page imagines
 * what its work would look like inside the network — same matching
 * function, no parasite layer.
 *
 * Thin locale-router wrapper. Rich content lives at
 * `web/content/people/grab/{locale}.tsx`; chrome strings come from
 * `web/messages/{locale}.json` via the shared template.
 *
 * Hero strategy: thematic CSS gradient — no scraped logo (would imply
 * partnership), no personal photo (this is a corporate brand, not a
 * person). The gradient bridges --primary (warm gold) and --chart-2
 * (teal) over a deep base, carrying the warm/cool tension the body of
 * the page already lives in: extraction layer dissolving into a
 * cooperative routing flow.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getGrabContent(lang).metadata;
}

export default async function GrabProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getGrabContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} graphSlug="grab" />;
}
