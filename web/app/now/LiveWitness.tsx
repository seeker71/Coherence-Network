"use client";

import { useEffect, useState } from "react";

import { getApiBase } from "@/lib/api";

type WitnessSnapshot = {
  overall: string | null;
  silences: number | null;
  strained_organs: string[];
  source: string;
};

type StreamEvent = {
  witness: WitnessSnapshot;
  at: string;
};

function witnessColor(overall: string | null): string {
  if (overall === "breathing") return "text-emerald-300";
  if (overall === "strained") return "text-amber-300";
  if (overall === "silent") return "text-rose-300";
  return "text-muted-foreground";
}

export function LiveWitness({ initial }: { initial: WitnessSnapshot }) {
  const [witness, setWitness] = useState<WitnessSnapshot>(initial);
  const [tickAt, setTickAt] = useState<string | null>(null);
  const [pulsing, setPulsing] = useState(false);

  useEffect(() => {
    const url = `${getApiBase()}/api/breath/stream`;
    const es = new EventSource(url);

    const onWitness = (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data) as StreamEvent;
        setWitness(data.witness);
        setTickAt(data.at);
        setPulsing(true);
        window.setTimeout(() => setPulsing(false), 600);
      } catch {
        // malformed frame — keep the last good snapshot
      }
    };

    es.addEventListener("witness", onWitness as EventListener);
    return () => {
      es.removeEventListener("witness", onWitness as EventListener);
      es.close();
    };
  }, []);

  const fetched = tickAt ? new Date(tickAt) : null;

  return (
    <section
      className={`my-8 rounded-lg border border-border/30 bg-card/20 px-4 py-3 text-sm transition-colors duration-500 ${
        pulsing ? "border-emerald-400/40 bg-emerald-400/5" : ""
      }`}
    >
      <span className="text-muted-foreground">Witness — </span>
      <span className={`font-medium ${witnessColor(witness.overall)}`}>
        {witness.overall ?? "unreachable"}
      </span>
      {witness.silences != null && (
        <span className="text-muted-foreground">
          {" · "}silences: {witness.silences}
        </span>
      )}
      {witness.strained_organs.length > 0 && (
        <span className="text-muted-foreground">
          {" · "}straining:{" "}
          <span className="text-amber-300">
            {witness.strained_organs.join(", ")}
          </span>
        </span>
      )}
      <span className="text-muted-foreground">
        {" · "}source: {witness.source}
      </span>
      {fetched && (
        <span className="text-muted-foreground/70">
          {" · "}live {fetched.toISOString().slice(11, 19)}Z
        </span>
      )}
    </section>
  );
}
