import { cookies } from "next/headers";

import { getApiBase } from "@/lib/api";
import { ActiveNavLink } from "./active_nav_link";
import {
  AttributedExternalLink,
  AttributedInternalLink,
} from "@/components/content/AttributedExternalLink";
import { ThemeToggle } from "./theme-toggle";
import { ModeSwitcher } from "./mode-switcher";
import { WorkspacePicker } from "./workspace-picker";
import { LocaleSwitcherCompact } from "./LocaleSwitcherCompact";
import { MeButton } from "./MeButton";
import { SecondaryLayerNav } from "./SecondaryLayerNav";
import { createTranslator } from "@/lib/i18n";
import { DEFAULT_LOCALE, isSupportedLocale, type LocaleCode } from "@/lib/locales";

type NavItemKey = {
  href: string;
  labelKey: string;
  isHeartbeat?: boolean;
};

// Primary layers — four entry points into the organism, named by
// what they carry rather than by page. Each one opens into a
// contextual secondary row (rendered by SecondaryLayerNav) with the
// pages that live inside that layer.
const PRIMARY_NAV: NavItemKey[] = [
  { href: "/vision", labelKey: "nav.layer.vision" },
  { href: "/presences", labelKey: "nav.layer.presences" },
  { href: "/ideas", labelKey: "nav.layer.work" },
  { href: "/resonance", labelKey: "nav.layer.pulse", isHeartbeat: true },
];

// Secondary surfaces — kept in "More" because a new visitor doesn't
// need them on the first surface. Trimmed to the five that a curious
// arrival might actually want: where to put resources (invest), what
// the body is holding (treasury), how to find anything (search), the
// breath log (blog), and the API for builders. The deeper internal
// surfaces (specs, substrate, automation, friction, identity) reach
// themselves through the pages that already use them.
const SECONDARY_NAV: NavItemKey[] = [
  { href: "/invest", labelKey: "nav.invest" },
  { href: "/treasury", labelKey: "nav.treasury" },
  { href: "/search", labelKey: "nav.search" },
  { href: "/blog", labelKey: "nav.blog" },
];

// One welcome doorway — collapsed from six because a new visitor
// shouldn't have to choose between Silence / One sheet / Come in /
// With us / Begin / Share to find the front door. The /come-in page
// itself carries the journey through those surfaces; the nav offers
// one threshold.
const DOORWAY_NAV: NavItemKey[] = [
  { href: "/come-in", labelKey: "nav.entry.comeIn" },
];

function HeartbeatIcon() {
  return (
    <span className="relative flex h-1.5 w-1.5" aria-hidden="true">
      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary/40" />
      <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-primary/80" />
    </span>
  );
}

export default async function SiteHeader() {
  const apiBase = getApiBase();
  const cookieStore = await cookies();
  const cookieLang = cookieStore.get("NEXT_LOCALE")?.value;
  const lang: LocaleCode = isSupportedLocale(cookieLang) ? cookieLang : DEFAULT_LOCALE;
  const t = createTranslator(lang);

  return (
    <header className="sticky top-0 z-50 border-b border-border/40 bg-background/85 backdrop-blur-md" role="banner">
      <div className="mx-auto max-w-6xl px-2 sm:px-4 md:px-8">
        <div className="flex h-14 items-center gap-1.5 sm:gap-2 md:gap-4 min-w-0">
          <AttributedInternalLink
            href="/"
            className="flex items-center gap-1.5 sm:gap-2 font-semibold tracking-tight text-foreground hover:text-primary transition-colors duration-300 shrink-0"
            aria-label={t("header.brandHome")}
          >
            <span className="relative flex h-2.5 w-2.5" aria-hidden="true" title={t("header.heartbeatTitle")}>
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary/40" />
              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-primary/80" />
            </span>
            <span className="hidden xs:inline sm:inline">Coherence</span>
            <span className="hidden md:inline">Network</span>
          </AttributedInternalLink>

          <nav className="hidden md:flex items-center gap-1 text-sm" aria-label={t("nav.primary")}>
            {PRIMARY_NAV.map((n) => (
              <ActiveNavLink
                key={n.href}
                href={n.href}
                label={t(n.labelKey)}
                isHeartbeat={n.isHeartbeat}
              />
            ))}
          </nav>

          <div className="flex-1" />

          {/* Workspace picker — Wave 2 multi-tenancy (desktop only;
              mobile keeps the header thumb-zone clear) */}
          <div className="hidden md:block">
            <WorkspacePicker />
          </div>

          {/* Locale switcher — always reachable, always visible.
              Size tuned so four letters + container fit at 390px. */}
          <LocaleSwitcherCompact
            ariaLabel={t("locale.switcherLabel")}
            size="xs"
            className="shrink-0"
          />

          {/* Mode switcher — expert / simple (desktop only) */}
          <div className="hidden md:block">
            <ModeSwitcher />
          </div>

          {/* Theme toggle — Spec 165 */}
          <ThemeToggle />

          {/* Me — the signed-in contributor's doorway to their own surfaces */}
          <MeButton />

          {/* Desktop "More" dropdown — secondary pages */}
          <details className="relative hidden md:block group">
            <summary
              className="list-none cursor-pointer rounded-lg border border-border/50 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:border-border transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1"
              aria-label={t("nav.openMore")}
              role="button"
            >
              {t("header.more")}
            </summary>
            <div className="absolute right-0 mt-2 w-72 rounded-xl border border-border/50 bg-popover/95 backdrop-blur-md p-4 shadow-xl">
              <div className="space-y-3">
                <div className="space-y-2">
                  <p className="text-[11px] font-medium uppercase tracking-wider text-amber-500/90">{t("nav.entry.groupLabel")}</p>
                  <div className="flex flex-wrap gap-1.5">
                    {DOORWAY_NAV.map((n) => (
                      <AttributedInternalLink
                        key={n.href}
                        href={n.href}
                        className="rounded-lg border border-amber-500/30 px-2.5 py-1 text-sm text-amber-300/90 hover:text-amber-200 hover:bg-amber-500/10 hover:border-amber-500/60 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-ring"
                      >
                        {t(n.labelKey)}
                      </AttributedInternalLink>
                    ))}
                  </div>
                </div>
                <div className="border-t border-border/30" />
                <div className="space-y-2">
                  <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground/80">{t("nav.explore")}</p>
                  <div className="flex flex-wrap gap-1.5">
                    {SECONDARY_NAV.map((n) => (
                      <AttributedInternalLink
                        key={n.href}
                        href={n.href}
                        className="rounded-lg border border-border/30 px-2.5 py-1 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 hover:border-border/60 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-ring"
                      >
                        {t(n.labelKey)}
                      </AttributedInternalLink>
                    ))}
                    <AttributedExternalLink
                      href={`${apiBase}/docs`}
                      entityId="api-docs"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="rounded-lg border border-border/30 px-2.5 py-1 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 hover:border-border/60 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-ring"
                    >
                      {t("nav.apiDocs")}
                    </AttributedExternalLink>
                  </div>
                </div>
              </div>
            </div>
          </details>

          {/* Mobile menu */}
          <details className="md:hidden relative">
            <summary
              className="list-none cursor-pointer rounded-lg border border-border/50 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1"
              aria-label={t("header.toggleNav")}
              role="button"
            >
              {t("header.menu")}
            </summary>
            <nav
              className="absolute right-0 mt-2 w-56 max-h-[calc(100vh-6rem)] overflow-y-auto rounded-xl border border-border/50 bg-popover/95 backdrop-blur-md shadow-xl overscroll-contain"
              aria-label={t("nav.mobile")}
            >
              <div className="p-3 space-y-1">
                <div className="flex items-center justify-between px-2 py-1.5">
                  <span className="text-[11px] uppercase tracking-wider text-muted-foreground/80">
                    {t("locale.switcherLabel")}
                  </span>
                  <LocaleSwitcherCompact
                    ariaLabel={t("locale.switcherLabel")}
                    size="xs"
                  />
                </div>
                <div className="border-t border-border/30 my-2" />
                {PRIMARY_NAV.map((n) => (
                  <AttributedInternalLink
                    key={n.href}
                    href={n.href}
                    className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-ring ${
                      n.isHeartbeat
                        ? "text-primary/80 hover:text-primary hover:bg-accent/60"
                        : "hover:bg-accent/60"
                    }`}
                  >
                    {n.isHeartbeat && <HeartbeatIcon />}
                    {t(n.labelKey)}
                  </AttributedInternalLink>
                ))}
                <div className="border-t border-border/30 my-2" />
                <p className="px-3 pt-1 text-[11px] font-medium uppercase tracking-wider text-amber-500/90">{t("nav.entry.groupLabel")}</p>
                {DOORWAY_NAV.map((n) => (
                  <AttributedInternalLink
                    key={n.href}
                    href={n.href}
                    className="block rounded-lg px-3 py-2 text-sm text-amber-300/90 hover:text-amber-200 hover:bg-amber-500/10 transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-ring"
                  >
                    {t(n.labelKey)}
                  </AttributedInternalLink>
                ))}
                <div className="border-t border-border/30 my-2" />
                <p className="px-3 pt-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground/80">{t("header.more")}</p>
                {SECONDARY_NAV.map((n) => (
                  <AttributedInternalLink
                    key={n.href}
                    href={n.href}
                    className="block rounded-lg px-3 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-ring"
                  >
                    {t(n.labelKey)}
                  </AttributedInternalLink>
                ))}
                <AttributedExternalLink
                  href={`${apiBase}/docs`}
                  entityId="api-docs"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block rounded-lg px-3 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  {t("nav.apiDocs")}
                </AttributedExternalLink>
              </div>
            </nav>
          </details>
        </div>
      </div>
      {/* Secondary layer row — renders only when the visitor is on a
          page that belongs to a known layer (Vision / Presences /
          Work / Pulse). Shows the peer pages inside that layer. */}
      <SecondaryLayerNav />
    </header>
  );
}
