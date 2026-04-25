"use client";

/**
 * LocaleSwitcherCompact — the smallest possible language toggle for the
 * site header (desktop + mobile menu). Four letters, no caption, no
 * pending/stale chrome. Clicking sets the NEXT_LOCALE cookie and pushes
 * a route with ?lang=<code> so server components re-render in the new
 * language on the very next navigation.
 */

import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { useCallback } from "react";
import { LOCALES, DEFAULT_LOCALE, type LocaleCode } from "@/lib/locales";
import { useLocale } from "@/components/MessagesProvider";

interface Props {
  ariaLabel?: string;
  className?: string;
  size?: "sm" | "xs";
}

export function LocaleSwitcherCompact({
  ariaLabel,
  className = "",
  size = "sm",
}: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const currentLang = useLocale();

  const setLang = useCallback(
    (code: LocaleCode) => {
      const params = new URLSearchParams(searchParams?.toString() ?? "");
      if (code === DEFAULT_LOCALE) {
        params.delete("lang");
      } else {
        params.set("lang", code);
      }
      const qs = params.toString();
      const next = qs ? `${pathname}?${qs}` : pathname || "/";
      document.cookie = `NEXT_LOCALE=${code}; path=/; max-age=${60 * 60 * 24 * 365}`;
      router.push(next);
      router.refresh();
    },
    [router, pathname, searchParams],
  );

  const padding = size === "xs" ? "px-1.5 py-0.5 text-[10px]" : "px-2 py-1 text-xs";

  return (
    <div
      role="group"
      aria-label={ariaLabel}
      className={`inline-flex items-center gap-0.5 rounded-lg border border-border/40 bg-background/60 p-0.5 ${className}`}
    >
      {LOCALES.map((loc) => {
        const isCurrent = loc.code === currentLang;
        return (
          <button
            key={loc.code}
            type="button"
            onClick={() => setLang(loc.code)}
            className={`${padding} rounded font-medium uppercase tracking-wider transition-colors ${
              isCurrent
                ? "bg-amber-500/20 text-amber-200"
                : "text-muted-foreground hover:text-foreground hover:bg-accent/40"
            }`}
            title={loc.nativeName}
            aria-pressed={isCurrent}
            aria-label={loc.nativeName}
          >
            {loc.code}
          </button>
        );
      })}
    </div>
  );
}
