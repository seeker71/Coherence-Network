// Side-by-side capability comparison between this instance ("us") and a peer.
// Renders rows for providers, languages, and substrate canonicals; each cell
// is marked "both", "us only", or "peer only" — never "missing" or "wrong".
// Each instance's truth is its own; this is a difference reading, not a verdict.

"use client";

import { useMemo, useState } from "react";

type Side = "us" | "peer" | "both";

type Row = {
  kind: string;
  label: string;
  value: string;
  side: Side;
};

type Props = {
  peerInstanceId: string;
  us: {
    providers: string[];
    language_coverage: string[];
    substrate_canonicals: string[];
  };
  peer: {
    providers: string[];
    language_coverage: string[];
    substrate_canonicals: string[];
  };
  labels: {
    title: string;
    expand: string;
    collapse: string;
    kindProviders: string;
    kindLanguages: string;
    kindSubstrate: string;
    us: string;
    both: string;
    usOnly: string;
    peerOnly: string;
  };
};

function diff(us: string[], peer: string[]): { value: string; side: Side }[] {
  const usSet = new Set(us);
  const peerSet = new Set(peer);
  const all = Array.from(new Set([...us, ...peer])).sort();
  return all.map((v) => {
    const inUs = usSet.has(v);
    const inPeer = peerSet.has(v);
    const side: Side = inUs && inPeer ? "both" : inUs ? "us" : "peer";
    return { value: v, side };
  });
}

export default function CapabilityComparison({
  peerInstanceId,
  us,
  peer,
  labels,
}: Props) {
  const [open, setOpen] = useState(false);

  const rows = useMemo<Row[]>(() => {
    const groups: { kind: string; label: string; pair: [string[], string[]] }[] = [
      { kind: "providers", label: labels.kindProviders, pair: [us.providers, peer.providers] },
      { kind: "languages", label: labels.kindLanguages, pair: [us.language_coverage, peer.language_coverage] },
      { kind: "substrate", label: labels.kindSubstrate, pair: [us.substrate_canonicals, peer.substrate_canonicals] },
    ];
    const out: Row[] = [];
    for (const g of groups) {
      for (const d of diff(g.pair[0], g.pair[1])) {
        out.push({ kind: g.kind, label: g.label, value: d.value, side: d.side });
      }
    }
    return out;
  }, [us, peer, labels]);

  const counts = useMemo(() => {
    const c = { both: 0, us: 0, peer: 0 };
    for (const r of rows) c[r.side] += 1;
    return c;
  }, [rows]);

  return (
    <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/40 to-card/20 p-4 space-y-3">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-3 text-left"
        aria-expanded={open}
      >
        <div className="space-y-0.5">
          <h3 className="text-sm font-medium">{labels.title}</h3>
          <p className="text-xs text-muted-foreground">
            <span className="text-emerald-300/90">{counts.both} {labels.both}</span>
            <span className="mx-2 text-border/60">·</span>
            <span className="text-blue-300/90">{counts.us} {labels.usOnly}</span>
            <span className="mx-2 text-border/60">·</span>
            <span className="text-amber-300/90">{counts.peer} {labels.peerOnly}</span>
          </p>
        </div>
        <span className="text-xs text-muted-foreground">{open ? labels.collapse : labels.expand}</span>
      </button>

      {open ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[480px] text-xs">
            <thead>
              <tr className="text-muted-foreground/80">
                <th className="text-left font-normal py-2 pr-3">kind</th>
                <th className="text-left font-normal py-2 pr-3">value</th>
                <th className="text-left font-normal py-2 pr-3">{labels.us}</th>
                <th className="text-left font-normal py-2">{peerInstanceId}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr
                  key={`${r.kind}-${r.value}-${i}`}
                  className="border-t border-border/15"
                >
                  <td className="py-1.5 pr-3 text-muted-foreground/80">{r.label}</td>
                  <td className="py-1.5 pr-3 font-mono">{r.value}</td>
                  <td className="py-1.5 pr-3">
                    {r.side === "us" || r.side === "both" ? (
                      <span className="text-emerald-300">●</span>
                    ) : (
                      <span className="text-muted-foreground/30">○</span>
                    )}
                  </td>
                  <td className="py-1.5">
                    {r.side === "peer" || r.side === "both" ? (
                      <span className="text-emerald-300">●</span>
                    ) : (
                      <span className="text-muted-foreground/30">○</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}
