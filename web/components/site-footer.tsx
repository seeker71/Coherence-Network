import Link from "next/link";

/** Always-visible footer with ecosystem entry point (R1). */
export default function SiteFooter() {
  return (
    <footer className="border-t border-border/40 bg-background/85 backdrop-blur-md" role="contentinfo">
      <div className="mx-auto max-w-6xl px-4 md:px-8 py-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-muted-foreground">
        <p>&copy; {new Date().getFullYear()} Coherence Network</p>
        <nav aria-label="Footer navigation" className="flex items-center gap-4">
          <Link
            href="/ecosystem"
            className="hover:text-foreground transition-colors duration-200"
            data-testid="footer-ecosystem-link"
          >
            Ecosystem
          </Link>
        </nav>
      </div>
    </footer>
  );
}
