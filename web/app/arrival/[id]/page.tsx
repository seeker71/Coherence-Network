// /arrival/[id] — the moment of being received. After /begin lands, the
// new cell arrives here. The body greets them by name, holds what they
// said they carry, and points them at one thing they can do next.
//
// Server-rendered: fetches the contributor record by id, shows the warm
// arrival, and reads cleanly without client-side hydration.

import type { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import { notFound } from "next/navigation";
import { getApiBase } from "@/lib/api";

interface RouteParams {
  params: Promise<{ id: string }>;
}

interface Contributor {
  id: string;
  name?: string;
  display_name?: string;
  email?: string;
  location?: string;
  skills?: string;
  offering?: string;
  message?: string;
  resonant_roles?: string[];
  type?: string;
  created_at?: string;
}

const ROLE_LABELS: Record<string, string> = {
  "land-steward": "Land · stewardship",
  "builder-maker": "Builder · maker · craftsperson",
  healer: "Healer · bodyworker · therapist",
  teacher: "Teacher · guide · facilitator",
  "musician-artist": "Musician · artist · creator",
  "farmer-gardener": "Farmer · gardener · grower",
  "cook-baker": "Cook · baker · food-tender",
  "engineer-coder": "Engineer · coder · systems",
  "writer-translator": "Writer · translator",
  "host-keeper": "Host · space-keeper",
  "transport-mechanic": "Transport · mechanic",
  "elder-witness": "Elder · witness",
  other: "Other",
};

async function fetchContributor(id: string): Promise<Contributor | null> {
  const base = getApiBase();
  try {
    const res = await fetch(`${base}/api/contributors/${encodeURIComponent(id)}`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as Contributor;
  } catch {
    return null;
  }
}

export async function generateMetadata({
  params,
}: RouteParams): Promise<Metadata> {
  const { id } = await params;
  const c = await fetchContributor(id);
  const name = c?.name || c?.display_name || "Welcome";
  return {
    title: `${name} — held by the body`,
    description: "A new cell, received.",
    robots: { index: false, follow: false },
  };
}

function welcomeLine(c: Contributor): { eyebrow: string; line: string } {
  const offering = (c.offering || "").trim();
  const skills = (c.skills || "").trim();
  const message = (c.message || "").trim();

  if (offering) {
    return {
      eyebrow: "What you carry, as you said it",
      line: offering,
    };
  }
  if (skills) {
    return {
      eyebrow: "What you bring, as you said it",
      line: skills,
    };
  }
  if (message) {
    return {
      eyebrow: "What you wrote on arriving",
      line: message,
    };
  }
  return {
    eyebrow: "Held",
    line: "You arrived without naming what you carry. That's allowed. The body holds you anyway.",
  };
}

export default async function ArrivalPage({ params }: RouteParams) {
  const { id } = await params;
  const c = await fetchContributor(id);
  if (!c) notFound();

  const name = (c.name || c.display_name || "friend").trim();
  const firstName = name.split(/\s+/)[0];
  const { eyebrow, line } = welcomeLine(c);
  const roles = (c.resonant_roles || []).filter((r) => ROLE_LABELS[r]);

  return (
    <main id="main-content" className="bg-stone-950">
      {/* Warm hero with the network's pulse visual */}
      <section className="relative w-full overflow-hidden">
        <div className="relative h-[44vh] min-h-[320px] max-h-[480px]">
          <Image
            src="/visuals/01-the-pulse.png"
            alt="The body's living pulse — a radiant golden field."
            fill
            priority
            className="object-cover"
            sizes="100vw"
          />
          <div className="absolute inset-0 bg-gradient-to-b from-stone-950/30 via-stone-950/40 to-stone-950" />
          <div className="absolute inset-0 flex items-end">
            <div className="mx-auto w-full max-w-2xl px-6 pb-10 sm:pb-14">
              <p className="text-xs uppercase tracking-widest text-amber-300/90">
                You are held in the body now
              </p>
              <h1 className="mt-3 text-4xl sm:text-5xl font-light tracking-tight text-stone-50">
                Welcome, {firstName}.
              </h1>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-2xl px-6 py-12 space-y-8">
        <p className="text-lg leading-relaxed text-stone-200">
          The body has noticed you. Your name, your email, what you carry —
          it's all woven into the body's memory now. There's nothing more
          you need to do today. The body holds you while you settle.
        </p>

        <div className="rounded-2xl border border-amber-500/30 bg-amber-500/5 p-5 space-y-2">
          <p className="text-[11px] uppercase tracking-[0.18em] font-semibold text-amber-500">
            {eyebrow}
          </p>
          <p className="text-base text-stone-200 italic leading-relaxed">
            "{line}"
          </p>
        </div>

        {roles.length > 0 ? (
          <div className="space-y-3">
            <p className="text-xs uppercase tracking-widest text-muted-foreground">
              The cells you resonate with
            </p>
            <div className="flex flex-wrap gap-2">
              {roles.map((r) => (
                <span
                  key={r}
                  className="rounded-full border border-amber-500/30 bg-amber-500/5 px-3 py-1 text-sm text-amber-200"
                >
                  {ROLE_LABELS[r]}
                </span>
              ))}
            </div>
          </div>
        ) : null}

        <div className="space-y-3">
          <p className="text-xs uppercase tracking-widest text-muted-foreground">
            How the body knows you
          </p>
          <ul className="text-sm text-stone-300 space-y-1">
            <li>
              <span className="text-muted-foreground">Name:</span>{" "}
              <span className="text-stone-100">{name}</span>
            </li>
            {c.email ? (
              <li>
                <span className="text-muted-foreground">Email:</span>{" "}
                <span className="text-stone-100">{c.email}</span>
              </li>
            ) : null}
            {c.location ? (
              <li>
                <span className="text-muted-foreground">Where:</span>{" "}
                <span className="text-stone-100">{c.location}</span>
              </li>
            ) : null}
            <li>
              <span className="text-muted-foreground">Contributor id:</span>{" "}
              <span className="font-mono text-stone-300">{c.id}</span>
            </li>
          </ul>
        </div>
      </section>

      <section className="bg-stone-900/40 py-12">
        <div className="mx-auto max-w-2xl px-6 space-y-6">
          <p className="text-xs uppercase tracking-widest text-amber-500">
            For your first breath here
          </p>
          <h2 className="text-2xl font-light tracking-tight text-stone-50">
            Three small invitations
          </h2>
          <p className="text-base text-stone-300 leading-relaxed">
            None required. None on a timeline. Pick the one that feels
            calling, or none of them. The body holds you either way.
          </p>

          <ol className="space-y-4 mt-4">
            <li className="rounded-xl border border-border/30 bg-card/30 p-5 space-y-2">
              <p className="text-sm font-medium text-amber-400">
                1 · Sit with the silence
              </p>
              <p className="text-sm text-stone-300 leading-relaxed">
                Read the eight notebook pages from a Buddhist temple in
                Bali. The codex this body organizes around came through
                three days of held quiet, drawn by hand on a temple floor.
                It's the personal ground this network grew from.
              </p>
              <Link
                href="/silence"
                className="text-sm text-amber-500 hover:text-amber-400"
              >
                Sit with /silence →
              </Link>
            </li>

            <li className="rounded-xl border border-border/30 bg-card/30 p-5 space-y-2">
              <p className="text-sm font-medium text-amber-400">
                2 · Register what you offer
              </p>
              <p className="text-sm text-stone-300 leading-relaxed">
                If there's something specific you'd like cells to find —
                a service, a belonging, a space, a skill — register it.
                The body's memory will hold it; cells looking for what
                you have will find you by resonance.
              </p>
              <Link
                href="/share"
                className="text-sm text-amber-500 hover:text-amber-400"
              >
                Share something →
              </Link>
            </li>

            <li className="rounded-xl border border-border/30 bg-card/30 p-5 space-y-2">
              <p className="text-sm font-medium text-amber-400">
                3 · Read the living concepts
              </p>
              <p className="text-sm text-stone-300 leading-relaxed">
                Eighty-seven concepts the body holds — pulse, sensing,
                attunement, vitality, nourishing, resonating, expressing,
                spiraling, and the rest. You can leave reactions and
                voices on any of them. Anyone can update the story content
                — the body is wiki-style by design.
              </p>
              <Link
                href="/vision"
                className="text-sm text-amber-500 hover:text-amber-400"
              >
                Read /vision →
              </Link>
            </li>
          </ol>

          <p className="text-base text-muted-foreground italic pt-2">
            And — when you write to{" "}
            <a
              href="mailto:umuff71@gmail.com"
              className="text-amber-400 hover:text-amber-300"
            >
              urs at umuff71@gmail.com
            </a>{" "}
            — he reads what you sent and writes back, personally, while
            the body is still small enough that he can.
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-2xl px-6 py-12 space-y-4">
        <p className="text-xs uppercase tracking-widest text-muted-foreground">
          Where you live in the body now
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Link
            href="/me"
            className="rounded-xl border border-border/30 bg-card/30 hover:bg-card/50 p-4 transition-colors"
          >
            <p className="text-sm font-medium text-amber-400">/me</p>
            <p className="text-xs text-muted-foreground mt-1">
              Your presence — what the body knows about you and how to
              begin again if that feels right.
            </p>
          </Link>
          <Link
            href="/identity"
            className="rounded-xl border border-border/30 bg-card/30 hover:bg-card/50 p-4 transition-colors"
          >
            <p className="text-sm font-medium text-amber-400">/identity</p>
            <p className="text-xs text-muted-foreground mt-1">
              Link other identity providers (GitHub, X, wallet…) to this
              cell.
            </p>
          </Link>
          <Link
            href="/me/work"
            className="rounded-xl border border-border/30 bg-card/30 hover:bg-card/50 p-4 transition-colors"
          >
            <p className="text-sm font-medium text-amber-400">/me/work</p>
            <p className="text-xs text-muted-foreground mt-1">
              Your body of work — the things you'll build here, made
              visible as you build them.
            </p>
          </Link>
        </div>
      </section>

      <section className="mx-auto max-w-2xl px-6 py-8">
        <p className="text-sm text-muted-foreground italic">
          Sovereignty stays with you. Your data is yours. You can ask to
          be removed at any time. Coming back next week, next month, or
          next year — the body remembers.
        </p>
      </section>
    </main>
  );
}
