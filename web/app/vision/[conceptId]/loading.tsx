export default function Loading() {
  return (
    <main className="min-h-screen animate-pulse">
      {/* Hero gradient placeholder */}
      <div className="h-64 bg-gradient-to-b from-stone-800/30 to-transparent" />

      <div className="max-w-4xl mx-auto px-6 -mt-20 space-y-8">
        {/* Breadcrumb */}
        <div className="h-4 w-48 rounded bg-stone-800/40" />

        {/* Title */}
        <div className="space-y-3">
          <div className="h-12 w-64 rounded bg-stone-800/40" />
          <div className="h-6 w-full max-w-2xl rounded bg-stone-800/30" />
          <div className="h-6 w-3/4 max-w-xl rounded bg-stone-800/30" />
        </div>

        {/* Content grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="md:col-span-2 space-y-6">
            <div className="h-48 rounded-2xl bg-stone-800/20 border border-stone-800/30" />
            <div className="h-32 rounded-2xl bg-stone-800/20 border border-stone-800/30" />
          </div>
          <div className="space-y-4">
            <div className="h-24 rounded-2xl bg-stone-800/20 border border-stone-800/30" />
            <div className="h-20 rounded-2xl bg-stone-800/20 border border-stone-800/30" />
          </div>
        </div>
      </div>
    </main>
  );
}
