"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useT } from "@/components/MessagesProvider";

/**
 * MobileBottomNav — thumb-zone nav for phones.
 *
 * Hidden on surfaces where the page owns its own bottom UI (meeting
 * gestures, propose form submit, explore advance button). Visible as a
 * light shelf with the organism's five primary verbs everywhere else.
 *
 * The five verbs map to the dialogue substrate we actually shipped:
 * Here (current attention), Feed (the felt pulse), Meet (a quick door
 * to the first concept), Propose (offer something), Me (your corner).
 */

const BOTTOM_NAV = [
  { href: "/here", labelKey: "bottomNav.here", icon: "🌿" },
  { href: "/feed", labelKey: "bottomNav.feed", icon: "🔔" },
  { href: "/vision", labelKey: "bottomNav.vision", icon: "✨" },
  { href: "/propose", labelKey: "bottomNav.propose", icon: "➕" },
  { href: "/feed/you", labelKey: "bottomNav.you", icon: "👤" },
];

// Surfaces where the page draws its own lower-fold controls and the
// bottom nav would collide with them. The nav simply disappears; scroll
// still works and the header still carries the "Me" door.
const HIDDEN_ON_PREFIXES = [
  "/meet/",
  "/explore/",
  "/propose",
];

export function MobileBottomNav() {
  const pathname = usePathname() || "";
  const t = useT();

  const hidden = HIDDEN_ON_PREFIXES.some((p) => pathname.startsWith(p));
  if (hidden) return null;

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-40 md:hidden border-t border-border/40 bg-background/95 backdrop-blur-md safe-area-bottom max-w-full overflow-x-hidden"
      aria-label={t("nav.mobile")}
    >
      <div className="flex h-16 items-center justify-around px-2">
        {BOTTOM_NAV.map((item) => {
          const isActive =
            pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              className={[
                "flex flex-col items-center justify-center gap-0.5 rounded-xl px-2 py-2 text-[10px] transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-ring min-w-0",
                isActive
                  ? "text-primary font-medium"
                  : "text-muted-foreground hover:text-foreground",
              ].join(" ")}
              aria-current={isActive ? "page" : undefined}
            >
              <span className="text-base leading-none" aria-hidden="true">{item.icon}</span>
              <span className="truncate max-w-full">{t(item.labelKey)}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
