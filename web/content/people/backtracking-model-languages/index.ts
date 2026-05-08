import type { LocaleCode } from "@/lib/locales";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";
import en from "./en";

export function getBacktrackingModelLanguagesContent(_lang: LocaleCode): PersonProfileContent {
  return en;
}
