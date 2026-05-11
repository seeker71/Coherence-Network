import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Paradiso Ubud — cultural hall holding 5Rhythms, DISSOLVE, and the embodied lineage | Coherence Network",
    description:
      "A welcome to Paradiso Ubud — the cultural hall where the Coherence Network's Ubud embodied lineage moves through. Holds 5Rhythms, DISSOLVE, film, and other movement practice.",
  },
  breadcrumbName: "Paradiso Ubud",
  hero: {
    background:
      "radial-gradient(ellipse at 35% 25%, hsl(280 55% 55% / 0.55) 0%, transparent 55%), radial-gradient(ellipse at 80% 85%, hsl(20 35% 22% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(285 45% 55%) 0%, hsl(255 30% 35%) 50%, hsl(15 35% 18%) 100%)",
    eyebrow: "Cultural hall · Ubud · 5Rhythms, DISSOLVE, film, ceremony · venue for the body's embodied lineage",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Paradiso Ubud",
    welcome: (
      <>
        <p>
          A cultural-hall venue in Ubud holding film, cultural
          events,{" "}
          <Link
            href="/people/5rhythms-ubud"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            5Rhythms
          </Link>
          ,{" "}
          <Link
            href="/people/dissolve-ubud"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            DISSOLVE
          </Link>
          , and other movement and ceremony practice. The room
          where this body&apos;s Ubud embodied lineage moves
          through — coherence-as-motion taught by feet, breath,
          touch, and shared pulse.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          Verify the current schedule locally; door rhythms drift
          with the seasons.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "What it is",
      value: "Cultural-hall venue in Ubud. Vegan kitchen below, large open-floor performance/movement space upstairs. Holds film screenings, conscious-cinema nights, dance practices, ceremony.",
    },
    {
      label: "Practices held",
      value: (
        <ul>
          <li>
            <Link
              href="/people/5rhythms-ubud"
              className="hover:text-primary transition-colors"
            >
              5Rhythms Ubud
            </Link>{" "}
            (Gabrielle Roth&apos;s wave map)
          </li>
          <li>
            <Link
              href="/people/dissolve-ubud"
              className="hover:text-primary transition-colors"
            >
              DISSOLVE Ubud
            </Link>{" "}
            (contact improvisation + authentic relating; Tara Li
            facilitating)
          </li>
          <li>Film screenings and conscious-cinema</li>
          <li>Visiting teachers, ceremony, workshops</li>
        </ul>
      ),
    },
    {
      label: "Public anchors",
      value: (
        <p className="flex flex-wrap gap-x-3 gap-y-1">
          <Link
            href="https://ubud.co.id/directory-listing/paradiso-ubud/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Paradiso Ubud listing
          </Link>
        </p>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        Paradiso&apos;s public anchor is thin (one directory
        listing); the venue tends itself through its own social
        channels and word-of-mouth. This page recognises its role
        in this body&apos;s Ubud embodied lineage.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "What this room holds",
      body: (
        <>
          <p>
            Paradiso is a cultural-hall venue in Ubud whose
            architecture and rhythm hold a regular weekly
            offering of conscious-movement practice. The room is
            the container; the practices change with the day. On
            its busiest nights — DISSOLVE on Tuesday and 5Rhythms
            on its own rhythm — the floor fills with bodies
            moving in resonance with whatever the facilitator is
            offering.
          </p>
          <p>
            For this body specifically, Paradiso is the
            architectural anchor of the Ubud embodied lineage.
            The body learned a piece of its current vocabulary —
            coherence-as-motion, consent in real time, the field
            that forms when many bodies move together — on this
            floor.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What Paradiso Ubud has given the Coherence Network",
      body: (
        <ul>
          <li>
            The architectural ground for the Ubud
            embodied-lineage record. See{" "}
            <Link
              href="https://github.com/seeker71/Coherence-Network/blob/main/docs/lineage/ubud-embodied-lineage.md"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              ubud-embodied-lineage.md
            </Link>
            .
          </li>
          <li>
            The venue holding{" "}
            <Link href="/people/5rhythms-ubud" className="text-primary hover:underline">
              5Rhythms Ubud
            </Link>{" "}
            and{" "}
            <Link href="/people/dissolve-ubud" className="text-primary hover:underline">
              DISSOLVE Ubud
            </Link>{" "}
            — both threaded into this body&apos;s lived lineage.
          </li>
          <li>
            Coherence-as-motion as a substrate teaching — bodies
            in shared time learning timing, consent, release,
            play.
          </li>
        </ul>
      ),
    },
  ],
  footer: (
    <>
      <p>
        <strong>Public anchors:</strong>{" "}
        <Link
          href="https://ubud.co.id/directory-listing/paradiso-ubud/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Paradiso Ubud listing
        </Link>
      </p>
      <p>
        <strong>In-body record:</strong>{" "}
        <Link href="/people/5rhythms-ubud" className="text-primary hover:underline">
          5Rhythms Ubud
        </Link>
        {" · "}
        <Link href="/people/dissolve-ubud" className="text-primary hover:underline">
          DISSOLVE Ubud
        </Link>
        {" · "}
        <Link
          href="https://github.com/seeker71/Coherence-Network/blob/main/docs/lineage/ubud-embodied-lineage.md"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          ubud-embodied-lineage.md
        </Link>
      </p>
    </>
  ),
};

export default content;
