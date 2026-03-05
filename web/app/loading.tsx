export default function Loading() {
  return (
    <main className="mx-auto max-w-6xl px-4 md:px-8 py-12" aria-busy="true" aria-label="Loading content">
      <div className="animate-pulse space-y-6">
        <div className="h-8 w-48 rounded bg-muted" />
        <div className="grid gap-4 md:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-32 rounded-lg bg-muted" />
          ))}
        </div>
        <div className="space-y-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-6 rounded bg-muted" style={{ width: `${80 - i * 10}%` }} />
          ))}
        </div>
      </div>
    </main>
  );
}
