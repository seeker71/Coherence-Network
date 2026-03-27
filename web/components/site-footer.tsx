import Link from "next/link";

export default function SiteFooter() {
  return (
    <footer className="border-t border-border/40 bg-background/80" role="contentinfo">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-5 text-sm text-muted-foreground md:px-8">
        <p className="text-xs md:text-sm">Coherence Network</p>
        <nav aria-label="Footer navigation">
          <Link
            href="/ecosystem"
            className="rounded-md px-2 py-1 text-sm font-medium text-foreground/90 transition hover:text-primary focus:outline-none focus:ring-2 focus:ring-ring"
          >
            Ecosystem
          </Link>
        </nav>
      </div>
    </footer>
  );
}
