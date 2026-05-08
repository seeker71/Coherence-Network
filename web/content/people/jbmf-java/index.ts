import type { LocaleCode } from "@/lib/locales";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";
import en from "./en";

export function getJbmfJavaContent(_lang: LocaleCode): PersonProfileContent {
  return en;
}
