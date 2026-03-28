import Link from "next/link";

import { getApiBase } from "@/lib/api";
import { ActiveNavLink } from "./active_nav_link";

/** Primary nav — 5 core actions visible to everyone. */
const PRIMARY_NAV = [
  { href: "/ideas", label: "Ideas" },
  { href: "/contribute", label: "Contribute" },
  { href: "/resonance", label: "Resonance" },
  { href: "/pipeline", label: "Pipeline" },
  { href: "/nodes", label: "Nodes" },
];

/** Always visible — the heartbeat of the network. */
const HEARTBEAT_NAV = { href: "/resonance", label: "Resonance" };

/** Secondary nav — grouped by purpose, accessible via Menu dropdown. */
const SECONDARY_NAV = [
  // Value & investment
  { href: "/invest", label: "Invest" },
  { href: "/treasury", label: "Treasury" },
  { href: "/contributors", label: "Contributors" },
  { href: "/assets", label: "Assets" },
  // Knowledge & specs
  { href: "/specs", label: "Specs" },
  { href: "/blog", label: "Blog" },
  { href: "/search", label: "Search" },
  // Operations (power users)
  { href: "/tasks", label: "Work Cards" },
  { href: "/automation", label: "Automation" },
  { href: "/friction", label: "Friction" },
  { href: "/identity", label: "Identity" },
];

export default function SiteHeader() {
  const apiBase = getApiBase();

  return (
    <header className="sticky top-0 z-50 border-b border-border/40 bg-background/85 backdrop-blur-md" role="banner">
      <div className="mx-auto max-w-6xl px-4 md:px-8">
        <div className="flex h-14 items-center gap-4">
          <Link
            href="/"
            className="flex items-center gap-2 font-semibold tracking-tight text-foreground hover:text-primary transition-colors duration-300"
            aria-label="Coherence Network home"
          >
            <span className="relative flex h-2.5 w-2.5" aria-hidden="true" title="Network heartbeat">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary/40" />
              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-primary/80" />
            </span>
            Coherence Network
          </Link>

          <nav className="hidden md:flex items-center gap-1 text-sm" aria-label="Primary navigation">
            {PRIMARY_NAV.map((n) => (
              <ActiveNavLink
                key={n.href}
                href={n.href}
                label={n.label}
              />
            ))}
            <ActiveNavLink
              href={HEARTBEAT_NAV.href}
              label={HEARTBEAT_NAV.label}
              isHeartbeat
            />
          </nav>

          <div className="flex-1" />

          {/* Desktop "More" dropdown — secondary pages */}
          <details className="relative hidden md:block group">
            <summary
              className="list-none cursor-pointer rounded-lg border border-border/50 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:border-border transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1"
              aria-label="Open more navigation options"
              role="button"
            >
              More
            </summary>
            <div className="absolute right-0 mt-2 w-72 rounded-xl border border-border/50 bg-popover/95 backdrop-blur-md p-4 shadow-xl">
              <div className="space-y-2">
                <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground/80">Explore</p>
                <div className="flex flex-wrap gap-1.5">
                  {SECONDARY_NAV.map((n) => (
                    <Link
                      key={n.href}
                      href={n.href}
                      className="rounded-lg border border-border/30 px-2.5 py-1 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 hover:border-border/60 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-ring"
                    >
                      {n.label}
                    </Link>
                  ))}
                  <a
                    href={`${apiBase}/docs`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="rounded-lg border border-border/30 px-2.5 py-1 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 hover:border-border/60 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-ring"
                  >
                    API Docs
                  </a>
                </div>
              </div>
            </div>
          </details>

          {/* Mobile menu */}
          <details className="md:hidden relative">
            <summary
              className="list-none cursor-pointer rounded-lg border border-border/50 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1"
              aria-label="Toggle navigation menu"
              role="button"
            >
              Menu
            </summary>
            <nav
              className="absolute right-0 mt-2 w-56 rounded-xl border border-border/50 bg-popover/95 backdrop-blur-md shadow-xl"
              aria-label="Mobile navigation"
            >
              <div className="p-3 space-y-1">
                {PRIMARY_NAV.map((n) => (
                  <Link
                    key={n.href}
                    href={n.href}
                    className="block rounded-lg px-3 py-2 text-sm hover:bg-accent/60 transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-ring"
                  >
                    {n.label}
                  </Link>
                ))}
                <Link
                  href={HEARTBEAT_NAV.href}
                  className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm text-primary/80 hover:text-primary hover:bg-accent/60 transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  <span className="relative flex h-1.5 w-1.5" aria-hidden="true">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary/40" />
                    <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-primary/80" />
                  </span>
                  {HEARTBEAT_NAV.label}
                </Link>
                <div className="border-t border-border/30 my-2" />
                <p className="px-3 pt-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground/80">More</p>
                {SECONDARY_NAV.map((n) => (
                  <Link
                    key={n.href}
                    href={n.href}
                    className="block rounded-lg px-3 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-ring"
                  >
                    {n.label}
                  </Link>
                ))}
                <a
                  href={`${apiBase}/docs`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block rounded-lg px-3 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  API Docs
                </a>
              </div>
            </nav>
          </details>
        </div>
      </div>
    </header>
  );
}
