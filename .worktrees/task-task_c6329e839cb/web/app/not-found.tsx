import Link from "next/link";
import { cookies } from "next/headers";
import { createTranslator } from "@/lib/i18n";
import { DEFAULT_LOCALE, isSupportedLocale, type LocaleCode } from "@/lib/locales";

export default async function NotFound() {
  const cookieStore = await cookies();
  const cookieLang = cookieStore.get("NEXT_LOCALE")?.value;
  const lang: LocaleCode = isSupportedLocale(cookieLang) ? cookieLang : DEFAULT_LOCALE;
  const t = createTranslator(lang);

  return (
    <main className="mx-auto max-w-2xl px-4 py-24 text-center space-y-6">
      <div className="space-y-3">
        <p className="text-6xl font-light text-primary">404</p>
        <h1 className="text-2xl md:text-3xl font-light tracking-tight">
          {t("notFound.title")}
        </h1>
        <p className="text-muted-foreground leading-relaxed max-w-md mx-auto">
          {t("notFound.body")}
        </p>
      </div>
      <div className="flex flex-col sm:flex-row gap-3 justify-center">
        <Link
          href="/"
          className="rounded-xl bg-primary px-6 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
        >
          {t("notFound.goHome")}
        </Link>
        <Link
          href="/ideas"
          className="rounded-xl border border-border/30 px-6 py-2.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200"
        >
          {t("notFound.browseIdeas")}
        </Link>
      </div>
    </main>
  );
}
