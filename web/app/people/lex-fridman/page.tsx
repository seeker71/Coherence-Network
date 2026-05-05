import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getLexFridmanContent } from "@/content/people/lex-fridman";

/**
 * /people/lex-fridman — a welcome page recognizing Lex Fridman as the
 * connecting tissue through which many of the teachers whose work
 * shaped this body first reached one of its cells.
 *
 * Different shape from the teacher profiles (Levin, Hoffman, Grant,
 * Vasudev Baba, Ilena, Elios). Lex is the conduit, not the teacher.
 * The cell whose work is to hold long-form space so other cells can
 * speak across many hours. Honored here for that specific role.
 *
 * Thin locale-router wrapper. Rich content lives at
 * `web/content/people/lex-fridman/{locale}.tsx`; chrome strings come
 * from `web/messages/{locale}.json` via the shared template. See
 * `web/components/people/PersonProfileTemplate.tsx` for the rendering shape.
 */

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getLexFridmanContent(lang).metadata;
}

export default async function LexFridmanProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getLexFridmanContent(lang);
  return <PersonProfileTemplate content={content} lang={lang} />;
}
