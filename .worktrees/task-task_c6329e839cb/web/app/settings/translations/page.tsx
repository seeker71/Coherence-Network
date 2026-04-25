import Link from "next/link";

import { getApiBase } from "@/lib/api";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Translations coverage — Coherence Network",
  description:
    "Per-locale counts of original, machine-attuned, human-attuned, and stale translations across the concept space.",
};

type Coverage = {
  original: number;
  human: number;
  machine: number;
  stale: number;
};

type LocaleEntry = {
  code: string;
  label?: string;
  coverage: Coverage;
};

type LocalesResponse = {
  locales: LocaleEntry[];
  default: string;
};

async function fetchLocales(): Promise<LocalesResponse | null> {
  try {
    const response = await fetch(`${getApiBase()}/api/locales`, {
      cache: "no-store",
    });
    if (!response.ok) return null;
    return (await response.json()) as LocalesResponse;
  } catch {
    return null;
  }
}

function CoverageBar({ coverage }: { coverage: Coverage }) {
  const total =
    coverage.original + coverage.human + coverage.machine + coverage.stale;
  if (total === 0) {
    return (
      <div className="h-2 w-full rounded bg-stone-900/60 border border-stone-800" />
    );
  }
  const pct = (n: number) => (n / total) * 100;
  return (
    <div
      className="h-2 w-full rounded overflow-hidden flex"
      title={`${coverage.original} original · ${coverage.human} human · ${coverage.machine} machine · ${coverage.stale} stale`}
    >
      <div
        className="bg-amber-500/80"
        style={{ width: `${pct(coverage.original)}%` }}
      />
      <div
        className="bg-violet-500/80"
        style={{ width: `${pct(coverage.human)}%` }}
      />
      <div
        className="bg-teal-500/60"
        style={{ width: `${pct(coverage.machine)}%` }}
      />
      <div
        className="bg-rose-500/40"
        style={{ width: `${pct(coverage.stale)}%` }}
      />
    </div>
  );
}

function Legend() {
  const items = [
    { color: "bg-amber-500/80", label: "original — written in this language" },
    { color: "bg-violet-500/80", label: "human — translation from a contributor" },
    { color: "bg-teal-500/60", label: "machine — machine translation, awaiting native voice" },
    { color: "bg-rose-500/40", label: "stale — source has changed since translation" },
  ];
  return (
    <ul className="text-xs text-stone-400 space-y-1">
      {items.map((item) => (
        <li key={item.label} className="flex items-center gap-2">
          <span className={`inline-block w-3 h-3 rounded ${item.color}`} />
          <span>{item.label}</span>
        </li>
      ))}
    </ul>
  );
}

export default async function TranslationsCoveragePage() {
  const data = await fetchLocales();

  return (
    <main className="max-w-3xl mx-auto px-6 py-12">
      <nav className="text-sm text-stone-500 mb-8 flex items-center gap-2" aria-label="breadcrumb">
        <Link href="/" className="hover:text-amber-400/80 transition-colors">
          Home
        </Link>
        <span className="text-stone-700">/</span>
        <Link href="/settings" className="hover:text-amber-400/80 transition-colors">
          Settings
        </Link>
        <span className="text-stone-700">/</span>
        <span className="text-stone-300">Translations</span>
      </nav>

      <h1 className="text-3xl font-extralight text-white mb-2">Translations</h1>
      <p className="text-stone-400 mb-8 text-sm leading-relaxed">
        Per-locale coverage across concepts and other translatable entities.
        Original authoring in a language sits alongside human and machine
        translations; stale markers rise as source content changes and
        translations age out.
      </p>

      {!data && (
        <div className="rounded border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-200">
          Could not reach the locales API. The dashboard will appear when the
          API is reachable.
        </div>
      )}

      {data && (
        <>
          <div className="space-y-4 mb-8">
            {data.locales.map((locale) => {
              const total =
                locale.coverage.original +
                locale.coverage.human +
                locale.coverage.machine +
                locale.coverage.stale;
              const isDefault = locale.code === data.default;
              return (
                <div
                  key={locale.code}
                  className="rounded border border-stone-800 bg-stone-950/40 p-4"
                >
                  <div className="flex items-baseline justify-between mb-2">
                    <div className="flex items-baseline gap-3">
                      <code className="text-lg font-light text-white">
                        {locale.code}
                      </code>
                      {locale.label && (
                        <span className="text-sm text-stone-400">
                          {locale.label}
                        </span>
                      )}
                      {isDefault && (
                        <span className="text-[10px] uppercase tracking-wide text-amber-400/80 border border-amber-500/30 rounded px-2 py-0.5">
                          default
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-stone-500">
                      {total} view{total === 1 ? "" : "s"}
                    </div>
                  </div>
                  <CoverageBar coverage={locale.coverage} />
                  <div className="mt-2 text-xs text-stone-500 flex gap-4">
                    <span>
                      <span className="text-amber-400/80">{locale.coverage.original}</span>{" "}
                      original
                    </span>
                    <span>
                      <span className="text-violet-400/80">{locale.coverage.human}</span>{" "}
                      human
                    </span>
                    <span>
                      <span className="text-teal-400/80">{locale.coverage.machine}</span>{" "}
                      machine
                    </span>
                    <span>
                      <span className="text-rose-400/80">{locale.coverage.stale}</span>{" "}
                      stale
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          <Legend />
        </>
      )}
    </main>
  );
}
