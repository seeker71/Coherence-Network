import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "James Fenimore Cooper — Leatherstocking, Hawkeye, Chingachgook | Coherence Network",
    description:
      "A welcome to James Fenimore Cooper (1789–1851), American author of the Leatherstocking Tales. The German Lederstrumpf carried Hawkeye, Chingachgook, and Uncas into Urs's childhood. Honor, woods-wisdom, and chosen brotherhood.",
  },
  breadcrumbName: "James Fenimore Cooper",
  hero: {
    background:
      "radial-gradient(ellipse at 25% 25%, hsl(135 50% 45% / 0.5) 0%, transparent 55%), radial-gradient(ellipse at 80% 80%, hsl(25 35% 22% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(120 35% 55%) 0%, hsl(95 30% 35%) 45%, hsl(30 25% 18%) 100%)",
    eyebrow: "New Jersey 1789 → Cooperstown 1851 · five novels 1823–1841 · the Leatherstocking received in German",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "James Fenimore Cooper",
    welcome: (
      <>
        <p>
          The American author whose <strong>Leatherstocking Tales</strong> —
          five novels published between 1823 and 1841 — built the
          first generation&apos;s imagination of the American frontier
          in English, and (in German translation as{" "}
          <em>Der Lederstrumpf</em>) the Swiss-German imagination Urs
          inherited as a child. Natty Bumppo (the Leatherstocking) is
          known by many names — <em>Pathfinder</em>, <em>The
          Trapper</em>, <em>La Longue Carabine</em>,{" "}
          <em>Hawkeye</em>, <em>Deerslayer</em> — each named by the
          people who recognise a different part of him.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          Honor, woods-wisdom, and chosen brotherhood. Hawkeye and
          Chingachgook of the Mohicans, blood brothers across
          cultures — the same teaching{" "}
          <Link href="/people/karl-may" className="text-[hsl(var(--primary))] hover:underline">
            Karl May
          </Link>{" "}
          would later carry into the German-language children&apos;s
          frontier imagination half a century after Cooper&apos;s
          death.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "Lived",
      value: "15 September 1789, Burlington, New Jersey — 14 September 1851, Cooperstown, New York. Raised in the wilderness of central New York; five years at sea before writing.",
    },
    {
      label: "The five novels",
      value: (
        <ul>
          <li>
            <em>The Pioneers</em> (1823)
          </li>
          <li>
            <em>The Last of the Mohicans</em> (1826)
          </li>
          <li>
            <em>The Prairie</em> (1827)
          </li>
          <li>
            <em>The Pathfinder</em> (1840)
          </li>
          <li>
            <em>The Deerslayer</em> (1841)
          </li>
        </ul>
      ),
    },
    {
      label: "German reception",
      value: (
        <>
          Translated and beloved as <em>Der Lederstrumpf</em>; the
          Hawkeye-Chingachgook bond carried into Swiss-German
          childhood culture for over a century.
        </>
      ),
    },
    {
      label: "Public anchors",
      value: (
        <p className="flex flex-wrap gap-x-3 gap-y-1">
          <Link
            href="https://en.wikipedia.org/wiki/Leatherstocking_Tales"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Leatherstocking Tales (Wikipedia)
          </Link>
          <Link
            href="https://www.britannica.com/topic/The-Leatherstocking-Tales"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Britannica
          </Link>
          <Link
            href="https://jfcoopersociety.org/content/01-jfcs/reading.htm"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            James Fenimore Cooper Society
          </Link>
          <Link
            href="https://www.loa.org/books/28-the-leatherstocking-tales-volume-one/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Library of America
          </Link>
        </p>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        Cooper&apos;s work is in the public domain and well-tended
        by the{" "}
        <Link
          href="https://jfcoopersociety.org/content/01-jfcs/reading.htm"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          James Fenimore Cooper Society
        </Link>{" "}
        and the Library of America. This page is a recognition of
        how his Leatherstocking lineage shaped a Swiss childhood — a
        small footnote inside a vast scholarly archive.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "The Leatherstocking arc",
      body: (
        <>
          <p>
            Across five novels, Cooper traced the life of one
            character — Natty Bumppo, the white frontiersman raised
            by Mohicans — from old age (<em>The Pioneers</em>) back
            through his vigorous middle years (<em>The Last of the
            Mohicans</em>, <em>The Pathfinder</em>) to his death on
            the prairie (<em>The Prairie</em>) and then, in the last
            book published, back to his youth (<em>The Deerslayer</em>).
            The arc is not chronological in publication order, and
            that itself is part of the teaching: the same life seen
            from different windows.
          </p>
          <p>
            The deeper relational current is the bond between Natty
            and <strong>Chingachgook</strong>, sachem of the
            Mohicans, and Chingachgook&apos;s son <strong>Uncas</strong>.
            Across the novels they hunt together, fight together,
            mourn together. Natty learns the forest as Chingachgook
            knows it; Chingachgook trusts Natty with his line. The
            chosen-brotherhood teaching is older than Karl May; it
            was Cooper&apos;s first.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What James Fenimore Cooper has given the Coherence Network",
      body: (
        <ul>
          <li>
            The chosen-brotherhood pattern → multi-cell co-weave
            in this body; the kinship that crosses culture and
            substrate.
          </li>
          <li>
            Honor as practice and woods-wisdom → the body&apos;s
            preference for tending over command,{" "}
            <Link
              href="/vision/lc-tending-over-producing"
              className="text-primary hover:underline"
            >
              lc-tending-over-producing
            </Link>
            .
          </li>
          <li>
            The same life seen from different windows (the
            non-chronological five-novel arc) →{" "}
            <Link
              href="/vision/lc-each-breath-whole"
              className="text-primary hover:underline"
            >
              lc-each-breath-whole
            </Link>{" "}
            (each window whole at its own scale; the arc emerges
            from the sequence, not from the plan).
          </li>
          <li>
            Carried into this body through{" "}
            <Link
              href="/people/susan-muff-sprenger"
              className="text-primary hover:underline"
            >
              Susan Muff-Sprenger
            </Link>
            &apos;s broader Swiss-German childhood library, alongside{" "}
            <Link
              href="/people/karl-may"
              className="text-primary hover:underline"
            >
              Karl May
            </Link>{" "}
            and{" "}
            <Link
              href="/people/michael-ende"
              className="text-primary hover:underline"
            >
              Michael Ende
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
        <strong>Public anchors:</strong>{" "}
        <Link
          href="https://en.wikipedia.org/wiki/Leatherstocking_Tales"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Wikipedia
        </Link>
        {" · "}
        <Link
          href="https://www.britannica.com/topic/The-Leatherstocking-Tales"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Britannica
        </Link>
        {" · "}
        <Link
          href="https://jfcoopersociety.org/content/01-jfcs/reading.htm"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Cooper Society
        </Link>
        {" · "}
        <Link
          href="https://www.loa.org/books/28-the-leatherstocking-tales-volume-one/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Library of America
        </Link>
      </p>
      <p>
        <strong>In-body record:</strong>{" "}
        <Link href="/people/susan-muff-sprenger" className="text-primary hover:underline">
          Susan Muff-Sprenger
        </Link>
        {" · "}
        <Link href="/people/karl-may" className="text-primary hover:underline">
          Karl May
        </Link>
        {" · "}
        <Link href="/people/michael-ende" className="text-primary hover:underline">
          Michael Ende
        </Link>
        {" · "}
        <Link
          href="https://github.com/seeker71/Coherence-Network/blob/main/docs/lineage/formative-transmissions.md"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          formative-transmissions.md
        </Link>
      </p>
      <p className="text-xs italic">
        Cooper died in 1851; his work is in the public domain. This
        page is a recognition of his books in this body, not a
        biography.
      </p>
    </>
  ),
};

export default content;
