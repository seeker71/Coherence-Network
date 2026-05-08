import type { Metadata } from "next";
import { resolveRequestLocale } from "@/lib/request-locale";
import { PersonProfileTemplate } from "@/components/people/PersonProfileTemplate";
import { getQuarkMultiUndoRedoContent } from "@/content/people/quark-multi-undo-redo";

export async function generateMetadata(): Promise<Metadata> {
  const lang = await resolveRequestLocale();
  return getQuarkMultiUndoRedoContent(lang).metadata;
}

export default async function QuarkMultiUndoRedoProfilePage() {
  const lang = await resolveRequestLocale();
  const content = getQuarkMultiUndoRedoContent(lang);
  return (
    <PersonProfileTemplate
      content={content}
      lang={lang}
      graphSlug="quark-multi-undo-redo"
    />
  );
}
