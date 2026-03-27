"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

/* ------------------------------------------------------------------ */
/*  Navigation groups: Explore, Build, Operate                        */
/* ------------------------------------------------------------------ */

interface NavItem {
  href: string;
  label: string;
}

interface NavGroup {
  title: string;
  /** "operate" group only visible when admin mode is on */
  admin?: boolean;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    title: "Explore",
    items: [
      { href: "/blog", label: "Blog" },
      { href: "/specs", label: "Specs" },
      { href: "/search", label: "Search" },
      { href: "/contributors", label: "Contributors" },
    ],
  },
  {
    title: "Build",
    items: [
      { href: "/invest", label: "Invest" },
      { href: "/treasury", label: "Treasury" },
      { href: "/assets", label: "Assets" },
    ],
  },
  {
    title: "Operate",
    admin: true,
    items: [
      { href: "/automation", label: "Automation" },
      { href: "/friction", label: "Friction" },
      { href: "/identity", label: "Identity" },
    ],
  },
];

const STORAGE_KEY = "coherence-admin-mode";

/* ------------------------------------------------------------------ */
/*  Shared link styles                                                */
/* ------------------------------------------------------------------ */

const pillClass =
  "rounded-lg border border-border/30 px-2.5 py-1 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 hover:border-border/60 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-ring";

const listClass =
  "block rounded-lg px-3 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-ring";

/* ------------------------------------------------------------------ */
/*  Component                                                         */
/* ------------------------------------------------------------------ */

interface NavMoreDropdownProps {
  apiBase: string;
  variant: "desktop" | "mobile";
  primaryNav?: NavItem[];
  heartbeatNav?: NavItem;
}

export function NavMoreDropdown({
  apiBase,
  variant,
  primaryNav,
  heartbeatNav,
}: NavMoreDropdownProps) {
  const [adminMode, setAdminMode] = useState(false);

  useEffect(() => {
    setAdminMode(localStorage.getItem(STORAGE_KEY) === "true");
  }, []);

  const toggleAdmin = () => {
    const next = !adminMode;
    setAdminMode(next);
    localStorage.setItem(STORAGE_KEY, String(next));
  };

  const visibleGroups = NAV_GROUPS.filter((g) => !g.admin || adminMode);

  if (variant === "desktop") {
    return (
      <details className="relative hidden md:block group">
        <summary
          className="list-none cursor-pointer rounded-lg border border-border/50 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:border-border transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1"
          aria-label="Open more navigation options"
          role="button"
        >
          More
        </summary>
        <div className="absolute right-0 mt-2 w-80 rounded-xl border border-border/50 bg-popover/95 backdrop-blur-md p-4 shadow-xl">
          <div className="space-y-3">
            {visibleGroups.map((group) => (
              <div key={group.title}>
                <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground/80 mb-1.5">
                  {group.title}
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {group.items.map((n) => (
                    <Link key={n.href} href={n.href} className={pillClass}>
                      {n.label}
                    </Link>
                  ))}
                  {group.title === "Explore" && (
                    <a
                      href={`${apiBase}/docs`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={pillClass}
                    >
                      API Docs
                    </a>
                  )}
                </div>
              </div>
            ))}

            {/* Admin toggle */}
            <div className="border-t border-border/30 pt-2">
              <button
                onClick={toggleAdmin}
                className="flex items-center gap-2 text-xs text-muted-foreground/60 hover:text-muted-foreground transition-colors duration-200"
              >
                <span
                  className={`inline-block h-2 w-2 rounded-full transition-colors ${
                    adminMode ? "bg-primary" : "bg-border"
                  }`}
                />
                {adminMode ? "Hide" : "Show"} admin pages
              </button>
            </div>
          </div>
        </div>
      </details>
    );
  }

  /* ---- Mobile variant ---- */
  return (
    <details className="md:hidden relative">
      <summary
        className="list-none cursor-pointer rounded-lg border border-border/50 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1"
        aria-label="Toggle navigation menu"
        role="button"
      >
        Menu
      </summary>
      <nav
        className="absolute right-0 mt-2 w-64 rounded-xl border border-border/50 bg-popover/95 backdrop-blur-md shadow-xl"
        aria-label="Mobile navigation"
      >
        <div className="p-3 space-y-1">
          {/* Primary nav items */}
          {primaryNav?.map((n) => (
            <Link
              key={n.href}
              href={n.href}
              className="block rounded-lg px-3 py-2 text-sm hover:bg-accent/60 transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-ring"
            >
              {n.label}
            </Link>
          ))}
          {heartbeatNav && (
            <Link
              href={heartbeatNav.href}
              className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm text-primary/80 hover:text-primary hover:bg-accent/60 transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <span className="relative flex h-1.5 w-1.5" aria-hidden="true">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary/40" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-primary/80" />
              </span>
              {heartbeatNav.label}
            </Link>
          )}

          {/* Grouped secondary nav */}
          {visibleGroups.map((group) => (
            <div key={group.title}>
              <div className="border-t border-border/30 my-2" />
              <p className="px-3 pt-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground/80">
                {group.title}
              </p>
              {group.items.map((n) => (
                <Link key={n.href} href={n.href} className={listClass}>
                  {n.label}
                </Link>
              ))}
              {group.title === "Explore" && (
                <a
                  href={`${apiBase}/docs`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={listClass}
                >
                  API Docs
                </a>
              )}
            </div>
          ))}

          {/* Admin toggle */}
          <div className="border-t border-border/30 my-2" />
          <button
            onClick={toggleAdmin}
            className="flex items-center gap-2 px-3 py-2 text-xs text-muted-foreground/60 hover:text-muted-foreground transition-colors duration-200 w-full"
          >
            <span
              className={`inline-block h-2 w-2 rounded-full transition-colors ${
                adminMode ? "bg-primary" : "bg-border"
              }`}
            />
            {adminMode ? "Hide" : "Show"} admin pages
          </button>
        </div>
      </nav>
    </details>
  );
}
