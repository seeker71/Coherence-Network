import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getApiBase } from "@/lib/api";

const PRIMARY_NAV = [
  { href: "/today", label: "Today" },
  { href: "/demo", label: "Demo" },
  { href: "/ideas", label: "Ideas" },
  { href: "/tasks", label: "Work" },
  { href: "/flow", label: "Progress" },
];

const EXPLORE_NAV = [
  { href: "/search", label: "Search" },
  { href: "/portfolio", label: "Portfolio" },
  { href: "/specs", label: "Plans" },
  { href: "/contribute", label: "Contribute" },
  { href: "/contributors", label: "People" },
];

const TOOL_NAV = [
  { href: "/usage", label: "Usage" },
  { href: "/automation", label: "Automation" },
  { href: "/remote-ops", label: "Remote Ops" },
  { href: "/agent", label: "Agent" },
  { href: "/friction", label: "Friction" },
  { href: "/gates", label: "Checks" },
  { href: "/contributions", label: "Contributions" },
  { href: "/assets", label: "Assets" },
  { href: "/import", label: "Import" },
  { href: "/api-health", label: "API Health" },
];

export default function SiteHeader() {
  const apiBase = getApiBase();

  return (
    <header className="sticky top-0 z-50 border-b bg-background/80 backdrop-blur" role="banner">
      <div className="mx-auto max-w-6xl px-4 md:px-8">
        <div className="flex h-14 items-center gap-3">
          <Link href="/" className="font-semibold tracking-tight" aria-label="Coherence Network home">
            Coherence Network
          </Link>

          <nav className="hidden md:flex items-center gap-1 text-sm text-muted-foreground" aria-label="Primary navigation">
            {PRIMARY_NAV.map((n) => (
              <Link
                key={n.href}
                href={n.href}
                className="rounded px-2 py-1 hover:text-foreground hover:bg-accent focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1"
              >
                {n.label}
              </Link>
            ))}
          </nav>

          <div className="flex-1" />

          <details className="relative hidden md:block">
            <summary
              className="list-none cursor-pointer rounded border px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1"
              aria-label="Open more navigation options"
              role="button"
            >
              More
            </summary>
            <div className="absolute right-0 mt-2 w-72 rounded-lg border bg-background p-3 shadow-lg">
              <div className="space-y-3">
                <div className="space-y-2">
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Explore</p>
                  <div className="flex flex-wrap gap-2">
                    {EXPLORE_NAV.map((n) => (
                      <Link
                        key={n.href}
                        href={n.href}
                        className="rounded border px-2 py-1 text-sm hover:bg-accent focus:outline-none focus:ring-2 focus:ring-ring"
                      >
                        {n.label}
                      </Link>
                    ))}
                  </div>
                </div>
                <div className="space-y-2">
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Tools</p>
                  <div className="flex flex-wrap gap-2">
                    {TOOL_NAV.map((n) => (
                      <Link
                        key={n.href}
                        href={n.href}
                        className="rounded border px-2 py-1 text-sm hover:bg-accent focus:outline-none focus:ring-2 focus:ring-ring"
                      >
                        {n.label}
                      </Link>
                    ))}
                    <a
                      href={`${apiBase}/docs`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="rounded border px-2 py-1 text-sm hover:bg-accent focus:outline-none focus:ring-2 focus:ring-ring"
                    >
                      API Docs
                    </a>
                  </div>
                </div>
              </div>
            </div>
          </details>

          <form action="/search" method="GET" className="hidden lg:flex items-center gap-2" role="search" aria-label="Search the network">
            <label htmlFor="header-search" className="sr-only">Search the network</label>
            <Input
              id="header-search"
              name="q"
              placeholder="Search ideas, projects, or people"
              className="w-72 bg-background/60"
              autoComplete="off"
            />
            <Button type="submit" variant="secondary">
              Go
            </Button>
          </form>

          <details className="md:hidden relative">
            <summary
              className="list-none cursor-pointer rounded border px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1"
              aria-label="Toggle navigation menu"
              role="button"
            >
              Menu
            </summary>
            <nav
              className="absolute right-0 mt-2 w-48 rounded border bg-background shadow"
              aria-label="Mobile navigation"
            >
              <div className="p-2 grid gap-1">
                {PRIMARY_NAV.map((n) => (
                  <Link
                    key={n.href}
                    href={n.href}
                    className="rounded px-2 py-1 text-sm hover:bg-accent focus:outline-none focus:ring-2 focus:ring-ring"
                  >
                    {n.label}
                  </Link>
                ))}
                <p className="px-2 pt-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">Explore</p>
                {EXPLORE_NAV.map((n) => (
                  <Link
                    key={n.href}
                    href={n.href}
                    className="rounded px-2 py-1 text-sm hover:bg-accent focus:outline-none focus:ring-2 focus:ring-ring"
                  >
                    {n.label}
                  </Link>
                ))}
                <p className="px-2 pt-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">Tools</p>
                {TOOL_NAV.map((n) => (
                  <Link
                    key={n.href}
                    href={n.href}
                    className="rounded px-2 py-1 text-sm hover:bg-accent focus:outline-none focus:ring-2 focus:ring-ring"
                  >
                    {n.label}
                  </Link>
                ))}
                <a
                  href={`${apiBase}/docs`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded px-2 py-1 text-sm hover:bg-accent focus:outline-none focus:ring-2 focus:ring-ring"
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
