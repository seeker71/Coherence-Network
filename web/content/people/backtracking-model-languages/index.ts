import type { LocaleCode } from "@/lib/locales";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";
import en from "./en";
import de from "./de";
import es from "./es";
import id from "./id";

export function getBacktrackingModelLanguagesContent(lang: LocaleCode): PersonProfileContent {
  if (lang === "de") return de;
  if (lang === "es") return es;
  if (lang === "id") return id;
  return en;
}
