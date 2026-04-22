"use client";

/**
 * CarriedBy — the presences that carry this concept's frequency.
 *
 * Complement to ResonatesWith (on /people/[id]): a presence page
 * shows the concepts it resonates with; a concept page shows the
 * presences that carry it. Someone reading about Ceremony lands
 * here and discovers the artists, sanctuaries, gatherings, and
 * communities already living this concept — each a doorway to
 * their own presence page.
 *
 * Sourced from /api/concepts/{id}/carried-by, which reverses the
 * resonates-with edges the resonance service lays down.
 */
import Link from "next/link";
import { useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";

type Carrier = {
  presence_id: string;
  presence_name: string;
  presence_type: string;
  image_url: string | null;
  score: number;
  shared_tokens: string[];
  method: string;
};

const TYPE_LABEL: Record<string, string> = {
  contributor: "person",
  community: "community",
  "network-org": "project",
  event: "gathering",
  scene: "scene",
  practice: "practice",
  skill: "program",
  asset: "work",
};

// English pluralisation irregulars the render actually encounters.
// Adding more here costs nothing; doing "just add s" would spell
// things like "communitys" and "practicys".
const PLURAL: Record<string, string> = {
  person: "persons",
  community: "communities",
  project: "projects",
  gathering: "gatherings",
  scene: "scenes",
  practice: "practices",
  program: "programs",
  work: "works",
};

export function CarriedBy({ conceptId }: { conceptId: string }) {
  const [items, setItems] = useState<Carrier[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const apiBase = getApiBase();
    (async () => {
      try {
        const r = await fetch(
          `${apiBase}/api/concepts/${encodeURIComponent(conceptId)}/carried-by`,
          { cache: "no-store" },
        );
        if (!r.ok) return;
        const body: { items: Carrier[] } = await r.json();
        setItems(Array.isArray(body.items) ? body.items : []);
      } catch {
        /* transient */
      } finally {
        setLoaded(true);
      }
    })();
  }, [conceptId]);

  if (!loaded || items.length === 0) return null;

  // Group by presence type so visitors can scan — artists with
  // artists, communities with communities. Keep the overall order
  // within each bucket (score desc).
  const groups: Record<string, Carrier[]> = {};
  for (const it of items) {
    const key = TYPE_LABEL[it.presence_type] || it.presence_type;
    (groups[key] ||= []).push(it);
  }
  const groupOrder = [
    "person",
    "community",
    "gathering",
    "project",
    "scene",
    "practice",
    "program",
    "work",
  ];
  const orderedKeys = groupOrder.filter((k) => groups[k]);

  return (
    <section className="max-w-3xl mt-8">
      <div className="rounded-2xl border border-border/40 bg-card/40 p-5">
        <p className="text-[11px] uppercase tracking-[0.18em] font-semibold text-muted-foreground mb-1">
          Carried by
        </p>
        <p className="text-xs text-muted-foreground/80 mb-4 italic">
          Presences in the network whose spectrum overlaps with this
          concept — doorways into each one.
        </p>
        <div className="space-y-4">
          {orderedKeys.map((key) => (
            <div key={key}>
              <p className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground/60 mb-2">
                {groups[key].length === 1 ? key : PLURAL[key] || `${key}s`}
              </p>
              <ul className="flex flex-wrap gap-2">
                {groups[key].map((c) => {
                  const strength = Math.min(0.98, 0.45 + c.score * 2.5);
                  return (
                    <li key={c.presence_id}>
                      <Link
                        href={`/people/${encodeURIComponent(c.presence_id)}`}
                        title={
                          c.shared_tokens.length
                            ? `${c.shared_tokens.join(" · ")}\n(${c.method})`
                            : c.method
                        }
                        className="inline-flex items-center gap-2 rounded-full border border-border/40 bg-background/40 hover:bg-accent/40 px-3 py-1.5 transition-colors"
                        style={{ opacity: strength }}
                      >
                        {c.image_url ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img
                            src={c.image_url}
                            alt=""
                            className="w-5 h-5 rounded-full object-cover border border-border/30"
                          />
                        ) : (
                          <span className="w-5 h-5 rounded-full bg-accent/40 text-[10px] flex items-center justify-center">
                            {c.presence_name.charAt(0).toUpperCase()}
                          </span>
                        )}
                        <span className="text-sm text-foreground/90">
                          {c.presence_name}
                        </span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
