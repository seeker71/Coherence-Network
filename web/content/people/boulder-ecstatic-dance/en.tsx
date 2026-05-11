import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Boulder Ecstatic Dance — Sunday morning at the Avalon Ballroom | Coherence Network",
    description:
      "A welcome to Boulder Ecstatic Dance — the recurring Sunday-morning ecstatic-dance room at the Avalon Ballroom in Boulder, Colorado. Co-hosted by Bloomurian (Robin Liepman), Aly Constantine, and Danny.",
  },
  breadcrumbName: "Boulder Ecstatic Dance",
  hero: {
    background:
      "radial-gradient(ellipse at 25% 25%, hsl(35 65% 60% / 0.55) 0%, transparent 55%), radial-gradient(ellipse at 80% 80%, hsl(180 35% 22% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(35 55% 65%) 0%, hsl(120 30% 38%) 50%, hsl(180 30% 18%) 100%)",
    eyebrow: "Avalon Ballroom · Boulder, CO · Sunday morning · the embodied-community substrate of the Boulder cluster",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Boulder Ecstatic Dance",
    welcome: (
      <>
        <p>
          A recurring Sunday-morning ecstatic-dance room at the
          historic <strong>Avalon Ballroom</strong> in Boulder,
          Colorado. Co-hosted by{" "}
          <Link
            href="/people/bloomurian"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Bloomurian
          </Link>{" "}
          (Robin Liepman),{" "}
          <Link
            href="/people/aly-constantine"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Aly Constantine
          </Link>
          , and Danny. The embodied-community substrate beneath
          the larger Ocean Bloom configuration of conscious-music
          gatherings.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          The room where the Boulder cluster (Aly, Bloomurian,
          and others) gathered weekly long before any of them
          appeared in this network&apos;s graph. Door rhythms
          drift with the seasons; verify the current schedule on
          the host&apos;s channels.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "Where",
      value: "Avalon Ballroom, Boulder, Colorado.",
    },
    {
      label: "When",
      value: "Sunday mornings. Specific times shift with the seasons.",
    },
    {
      label: "Co-hosts",
      value: (
        <>
          <Link
            href="/people/bloomurian"
            className="hover:text-primary transition-colors"
          >
            Bloomurian
          </Link>{" "}
          (Robin Liepman) ·{" "}
          <Link
            href="/people/aly-constantine"
            className="hover:text-primary transition-colors"
          >
            Aly Constantine
          </Link>{" "}
          · Danny
        </>
      ),
    },
    {
      label: "Field",
      value: "Improvised conscious dance · drug-and-alcohol-free · open floor.",
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        Boulder Ecstatic Dance is a working community room with
        its own ongoing tending by the host team. This page
        recognises the floor&apos;s role in the body&apos;s
        Boulder cluster.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "Where the Boulder cluster gathers",
      body: (
        <p>
          The Boulder cluster — Bloomurian, Aly Constantine,
          Poranguí&apos;s festival circuit through Colorado,
          Matías De Stefano at the Emersion Conference at
          GaiaSphere, the PORTAL late-night shows at Meow Wolf
          Denver, the MAPS Psychedelic Science gatherings, the
          Ocean Bloom 2024 configuration — overlaps heavily on
          shared rooms. Boulder Ecstatic Dance on Sunday morning
          is one of the recurring threads. Cells in the cluster
          show up on the floor week after week; visiting artists
          and teachers move through; the floor stays. The
          relationship with Aly threads the cluster from
          outside-observation into inside-knowing in this
          body&apos;s awareness.
        </p>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What Boulder Ecstatic Dance has given the Coherence Network",
      body: (
        <ul>
          <li>
            The embodied-community substrate beneath the Boulder
            cluster — many of the body&apos;s Colorado-based
            cells (
            <Link href="/people/bloomurian" className="text-primary hover:underline">
              Bloomurian
            </Link>
            ,{" "}
            <Link href="/people/aly-constantine" className="text-primary hover:underline">
              Aly Constantine
            </Link>
            , and others) meet here on a weekly rhythm.
          </li>
          <li>
            The same Gabrielle-Roth-wave lineage that grounds{" "}
            <Link
              href="/people/rhythm-sanctuary"
              className="text-primary hover:underline"
            >
              Rhythm Sanctuary
            </Link>{" "}
            (Wheat Ridge) and{" "}
            <Link
              href="/people/5rhythms-ubud"
              className="text-primary hover:underline"
            >
              5Rhythms Ubud
            </Link>{" "}
            — three Colorado-and-Bali rooms holding the same
            substrate practice.
          </li>
          <li>
            Sunday-morning rhythm as substrate-teaching: the
            steady tend of one floor over years is more
            substantial than any single event. Pairs with{" "}
            <Link
              href="/vision/lc-tending-over-producing"
              className="text-primary hover:underline"
            >
              lc-tending-over-producing
            </Link>
            .
          </li>
        </ul>
      ),
    },
  ],
  footer: (
    <>
      <p>
        <strong>In-body record:</strong>{" "}
        <Link href="/people/bloomurian" className="text-primary hover:underline">
          Bloomurian
        </Link>
        {" · "}
        <Link href="/people/aly-constantine" className="text-primary hover:underline">
          Aly Constantine
        </Link>
        {" · "}
        <Link href="/people/gabrielle-roth" className="text-primary hover:underline">
          Gabrielle Roth
        </Link>
        {" · "}
        <Link href="/people/rhythm-sanctuary" className="text-primary hover:underline">
          Rhythm Sanctuary
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
