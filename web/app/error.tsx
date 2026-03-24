"use client";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const isFetchError = error.message?.toLowerCase().includes("fetch");

  return (
    <main
      className="mx-auto max-w-2xl px-4 py-24 text-center space-y-6"
      role="alert"
      aria-live="assertive"
    >
      <div className="space-y-3">
        <h1 className="text-3xl md:text-4xl font-light tracking-tight">
          {isFetchError ? "Can't reach the network" : "Something went wrong"}
        </h1>
        <p className="text-muted-foreground leading-relaxed max-w-md mx-auto">
          {isFetchError
            ? "The API isn't responding right now. This usually means the backend server needs to be started."
            : error.message || "An unexpected error occurred. Please try again."}
        </p>
      </div>
      <div className="flex flex-col sm:flex-row gap-3 justify-center">
        <button
          onClick={reset}
          className="rounded-xl bg-primary px-6 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
        >
          Try again
        </button>
        <a
          href="/"
          className="rounded-xl border border-border/30 px-6 py-2.5 text-sm text-muted-foreground hover:text-foreground hover:bg-accent/60 transition-all duration-200"
        >
          Go home
        </a>
      </div>
      {isFetchError && (
        <p className="text-xs text-muted-foreground/80 max-w-sm mx-auto">
          Start the API with <code className="text-muted-foreground font-mono">cd api && uvicorn app.main:app</code> and
          then try again.
        </p>
      )}
    </main>
  );
}
