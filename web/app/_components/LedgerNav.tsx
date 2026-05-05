"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useT } from "@/components/MessagesProvider";

// Shared sub-nav for the three ledger surfaces — Contributors,
// Contributions, Assets. Each page gets the same chips, in the same
// order, with the same hrefs, so an explorer never wonders whether
// they are on the right cousin.

type Tab = {
  href: "/contributors" | "/contributions" | "/assets";
  labelKey: string;
  hintKey: string;
};

const TABS: Tab[] = [
  { href: "/contributors", labelKey: "ledger.tabs.contributors", hintKey: "ledger.tabs.contributorsHint" },
  { href: "/contributions", labelKey: "ledger.tabs.contributions", hintKey: "ledger.tabs.contributionsHint" },
  { href: "/assets", labelKey: "ledger.tabs.assets", hintKey: "ledger.tabs.assetsHint" },
];

export function LedgerNav() {
  const t = useT();
  const pathname = usePathname();
  return (
    <nav
      aria-label={t("ledger.tabsAriaLabel")}
      className="-mx-4 sm:mx-0 px-4 sm:px-0 overflow-x-auto"
    >
      <ul className="flex items-center gap-2 sm:gap-3 min-w-max sm:min-w-0">
        {TABS.map((tab) => {
          const isActive =
            pathname === tab.href || pathname.startsWith(`${tab.href}/`);
          return (
            <li key={tab.href}>
              <Link
                href={tab.href}
                aria-current={isActive ? "page" : undefined}
                className={[
                  "group flex items-center gap-2 rounded-full border px-4 py-2 text-sm transition-all duration-300",
                  isActive
                    ? "border-amber-400/50 bg-amber-500/10 text-amber-200"
                    : "border-border/30 bg-card/30 text-stone-300 hover:border-amber-400/30 hover:bg-amber-500/5 hover:text-amber-200",
                ].join(" ")}
              >
                <span className="font-medium">{t(tab.labelKey)}</span>
                <span
                  className={[
                    "text-[10px] uppercase tracking-[0.18em] transition-colors",
                    isActive
                      ? "text-amber-300/70"
                      : "text-stone-500 group-hover:text-amber-300/60",
                  ].join(" ")}
                >
                  {t(tab.hintKey)}
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
