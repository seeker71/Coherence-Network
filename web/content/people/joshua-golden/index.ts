import type { LocaleCode } from "@/lib/locales";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";
import en from "./en";
import de from "./de";
import es from "./es";
import id from "./id";

const BUNDLES: Record<LocaleCode, PersonProfileContent> = { en, de, es, id };

export function getJoshuaGoldenContent(
  lang: LocaleCode,
): PersonProfileContent {
  return BUNDLES[lang] ?? BUNDLES.en;
}
