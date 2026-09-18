"use client";

// VedicChart — Urs's natal chart drawn from /api/vedic/chart: the South Indian
// square (rashis fixed, lagna marked), the placements, and the Vimshottari
// dasha cycle. Every number comes from form-stdlib/vedic-chat.fk on the fkwu
// runtime; this component draws and computes nothing of the chart.

import { useEffect, useState } from "react";

import { getApiBase } from "@/lib/api";

type Position = {
  longitude: number;
  rashi: number;
  rashi_name: string;
  western: string;
  degree: number;
  nakshatra: number;
  nakshatra_name: string;
  pada: number;
};

type Graha = Position & { key: number; name: string; english: string; house: number };

type Dasha = { lord: number; name: string; english: string; start: number; end: number; running: boolean };

type Chart = {
  ground: { y: number; m: number; d: number; uth: number; utm: number; lat: number; lon: number };
  ayanamsa: number;
  lagna: Position;
  grahas: Graha[];
  year: number;
  dashas: Dasha[];
};

type ChartResponse = {
  chart: Chart;
  ground: string;
  year: number;
  runtime: string;
  body: string;
  lane: string;
};

// The South Indian square: rashis sit in fixed cells, Mesha at the top row's
// second cell, running clockwise. Index = rashi 0..11 (Mesha..Meena).
const SQUARE: (number | null)[][] = [
  [11, 0, 1, 2],
  [10, null, null, 3],
  [9, null, null, 4],
  [8, 7, 6, 5],
];

// Two-letter faces for the grahas inside the cells, keyed by the cell's graha key.
const ABBR: Record<number, string> = { 0: "Sy", 1: "Ch", 2: "Ma", 3: "Bu", 4: "Gu", 5: "Sk", 6: "Sa", 7: "Ra", 8: "Ke" };

function yearWords(y: number): string {
  const whole = Math.floor(y);
  const month = Math.min(12, Math.max(1, 1 + Math.floor((y - whole) * 12)));
  return `${whole}-${String(month).padStart(2, "0")}`;
}

export function VedicChart() {
  const [data, setData] = useState<ChartResponse | null>(null);
  const [silence, setSilence] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${getApiBase()}/api/vedic/chart`, { cache: "no-store" });
        if (!res.ok) {
          let detail = `${res.status}`;
          try {
            const err = (await res.json()) as { detail?: string };
            if (err.detail) detail = err.detail;
          } catch {
            // the body was not JSON; the status is the whole message
          }
          if (!cancelled) setSilence(`The native body did not answer (${detail}). The chart is cast on the fkwu kernel; when it is not reachable from this host, this door stays honest and quiet.`);
          return;
        }
        const json = (await res.json()) as ChartResponse;
        if (!cancelled) setData(json);
      } catch (e) {
        if (!cancelled) setSilence(`The door could not be reached: ${e instanceof Error ? e.message : String(e)}`);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (silence) {
    return (
      <p className="rounded-lg border border-dashed border-border px-3 py-2 text-sm text-muted-foreground">{silence}</p>
    );
  }
  if (!data) {
    return <p className="text-sm text-muted-foreground">Casting the chart…</p>;
  }

  const { chart } = data;
  const byRashi = new Map<number, Graha[]>();
  for (const g of chart.grahas) {
    const list = byRashi.get(g.rashi) ?? [];
    list.push(g);
    byRashi.set(g.rashi, list);
  }
  const rashiName = (i: number) => {
    const g = chart.grahas.find((x) => x.rashi === i);
    if (g) return g.rashi_name;
    if (chart.lagna.rashi === i) return chart.lagna.rashi_name;
    return RASHI_NAMES[i];
  };
  const running = chart.dashas.find((x) => x.running);

  return (
    <section className="flex flex-col gap-6">
      <p className="text-xs text-muted-foreground">
        Cast from <span className="text-foreground">{data.ground}</span> · Lahiri ayanamsa {chart.ayanamsa.toFixed(2)}° · computed on{" "}
        <span className="uppercase tracking-wider">{data.runtime}</span>
      </p>

      {/* The square */}
      <div className="grid aspect-square w-full grid-cols-4 grid-rows-4 overflow-hidden rounded-lg border border-border bg-card text-[11px] md:text-xs">
        {SQUARE.flatMap((row, r) =>
          row.map((rashi, c) => {
            if (rashi === null) {
              if (r === 1 && c === 1) {
                return (
                  <div key={`${r}-${c}`} className="col-span-2 row-span-2 flex flex-col items-center justify-center gap-1 p-2 text-center">
                    <span className="text-sm font-medium text-foreground md:text-base">Urs</span>
                    <span className="text-muted-foreground">6 Oct 1971 · 09:15 CET · Luzern</span>
                    <span className="text-muted-foreground">
                      Lagna {chart.lagna.rashi_name} {chart.lagna.degree.toFixed(2)}°
                    </span>
                    <span className="text-muted-foreground">{chart.lagna.nakshatra_name} pada {chart.lagna.pada}</span>
                  </div>
                );
              }
              return null;
            }
            const here = byRashi.get(rashi) ?? [];
            const isLagna = chart.lagna.rashi === rashi;
            const house = ((rashi - chart.lagna.rashi + 12) % 12) + 1;
            return (
              <div
                key={`${r}-${c}`}
                className={`relative flex flex-col gap-0.5 border border-border/60 p-1.5 md:p-2 ${isLagna ? "bg-primary/10" : ""}`}
              >
                <div className="flex items-baseline justify-between gap-1">
                  <span className="truncate text-muted-foreground">{rashiName(rashi)}</span>
                  <span className="text-[10px] text-muted-foreground/70">{house}</span>
                </div>
                {isLagna ? <span className="font-medium text-primary">La {Math.floor(chart.lagna.degree)}°</span> : null}
                {here.map((g) => (
                  <span key={g.key} className="text-foreground" title={`${g.name} (${g.english}) ${g.degree.toFixed(2)}° ${g.nakshatra_name} pada ${g.pada}`}>
                    {ABBR[g.key]} {Math.floor(g.degree)}°
                  </span>
                ))}
              </div>
            );
          }),
        )}
      </div>

      {/* The placements */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-xs uppercase tracking-wider text-muted-foreground">
            <tr>
              <th className="py-1 pr-2 sm:pr-3 font-normal">Graha</th>
              <th className="py-1 pr-2 sm:pr-3 font-normal">Rashi</th>
              <th className="py-1 pr-2 sm:pr-3 font-normal text-right">Deg</th>
              <th className="py-1 pr-2 sm:pr-3 font-normal">Nakshatra</th>
              <th className="py-1 pr-2 sm:pr-3 font-normal text-right">Pada</th>
              <th className="py-1 font-normal text-right">House</th>
            </tr>
          </thead>
          <tbody className="text-foreground">
            <tr className="border-t border-border/60">
              <td className="py-1 pr-2 sm:pr-3">Lagna</td>
              <td className="py-1 pr-2 sm:pr-3">
                {chart.lagna.rashi_name} <span className="hidden text-muted-foreground sm:inline">({chart.lagna.western})</span>
              </td>
              <td className="py-1 pr-2 sm:pr-3 text-right tabular-nums">{chart.lagna.degree.toFixed(2)}</td>
              <td className="py-1 pr-2 sm:pr-3">{chart.lagna.nakshatra_name}</td>
              <td className="py-1 pr-2 sm:pr-3 text-right tabular-nums">{chart.lagna.pada}</td>
              <td className="py-1 text-right tabular-nums">1</td>
            </tr>
            {chart.grahas.map((g) => (
              <tr key={g.key} className="border-t border-border/60">
                <td className="py-1 pr-2 sm:pr-3">
                  {g.name} <span className="hidden text-muted-foreground sm:inline">({g.english})</span>
                </td>
                <td className="py-1 pr-2 sm:pr-3">
                  {g.rashi_name} <span className="hidden text-muted-foreground sm:inline">({g.western})</span>
                </td>
                <td className="py-1 pr-2 sm:pr-3 text-right tabular-nums">{g.degree.toFixed(2)}</td>
                <td className="py-1 pr-2 sm:pr-3">{g.nakshatra_name}</td>
                <td className="py-1 pr-2 sm:pr-3 text-right tabular-nums">{g.pada}</td>
                <td className="py-1 text-right tabular-nums">{g.house}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* The dasha cycle */}
      <div>
        <h2 className="mb-2 text-xs uppercase tracking-wider text-muted-foreground">Vimshottari mahadashas</h2>
        <ol className="flex flex-col gap-1 text-sm">
          {chart.dashas.map((d) => (
            <li
              key={`${d.lord}-${d.start}`}
              className={`flex items-baseline justify-between gap-3 rounded px-2 py-1 ${d.running ? "bg-primary/10 text-foreground" : "text-muted-foreground"}`}
            >
              <span>
                {d.name} <span className="opacity-70">({d.english})</span>
              </span>
              <span className="tabular-nums">
                {yearWords(d.start)} to {yearWords(d.end)}
                {d.running ? <span className="ml-2 text-primary">running</span> : null}
              </span>
            </li>
          ))}
        </ol>
        {running ? (
          <p className="mt-2 text-xs text-muted-foreground">
            {`Read at ${chart.year.toFixed(1)}: the ${running.name} mahadasha. Boundaries carry the Moon's floor, about five months.`}
          </p>
        ) : null}
      </div>
    </section>
  );
}

const RASHI_NAMES = ["Mesha", "Vrishabha", "Mithuna", "Karka", "Simha", "Kanya", "Tula", "Vrishchika", "Dhanu", "Makara", "Kumbha", "Meena"];
