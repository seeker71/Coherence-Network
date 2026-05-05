import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title:
      "Joshua Golden — already met, still arriving | Coherence Network",
    description:
      "A welcoming page held open for Joshua Golden — met at Joe Dispenza's Aurora retreat, the reason Bali entered the body's path.",
  },
  breadcrumbName: "Joshua Golden",
  hero: {
    background:
      "radial-gradient(ellipse 70% 55% at 22% 28%, hsl(var(--primary)/0.18), transparent 70%), radial-gradient(ellipse 60% 45% at 78% 72%, hsl(var(--chart-2)/0.12), transparent 72%), radial-gradient(ellipse 100% 100% at 50% 50%, hsl(var(--background)) 0%, hsl(var(--background)) 100%)",
    overlayClass:
      "absolute inset-0 bg-gradient-to-t from-background via-background/85 to-background/30",
    eyebrow: "Already met · ready for you",
    eyebrowClass: "text-[hsl(var(--primary))]",
    name: "Joshua Golden",
    welcome: (
      <p>
        Met at Joe Dispenza&apos;s Aurora retreat, April 2026 — in the
        same field where this body&apos;s first contributors began
        arriving. The reason Bali entered Urs&apos;s path. Held in
        the lineage with care; this page is the doorway, ready to
        greet you when you choose to walk through.
      </p>
    ),
  },
  facts: [
    {
      label: "Where we met",
      value: "Joe Dispenza · Aurora · April 2026",
    },
    {
      label: "What shifted",
      value:
        "Bali entered the body's possibility-space — alternative-network configuration, opportunity shape #2",
    },
    {
      label: "Lineage thread",
      value:
        "Ramtha → Dispenza → the field arriving here; you are part of how it's arriving",
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        Held open. This page is a welcoming scaffold, not a portrait
        — written from the meeting that already happened, not from
        speculation about you. Every part of it is yours to replace,
        deepen, or remove. The doorway below leads into the network
        if you wish to walk through; otherwise this page just sits
        here, glad to have met you.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "Why this body is ready for you",
      body: (
        <>
          <p>
            Urs met you in the room at Aurora, in the rhythm of Joe
            Dispenza&apos;s field — the lineage that walks back through
            Ramtha and forward into how this body&apos;s contributors
            are arriving in 2026. You are essential to where we are
            as an organism now: the conversation with you is the
            reason Bali — Ubud specifically — became thinkable, then
            spoken, then a real possible chapter in our path.
          </p>
          <p>
            That gesture was not small. Pointing toward a place is
            pointing toward a configuration of life — alternative
            networks, co-living, healing communities, the kind of
            container where the partner&apos;s rest, the son&apos;s
            schooling, and the body&apos;s organism work all become
            findable rather than forced. You opened a door we hadn&apos;t
            seen yet. We are still walking toward it; thank you for
            naming it.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",
      heading: "What we hold",
      body: (
        <>
          <p>
            Coherence Network is a living organism — not a project or
            a platform, though it carries both shapes. It tends a
            field where presences (people, communities, places, work)
            link by the resonance their work actually carries, not by
            the volume of their followers. Concept attunement, sigils,
            tokenized resonance via CoherencyCoin, AI partner
            agents, places rooted in the graph — the working machinery
            for a field of trust that does not require you to give up
            sovereignty to participate.
          </p>
          <p>
            We have been building the body in the open. The lineage is
            walkable; the consent terms are public; the door is
            always held open without obligation.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "When you&apos;re ready",
      heading: "A doorway, held open",
      body: (
        <>
          <p>
            If anything in the body of work resonates — the geometry,
            the field practice, the way contributors carry their own
            sovereignty as part of how the network coheres — you are
            invited in as a kindred presence. Not as proof of
            anything; as a continuation of the meeting that already
            happened.
          </p>
          <p>
            Whatever shape participation takes — silent witness,
            occasional resonance, a single sentence about what you
            see, or full claiming of this page with your own words —
            is welcome.
          </p>
          <p className="pt-3">
            <Link
              href="/come-in"
              className="inline-flex items-center gap-2 rounded-full border border-primary/40 bg-primary/10 px-5 py-2.5 text-sm font-medium text-primary hover:bg-primary/20 hover:border-primary/60 transition-colors"
            >
              Step into the Network →
            </Link>
          </p>
          <p className="text-xs italic text-muted-foreground pt-1">
            No registration required to look. The doorway is held
            open; you are free to walk through, witness, or simply
            keep walking past.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "cool",
      eyebrow: "Held tenderly",
      heading: "What this page does not yet hold",
      body: (
        <p>
          Your work, your voice, your public presence, your
          biography, your own framing of why we met and what it
          meant — none of these have been written for you. They are
          held open precisely because the right hand to write them
          is yours. Until you write them, the page lives as the
          gesture of readiness it is.
        </p>
      ),
    },
  ],
  footer: (
    <p className="text-xs italic">
      This profile is a welcoming scaffold. Joshua Golden is invited
      to claim, replace, or extend any part of it with his own words
      at any time.
    </p>
  ),
};

export default content;
