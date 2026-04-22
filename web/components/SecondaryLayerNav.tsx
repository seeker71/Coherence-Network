"use client";

/**
 * SecondaryLayerNav — contextual nav shown under the primary layer row.
 *
 * The primary nav carries four layer names (The Vision · The Presences
 * · The Work · The Pulse). This strip sits below and expands the
 * active layer into its component pages — so when you're on any
 * /people page you see People · Communities · Gatherings · Practices
 * · Works as peers, linking to filtered views of the directory.
 *
 * Hidden on layers that don't have a sub-nav (or on pages outside
 * any known layer).
 */

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useT } from "@/components/MessagesProvider";

type SubItem = { href: string; labelKey: string; kind?: string };

const LAYER_SUBNAV: Array<{
  prefix: string;
  items: SubItem[];
}> = [
  {
    prefix: "/people",
    items: [
      { href: "/people", labelKey: "nav.sub.all" },
      { href: "/people?kind=humans", labelKey: "nav.sub.people", kind: "humans" },
      { href: "/people?kind=communities", labelKey: "nav.sub.communities", kind: "communities" },
      { href: "/people?kind=scenes", labelKey: "nav.sub.scenes", kind: "scenes" },
      { href: "/people?kind=gatherings", labelKey: "nav.sub.gatherings", kind: "gatherings" },
      { href: "/people?kind=practices", labelKey: "nav.sub.practices", kind: "practices" },
      { href: "/people?kind=works", labelKey: "nav.sub.works", kind: "works" },
    ],
  },
  {
    prefix: "/ideas",
    items: [
      { href: "/ideas", labelKey: "nav.sub.ideas" },
      { href: "/contribute", labelKey: "nav.sub.contribute" },
      { href: "/pipeline", labelKey: "nav.sub.pipeline" },
      { href: "/tasks", labelKey: "nav.workCards" },
      { href: "/contributors", labelKey: "nav.sub.contributors" },
      { href: "/assets", labelKey: "nav.sub.assets" },
    ],
  },
  {
    prefix: "/resonance",
    items: [
      { href: "/resonance", labelKey: "nav.sub.resonance" },
      { href: "/nodes", labelKey: "nav.sub.nodes" },
      { href: "/vitality", labelKey: "nav.vitality" },
      { href: "/pulse", labelKey: "nav.pulse" },
    ],
  },
];

// Pages that live inside a layer but don't share its url prefix.
// /contributors + /assets are work-ledger views (who's tending,
// what's been built + what it cost) — both belong under The Work.
const LAYER_ALIASES: Record<string, string> = {
  "/contribute": "/ideas",
  "/pipeline": "/ideas",
  "/tasks": "/ideas",
  "/contributors": "/ideas",
  "/assets": "/ideas",
  "/nodes": "/resonance",
  "/vitality": "/resonance",
  "/pulse": "/resonance",
};

export function SecondaryLayerNav() {
  const t = useT();
  const pathname = usePathname() || "";
  const searchParams = useSearchParams();

  // Map current path to its layer prefix.
  let activePrefix: string | null = null;
  for (const [alias, target] of Object.entries(LAYER_ALIASES)) {
    if (pathname === alias || pathname.startsWith(alias + "/")) {
      activePrefix = target;
      break;
    }
  }
  if (!activePrefix) {
    for (const layer of LAYER_SUBNAV) {
      if (pathname === layer.prefix || pathname.startsWith(layer.prefix + "/")) {
        activePrefix = layer.prefix;
        break;
      }
    }
  }
  if (!activePrefix) return null;

  const layer = LAYER_SUBNAV.find((l) => l.prefix === activePrefix);
  if (!layer) return null;

  const currentKind = searchParams?.get("kind") || null;

  return (
    <div className="hidden md:block border-b border-border/30 bg-background/70">
      <div className="mx-auto max-w-6xl px-2 sm:px-4 md:px-8">
        <nav
          className="flex h-10 items-center gap-0.5 text-[13px] overflow-x-auto"
          aria-label={t("nav.secondary")}
          style={{ scrollbarWidth: "none" }}
        >
          {layer.items.map((item) => {
            // Active when the pathname matches AND the kind query param
            // matches (for /people sub-filters).
            const itemKind = item.kind || null;
            const itemPath = item.href.split("?")[0];
            const isActive = (() => {
              if (itemPath !== pathname) return false;
              if (layer.prefix === "/people") {
                return itemKind === currentKind;
              }
              return true;
            })();
            return (
              <Link
                key={item.href}
                href={item.href}
                className={[
                  "rounded-lg px-2.5 py-1 transition-colors focus:outline-none focus:ring-2 focus:ring-ring",
                  isActive
                    ? "text-primary font-medium bg-primary/10"
                    : "text-muted-foreground hover:text-foreground hover:bg-accent/40",
                ].join(" ")}
              >
                {t(item.labelKey)}
              </Link>
            );
          })}
        </nav>
      </div>
    </div>
  );
}
