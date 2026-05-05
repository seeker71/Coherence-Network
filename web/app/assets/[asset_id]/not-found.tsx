import { cookies, headers } from "next/headers";
import Link from "next/link";

import { getApiBase } from "@/lib/api";
import { decodeEntities } from "@/lib/html-entities";
import { DEFAULT_LOCALE, isSupportedLocale, type LocaleCode } from "@/lib/locales";
import { createTranslator } from "@/lib/i18n";
import { AssetGlyph, assetTypeTone } from "@/app/_components/AssetGlyph";
import { assetTypeLabel } from "@/lib/asset-types";
import { LedgerNav } from "@/app/_components/LedgerNav";

type Asset = {
  id: string;
  type: string;
  description: string;
  total_cost: string;
  created_at?: string;
  image_url?: string | null;
  file_path?: string | null;
};

async function loadFeatured(): Promise<Asset[]> {
  const API = getApiBase();
  try {
    const res = await fetch(`${API}/api/assets?limit=12`, { cache: "no-store" });
    if (!res.ok) return [];
    const data = await res.json();
    const items = data?.items ?? (Array.isArray(data) ? data : []);
    return items as Asset[];
  } catch {
    return [];
  }
}

export default async function AssetNotFound() {
  const cookieLocale = (await cookies()).get("NEXT_LOCALE")?.value;
  const headerLang = (await headers()).get("accept-language")?.split(",")[0]?.split("-")[0];
  const candidate = cookieLocale || headerLang;
  const lang: LocaleCode = isSupportedLocale(candidate) ? candidate : DEFAULT_LOCALE;
  const t = createTranslator(lang);
  const featured = await loadFeatured();

  return (
    <main className="bg-stone-950 min-h-screen">
      <div className="mx-auto max-w-5xl px-4 sm:px-6 py-8 sm:py-12 space-y-6 sm:space-y-8">
        <div className="flex items-center gap-3 text-sm">
          <Link href="/assets" className="text-stone-400 hover:text-amber-300 transition-colors">
            {t("assets.detail.backToAssets")}
          </Link>
        </div>

        <LedgerNav />

        {/* The gentle hold */}
        <section className="rounded-2xl border border-amber-500/20 bg-gradient-to-br from-amber-500/5 via-amber-500/10 to-transparent p-6 sm:p-8 space-y-3">
          <p className="text-xs uppercase tracking-widest text-amber-300/90">{t("assets.notFound.eyebrow")}</p>
          <h1 className="text-2xl sm:text-4xl font-light tracking-tight text-stone-50">
            {t("assets.notFound.title")}
          </h1>
          <p className="max-w-2xl text-stone-300 leading-relaxed">
            {t("assets.notFound.body")}
          </p>
        </section>

        {/* Featured assets — direct invitation to keep exploring */}
        {featured.length > 0 && (
          <section className="space-y-3">
            <h2 className="text-sm uppercase tracking-[0.18em] text-stone-500">{t("assets.notFound.featuredHeading")}</h2>
            <ul className="grid gap-3 sm:grid-cols-2">
              {featured.slice(0, 8).map((a) => {
                const name = decodeEntities(a.description || a.type || t("assets.untitled"));
                const thumbSrc = a.file_path || a.image_url || null;
                const tone = assetTypeTone(a.type);
                return (
                  <li
                    key={a.id}
                    className={[
                      "group relative tone-card",
                      tone.glowClass,
                      "rounded-2xl border border-border/30 bg-gradient-to-br from-card/60 to-card/30 overflow-hidden hover:border-amber-400/30 hover:from-card/80 hover:to-card/40",
                    ].join(" ")}
                  >
                    <span
                      aria-hidden="true"
                      className={[
                        "absolute left-0 top-0 bottom-0 w-[3px] z-10",
                        tone.stripe,
                      ].join(" ")}
                    />
                    {thumbSrc && (
                      <Link
                        href={`/assets/${encodeURIComponent(a.id)}`}
                        className="block relative aspect-video w-full bg-stone-900/40 overflow-hidden"
                      >
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={thumbSrc}
                          alt={t("assets.thumbnailAlt", { description: name })}
                          loading="lazy"
                          className="absolute inset-0 w-full h-full object-cover transition-transform duration-500 group-hover:scale-[1.02]"
                        />
                      </Link>
                    )}
                    <div className="flex items-start gap-3 sm:gap-4 p-4 sm:p-5">
                      <AssetGlyph type={a.type} className="flex-shrink-0" />
                      <div className="flex-1 min-w-0 space-y-2">
                        <Link
                          href={`/assets/${encodeURIComponent(a.id)}`}
                          className="block font-medium text-stone-100 hover:text-amber-200 transition-colors leading-snug break-words"
                        >
                          {name}
                        </Link>
                        <span className="inline-flex items-center rounded-full border border-border/30 bg-card/40 px-2 py-0.5 text-[11px] text-stone-400">
                          {assetTypeLabel(t, a.type)}
                        </span>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          </section>
        )}

        {/* Other doors */}
        <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 sm:p-6 space-y-3">
          <p className="text-sm text-stone-300">{t("assets.notFound.otherDoorsLabel")}</p>
          <div className="flex flex-wrap gap-3">
            <Link
              href="/assets"
              className="inline-flex items-center rounded-full border border-amber-500/40 bg-amber-500/10 px-5 py-2 text-sm text-amber-200 hover:bg-amber-500/20 transition-colors"
            >
              {t("assets.notFound.ctaBrowseAssets")}
            </Link>
            <Link
              href="/contributions"
              className="inline-flex items-center rounded-full border border-border/40 px-5 py-2 text-sm text-stone-300 hover:border-amber-400/30 hover:text-amber-200 transition-colors"
            >
              {t("assets.notFound.ctaContributions")}
            </Link>
            <Link
              href="/contributors"
              className="inline-flex items-center rounded-full border border-border/40 px-5 py-2 text-sm text-stone-300 hover:border-amber-400/30 hover:text-amber-200 transition-colors"
            >
              {t("assets.notFound.ctaContributors")}
            </Link>
            <Link
              href="/"
              className="inline-flex items-center rounded-full border border-border/40 px-5 py-2 text-sm text-stone-300 hover:border-amber-400/30 hover:text-amber-200 transition-colors"
            >
              {t("assets.notFound.ctaHome")}
            </Link>
          </div>
        </section>
      </div>
    </main>
  );
}
