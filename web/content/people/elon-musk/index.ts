import type { LocaleCode } from "@/lib/locales";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";
import en from "./en";

const BUNDLES: Record<LocaleCode, PersonProfileContent> = {
  en,
  de: en,
  es: en,
  id: en,
};

export function getElonMuskContent(lang: LocaleCode): PersonProfileContent {
  return BUNDLES[lang] ?? BUNDLES.en;
}
