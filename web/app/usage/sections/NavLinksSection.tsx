import Link from "next/link";

const NAV_LINKS = [
  { href: "/", label: "Home" },
  { href: "/portfolio", label: "Portfolio" },
  { href: "/ideas", label: "Ideas" },
  { href: "/specs", label: "Specs" },
  { href: "/flow", label: "Flow" },
  { href: "/contributors", label: "Contributors" },
  { href: "/contributions", label: "Contributions" },
  { href: "/assets", label: "Assets" },
  { href: "/tasks", label: "Tasks" },
  { href: "/agent", label: "Agent" },
  { href: "/gates", label: "Gates" },
] as const;

export function NavLinksSection() {
  return (
    <section className="rounded-xl border border-border/30 bg-card/50 px-3 py-3">
      <div className="flex flex-wrap items-center gap-2">
        {NAV_LINKS.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className="inline-flex items-center rounded-full border border-border/30 bg-background/55 px-3 py-1.5 text-sm text-muted-foreground transition hover:text-foreground"
          >
            {link.label}
          </Link>
        ))}
      </div>
    </section>
  );
}
