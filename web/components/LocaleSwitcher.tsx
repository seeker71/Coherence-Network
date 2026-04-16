"use client";

import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { useCallback } from "react";
import { LOCALES, DEFAULT_LOCALE, type LocaleCode, type LanguageMeta } from "@/lib/locales";
import { useT } from "@/components/MessagesProvider";

type Props = {
  currentLang: LocaleCode;
  meta?: LanguageMeta | null;
};

export function LocaleSwitcher({ currentLang, meta }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const t = useT();

  const setLang = useCallback(
    (code: LocaleCode) => {
      const params = new URLSearchParams(searchParams?.toString() ?? "");
      if (code === DEFAULT_LOCALE) {
        params.delete("lang");
      } else {
        params.set("lang", code);
      }
      const qs = params.toString();
      const next = qs ? `${pathname}?${qs}` : (pathname || "/");
      document.cookie = `NEXT_LOCALE=${code}; path=/; max-age=${60 * 60 * 24 * 365}`;
      router.push(next);
      router.refresh();
    },
    [router, pathname, searchParams],
  );

  const available = new Set<string>(meta?.available_langs ?? [currentLang]);

  return (
    <div className="flex items-center gap-2 text-xs text-stone-400">
      <span className="text-stone-600">{t("locale.switcherLabel")}</span>
      <div className="flex gap-1">
        {LOCALES.map((loc) => {
          const isCurrent = loc.code === currentLang;
          const hasView = available.has(loc.code);
          return (
            <button
              key={loc.code}
              type="button"
              onClick={() => setLang(loc.code)}
              className={[
                "px-2 py-1 rounded border transition-colors",
                isCurrent
                  ? "border-amber-500/60 text-amber-300 bg-amber-500/5"
                  : hasView
                    ? "border-stone-700 text-stone-300 hover:border-amber-500/40 hover:text-amber-200"
                    : "border-stone-800 text-stone-500 hover:border-stone-600 hover:text-stone-300",
              ].join(" ")}
              title={hasView ? loc.nativeName : `${loc.nativeName} — ${t("locale.noViewYet")}`}
            >
              {loc.code.toUpperCase()}
            </button>
          );
        })}
      </div>
      {meta?.pending && (
        <span className="text-amber-400/80 italic">· {t("vision.pendingTranslation")}</span>
      )}
      {meta?.stale && !meta.pending && (
        <span className="text-amber-400/80 italic">· {t("vision.staleAwaitingReattunement")}</span>
      )}
    </div>
  );
}
