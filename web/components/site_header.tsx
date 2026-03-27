import Link from "next/link";

import { getApiBase } from "@/lib/api";
import { ActiveNavLink } from "./active_nav_link";
import { NavMoreDropdown } from "./nav_more_dropdown";

/** Primary nav — 5 core actions visible to everyone. */
const PRIMARY_NAV = [
  { href: "/ideas", label: "Ideas" },
  { href: "/contribute", label: "Contribute" },
  { href: "/resonance", label: "Resonance" },
  { href: "/tasks", label: "Pipeline" },
  { href: "/nodes", label: "Nodes" },
];

/** Always visible — the heartbeat of the network. */
const HEARTBEAT_NAV = { href: "/resonance", label: "Resonance" };

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

          {/* Desktop "More" dropdown — grouped secondary pages */}
          <NavMoreDropdown apiBase={apiBase} variant="desktop" />

          {/* Mobile menu */}
          <NavMoreDropdown
            apiBase={apiBase}
            variant="mobile"
            primaryNav={PRIMARY_NAV}
            heartbeatNav={HEARTBEAT_NAV}
          />
        </div>
      </div>
    </header>
  );
}
