import Link from "next/link";

/**
 * Rendered when the pulse monitor itself is unreachable. We refuse to show
 * stale or invented data — the absence of the witness is itself a truth
 * worth communicating.
 */
export function WitnessQuiet({ pulseBase }: { pulseBase: string }) {
  return (
    <section className="rounded-3xl border border-dashed border-border/40 bg-gradient-to-b from-muted/20 to-transparent p-10 text-center space-y-4">
      <p className="text-xs uppercase tracking-widest text-muted-foreground">
        Unknown
      </p>
      <h2 className="text-2xl font-light text-muted-foreground">
        The witness is quiet
      </h2>
      <p className="max-w-xl mx-auto text-sm text-muted-foreground leading-relaxed">
        No one is currently recording our breath. The pulse monitor is not
        answering — it may be starting, moving, or silent itself. This page
        will not show invented data, so we wait.
      </p>
      {pulseBase && (
        <p className="text-[11px] font-mono text-muted-foreground/60 break-all">
          {pulseBase}
        </p>
      )}
      <div className="pt-2 flex flex-wrap justify-center gap-4 text-sm">
        <Link href="/api-health" className="text-blue-400 hover:underline">
          API health (raw)
        </Link>
        <Link href="/vitality" className="text-emerald-400 hover:underline">
          Network vitality
        </Link>
      </div>
    </section>
  );
}
