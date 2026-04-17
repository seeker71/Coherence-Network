"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useT } from "@/components/MessagesProvider";

/**
 * FeedTabs — switch between the collective /feed and the personal /feed/you.
 * Renders above feed content. Tabs degrade gracefully: the "you" tab is
 * always visible, but the personal feed itself handles the empty-identity
 * state with an invitation to share first.
 */
export function FeedTabs() {
  const t = useT();
  const pathname = usePathname() || "";
  const isPersonal = pathname.startsWith("/feed/you");

  return (
    <nav className="flex items-center gap-1 mb-4 text-sm">
      <Link
        href="/feed"
        className={`px-3 py-1.5 rounded-full transition-colors ${
          !isPersonal
            ? "bg-amber-700/70 text-stone-950 font-medium"
            : "text-stone-400 hover:text-amber-300/90"
        }`}
      >
        {t("feed.tabCollective")}
      </Link>
      <Link
        href="/feed/you"
        className={`px-3 py-1.5 rounded-full transition-colors ${
          isPersonal
            ? "bg-teal-700/70 text-stone-950 font-medium"
            : "text-stone-400 hover:text-teal-300/90"
        }`}
      >
        {t("feed.tabPersonal")}
      </Link>
    </nav>
  );
}
