import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Ocean Bloom 2024 — Downtown Boulder · Poranguí, Liquid Bloom, Samuel J, Shawn Heinrichs, Bloomurian | Coherence Network",
    description:
      "A welcome to Ocean Bloom 2024 — the conscious-music gathering in Downtown Boulder that wove Poranguí, Liquid Bloom, Samuel J, Shawn Heinrichs, and Bloomurian into one configuration. A recurring archetype in this body's lineage of transformational-music festivals.",
  },
  breadcrumbName: "Ocean Bloom 2024",
  hero: {
    background:
      "radial-gradient(ellipse at 30% 25%, hsl(200 65% 55% / 0.55) 0%, transparent 55%), radial-gradient(ellipse at 80% 80%, hsl(280 30% 22% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(200 55% 60%) 0%, hsl(220 35% 38%) 50%, hsl(280 30% 18%) 100%)",
    eyebrow: "Downtown Boulder · 2024 · conscious-music gathering · the configuration that wove five artists into one room",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Ocean Bloom 2024",
    welcome: (
      <>
        <p>
          A conscious-music gathering held in Downtown Boulder
          in 2024 that wove together a specific set of artists
          this network has been tracking:{" "}
          <Link
            href="/people/porangui"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Poranguí
          </Link>
          ,{" "}
          <Link
            href="/people/liquid-bloom"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Liquid Bloom
          </Link>{" "}
          (Amani Friend), Samuel J, Shawn Heinrichs, and{" "}
          <Link
            href="/people/bloomurian"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Bloomurian
          </Link>
          . An archetype of the body&apos;s lineage:
          multi-artist conscious-music gatherings whose
          recurring lineups are themselves a stable substrate
          across festivals.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          The same five-to-eight artists circulate across
          Lightning in a Bottle, Sonic Bloom, Beloved, Sedona
          Yoga Festival, and the broader transformational-music
          festival field. Ocean Bloom 2024 was one specific
          weekend in one specific city where many of them landed
          together.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "When & where",
      value: "2024, Downtown Boulder, Colorado.",
    },
    {
      label: "Lineup (partial)",
      value: (
        <ul>
          <li>
            <Link href="/people/porangui" className="hover:text-primary transition-colors">
              Poranguí
            </Link>
          </li>
          <li>
            <Link href="/people/liquid-bloom" className="hover:text-primary transition-colors">
              Liquid Bloom
            </Link>{" "}
            (Amani Friend, Desert Dwellers lineage)
          </li>
          <li>Samuel J</li>
          <li>Shawn Heinrichs</li>
          <li>
            <Link href="/people/bloomurian" className="hover:text-primary transition-colors">
              Bloomurian
            </Link>{" "}
            (Robin Liepman)
          </li>
        </ul>
      ),
    },
    {
      label: "Recurring archetype",
      value: "Ocean Bloom is one expression of the multi-artist conscious-music gathering archetype that recurs across the transformational-music festival circuit: Lightning in a Bottle, Sonic Bloom, Beloved, Sedona Yoga Festival.",
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        Ocean Bloom 2024 is one specific gathering; this page
        recognises both that weekend and the broader archetype
        of conscious-music gatherings it belongs to in this
        body&apos;s lineage.
      </p>
    ),
  },
  articles: [
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What Ocean Bloom 2024 has given the Coherence Network",
      body: (
        <ul>
          <li>
            The Boulder anchor of the body&apos;s
            transformational-music lineage. The same artists
            recur across other rooms (
            <Link
              href="/people/boulder-ecstatic-dance"
              className="text-primary hover:underline"
            >
              Boulder Ecstatic Dance
            </Link>
            , PORTAL Late-Night Takeovers at Meow Wolf Denver,
            the MAPS Psychedelic Science gatherings) — the
            conscious-music festival circuit and the
            ecstatic-dance floor are one continuous community.
          </li>
          <li>
            The configuration as substrate-teaching: <em>same
            artists, different room, same field</em>. The body
            reads this as evidence of{" "}
            <Link
              href="/vision/lc-frequency-routes-reception"
              className="text-primary hover:underline"
            >
              lc-frequency-routes-reception
            </Link>{" "}
            (people in the same room are in different realities
            depending on what they are tuned to; the recurring
            lineup is the tuning).
          </li>
          <li>
            One specific 2024 weekend in Downtown Boulder was
            part of the path that brought several cells of this
            network&apos;s graph into proximity with each other
            long before any of them appeared in the substrate.
          </li>
        </ul>
      ),
    },
  ],
  footer: (
    <>
      <p>
        <strong>In-body record:</strong>{" "}
        <Link href="/people/porangui" className="text-primary hover:underline">
          Poranguí
        </Link>
        {" · "}
        <Link href="/people/liquid-bloom" className="text-primary hover:underline">
          Liquid Bloom
        </Link>
        {" · "}
        <Link href="/people/bloomurian" className="text-primary hover:underline">
          Bloomurian
        </Link>
        {" · "}
        <Link href="/people/boulder-ecstatic-dance" className="text-primary hover:underline">
          Boulder Ecstatic Dance
        </Link>
        {" · "}
        <Link
          href="https://github.com/seeker71/Coherence-Network/blob/main/docs/lineage/2026-04-29-constellation-of-cells.md"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          constellation-of-cells.md
        </Link>
      </p>
    </>
  ),
};

export default content;
