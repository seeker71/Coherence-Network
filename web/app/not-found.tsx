import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto max-w-2xl px-4 py-24 text-center space-y-6">
      <div className="space-y-3">
        <p className="text-6xl font-light text-primary">404</p>
        <h1 className="text-2xl md:text-3xl font-light tracking-tight">
          This page doesn't exist yet
        </h1>
        <p className="text-muted-foreground leading-relaxed max-w-md mx-auto">
          Maybe it will someday. Ideas have a way of becoming real around here.
        </p>
      </div>
      <div className="flex flex-col sm:flex-row gap-3 justify-center">
        <Link
          href="/"
          className="rounded-xl bg-primary px-6 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
        >
          Go home
        </Link>
        <Link
          href="/ideas"
          className="rounded-xl border border-border/30 px-6 py-2.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200"
        >
          Browse ideas
        </Link>
      </div>
    </main>
  );
}
