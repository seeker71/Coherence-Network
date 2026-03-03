import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getApiBase } from "@/lib/api";

type NavLink = { href: string; label: string };

const PRIMARY_NAV: NavLink[] = [
  { href: "/ideas", label: "Explore Ideas" },
  { href: "/flow", label: "Network Graph" },
  { href: "/contribute", label: "Collaborate" },
  { href: "/tasks", label: "Execution" },
];

const WORKSPACE_GROUPS: Array<{ title: string; links: NavLink[] }> = [
  {
    title: "Discover",
    links: [
      { href: "/search", label: "Search" },
      { href: "/portfolio", label: "Portfolio" },
      { href: "/ideas", label: "Ideas" },
      { href: "/specs", label: "Specs" },
      { href: "/flow", label: "Flow" },
    ],
  },
  {
    title: "Collaborate",
    links: [
      { href: "/contribute", label: "Contribute" },
      { href: "/contributors", label: "Contributors" },
      { href: "/contributions", label: "Contributions" },
      { href: "/assets", label: "Assets" },
      { href: "/import", label: "Import" },
    ],
  },
  {
    title: "Operate",
    links: [
      { href: "/tasks", label: "Tasks" },
      { href: "/agent", label: "Agent" },
      { href: "/usage", label: "Usage" },
      { href: "/automation", label: "Automation" },
      { href: "/friction", label: "Friction" },
      { href: "/gates", label: "Gates" },
      { href: "/remote-ops", label: "Remote Ops" },
      { href: "/api-health", label: "API Health" },
    ],
  },
];

const ALL_WORKSPACE_LINKS: NavLink[] = WORKSPACE_GROUPS.flatMap((group) => group.links);

export default function SiteHeader() {
  const apiBase = getApiBase();

  return (
    <header className="sticky top-0 z-50 border-b border-border/70 bg-background/70 backdrop-blur-xl">
      <div className="mx-auto max-w-6xl px-4 md:px-8">
        <div className="flex h-14 items-center gap-3">
          <Link href="/" className="shrink-0">
            <p className="font-semibold tracking-tight leading-tight">Coherence Network</p>
            <p className="text-xs text-muted-foreground">A shared home for open source collaboration</p>
          </Link>

          <nav className="hidden lg:flex items-center gap-1 text-sm text-muted-foreground">
            {PRIMARY_NAV.map((n) => (
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

          <form action="/search" method="GET" className="hidden xl:flex items-center gap-2">
            <Input
              name="q"
              placeholder="Search projects or ideas"
              className="w-64 bg-background/60"
              autoComplete="off"
            />
            <Button type="submit" variant="secondary">
              Search
            </Button>
          </form>

          <details className="relative hidden md:block">
            <summary className="list-none cursor-pointer rounded-full border border-border/80 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground">
              Workspace
            </summary>
            <div className="absolute right-0 mt-2 w-[28rem] rounded-2xl border border-border/80 bg-popover/95 p-4 shadow-lg backdrop-blur">
              <div className="grid gap-4 sm:grid-cols-3">
                {WORKSPACE_GROUPS.map((group) => (
                  <section key={group.title} className="space-y-2">
                    <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{group.title}</p>
                    <div className="grid gap-1">
                      {group.links.map((link) => (
                        <Link
                          key={link.href}
                          href={link.href}
                          className="rounded px-2 py-1 text-sm text-muted-foreground hover:bg-accent hover:text-foreground"
                        >
                          {link.label}
                        </Link>
                      ))}
                    </div>
                  </section>
                ))}
              </div>
            </div>
          </details>

          <Button asChild variant="outline" className="hidden sm:inline-flex">
            <a href={`${apiBase}/docs`} target="_blank" rel="noopener noreferrer">
              API Docs
            </a>
          </Button>

          <Button asChild className="hidden sm:inline-flex">
            <Link href="/contribute">Start Here</Link>
          </Button>

          <details className="md:hidden relative shrink-0">
            <summary className="list-none cursor-pointer rounded-full border border-border/80 px-3 py-1.5 text-sm">
              Menu
            </summary>
            <div className="absolute right-0 mt-2 w-72 rounded-2xl border border-border/80 bg-popover/95 p-3 shadow-lg backdrop-blur">
              <form action="/search" method="GET" className="grid grid-cols-[1fr_auto] gap-2">
                <Input name="q" placeholder="Search..." autoComplete="off" />
                <Button type="submit" variant="secondary">
                  Go
                </Button>
              </form>
              <div className="mt-3 space-y-3">
                <section className="space-y-1">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Start</p>
                  {PRIMARY_NAV.map((n) => (
                    <Link
                      key={`primary-${n.href}`}
                      href={n.href}
                      className="block rounded px-2 py-1 text-sm hover:bg-accent"
                    >
                      {n.label}
                    </Link>
                  ))}
                </section>
                <section className="space-y-1">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Workspace</p>
                  {ALL_WORKSPACE_LINKS.map((n) => (
                    <Link
                      key={`all-${n.href}`}
                      href={n.href}
                      className="block rounded px-2 py-1 text-sm text-muted-foreground hover:bg-accent hover:text-foreground"
                    >
                      {n.label}
                    </Link>
                  ))}
                </section>
                <a
                  href={`${apiBase}/docs`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block rounded px-2 py-1 text-sm hover:bg-accent"
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
