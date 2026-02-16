import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getApiBase } from "@/lib/api";

const NAV = [
  { href: "/search", label: "Search" },
  { href: "/portfolio", label: "Portfolio" },
  { href: "/flow", label: "Flow" },
  { href: "/ideas", label: "Ideas" },
  { href: "/specs", label: "Specs" },
  { href: "/usage", label: "Usage" },
  { href: "/friction", label: "Friction" },
  { href: "/gates", label: "Gates" },
];

const SECONDARY = [
  { href: "/contributors", label: "Contributors" },
  { href: "/contributions", label: "Contributions" },
  { href: "/assets", label: "Assets" },
  { href: "/tasks", label: "Tasks" },
  { href: "/import", label: "Import" },
  { href: "/api-health", label: "API Health" },
];

export default function SiteHeader() {
  const apiBase = getApiBase();

  return (
    <header className="sticky top-0 z-50 border-b bg-background/80 backdrop-blur">
      <div className="mx-auto max-w-6xl px-4 md:px-8">
        <div className="flex h-14 items-center gap-3">
          <Link href="/" className="font-semibold tracking-tight">
            Coherence Network
          </Link>

          <nav className="hidden md:flex items-center gap-1 text-sm text-muted-foreground">
            {NAV.map((n) => (
              <Link
                key={n.href}
                href={n.href}
                className="rounded px-2 py-1 hover:text-foreground hover:bg-accent"
              >
                {n.label}
              </Link>
            ))}
          </nav>

          <div className="flex-1" />

          <nav className="hidden lg:flex items-center gap-1 text-sm text-muted-foreground">
            {SECONDARY.map((n) => (
              <Link
                key={n.href}
                href={n.href}
                className="rounded px-2 py-1 hover:text-foreground hover:bg-accent"
              >
                {n.label}
              </Link>
            ))}
          </nav>

          <form action="/search" method="GET" className="hidden lg:flex items-center gap-2">
            <Input
              name="q"
              placeholder="Search packages: react, fastapi, neo4j"
              className="w-72 bg-background/60"
              autoComplete="off"
            />
            <Button type="submit" variant="secondary">
              Go
            </Button>
          </form>

          <Button asChild variant="outline" className="hidden sm:inline-flex">
            <a href={`${apiBase}/docs`} target="_blank" rel="noopener noreferrer">
              API Docs
            </a>
          </Button>

          <details className="md:hidden relative">
            <summary className="list-none cursor-pointer rounded border px-2 py-1 text-sm">
              Menu
            </summary>
            <div className="absolute right-0 mt-2 w-48 rounded border bg-background shadow">
              <div className="p-2 grid gap-1">
                {NAV.map((n) => (
                  <Link
                    key={n.href}
                    href={n.href}
                    className="rounded px-2 py-1 text-sm hover:bg-accent"
                  >
                    {n.label}
                  </Link>
                ))}
                {SECONDARY.map((n) => (
                  <Link
                    key={n.href}
                    href={n.href}
                    className="rounded px-2 py-1 text-sm hover:bg-accent"
                  >
                    {n.label}
                  </Link>
                ))}
                <a
                  href={`${apiBase}/docs`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded px-2 py-1 text-sm hover:bg-accent"
                >
                  API Docs
                </a>
              </div>
            </div>
          </details>
        </div>
      </div>
    </header>
  );
}
