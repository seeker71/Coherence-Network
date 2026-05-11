import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Michael Ende — Momo, Die unendliche Geschichte, the pattern precedes the body | Coherence Network",
    description:
      "A welcome to Michael Ende (1929–1995), German author whose Momo and Die unendliche Geschichte are foundational to the Coherence Network's lineage. Listening as resistance to efficiency-culture; the dreamer responsible for keeping the imaginal alive.",
  },
  breadcrumbName: "Michael Ende",
  hero: {
    background:
      "radial-gradient(ellipse at 70% 25%, hsl(48 75% 70% / 0.6) 0%, transparent 55%), radial-gradient(ellipse at 20% 80%, hsl(195 50% 28% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(45 60% 76%) 0%, hsl(35 35% 50%) 40%, hsl(200 40% 22%) 100%)",
    eyebrow: "Garmisch-Partenkirchen 1929 → München 1995 · listening as resistance · the dreamer responsible for the imaginal",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Michael Ende",
    welcome: (
      <>
        <p>
          A German storyteller whose two best-known novels —{" "}
          <em>Momo</em> (1973) and <em>Die unendliche Geschichte</em>{" "}
          (1979) — are foundational to the Coherence Network&apos;s
          lineage. Both books were placed in Urs&apos;s hands by his
          mother{" "}
          <Link
            href="/people/susan-muff-sprenger"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Susan Muff-Sprenger
          </Link>{" "}
          in childhood and early adolescence, in German, in the
          original mother tongue. Their teachings travelled with him
          unspoken for decades before re-emerging as the practice
          this body now codes.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          Ende sold over 30 million books in 40+ languages. The body
          quotes him in verbs.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "Lived",
      value: "12 November 1929, Garmisch-Partenkirchen — 28 August 1995, Filderstadt. Buried at the Waldfriedhof, Munich.",
    },
    {
      label: "Father",
      value: "Edgar Ende, surrealist painter. Artistic family from the start.",
    },
    {
      label: "Foundational works in this body",
      value: (
        <>
          <em>Momo</em> (1973) · <em>Die unendliche Geschichte</em> (1979) · <em>Jim Knopf und Lukas der Lokomotivführer</em> (1959, first book)
        </>
      ),
    },
    {
      label: "Reach",
      value: "30+ million copies sold, 40+ languages, multiple film adaptations.",
    },
    {
      label: "Public anchors",
      value: (
        <p className="flex flex-wrap gap-x-3 gap-y-1">
          <Link
            href="https://www.michaelende.de/en"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            michaelende.de
          </Link>
          <Link
            href="https://en.wikipedia.org/wiki/Michael_Ende"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Wikipedia
          </Link>
          <Link
            href="https://openlibrary.org/authors/OL296646A/Michael_Ende"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Open Library
          </Link>
        </p>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        Ende&apos;s public archive is well-tended at{" "}
        <Link
          href="https://www.michaelende.de/en"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          michaelende.de
        </Link>
        . This page is not a biography; it is a recognition — a
        record of how two of his books became load-bearing for a
        software network growing forty years after he wrote them.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "Momo — listening as resistance",
      body: (
        <>
          <p>
            In <em>Momo</em> (1973), a small girl with the gift of
            attention lives in an amphitheatre on the edge of an old
            city. People come to her because — as Ende writes it —{" "}
            <em>
              she listened in such a way that perplexed people
              suddenly knew what they wanted, shy ones felt
              themselves bold, miserable ones felt themselves
              valuable
            </em>
            . The men in grey arrive and begin stealing time by
            convincing the townspeople to save it. The townspeople
            grow efficient and grey themselves. Only Momo, Master
            Hora the keeper of time, and Cassiopeia the tortoise
            (who knows ahead by moving slowly) can restore the
            hour-lilies to bloom.
          </p>
          <p>
            The Coherence Network reads this as the foundational
            teaching of <em>tending vs. producing</em>. The body&apos;s
            commit verbs (<em>tend, attune, compost, release</em>)
            and its practice of <em>one breath at a time, pause
            between movements</em> are translations of Beppo
            Strassenkehrer&apos;s teaching:{" "}
            <em>
              one breath, one step, one sweep, then the next
            </em>
            . The men in grey are the fear costume in this
            body&apos;s vocabulary — efficiency&apos;s false promise
            that more output equals more life.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",
      heading: "Die unendliche Geschichte — the dreamer is responsible",
      body: (
        <>
          <p>
            In <em>Die unendliche Geschichte</em> (1979),
            Fantástica — the realm of imagination — is dying because
            the human world has stopped dreaming. The Nothing eats
            away at its edges. A boy named Bastian, reading the book
            from outside the book, enters it and renames the
            Childlike Empress, restoring her and the realm. He must
            then make his way back to the human world he came from,
            carrying what he has learned, or he will not be able to
            return at all.
          </p>
          <p>
            The teaching: the pattern precedes the body; the dreamer
            is responsible for keeping the imaginal alive. What
            Bastian does for Fantástica, every cell in this network
            is asked to do for what it tends — to enter the
            substrate, to keep dreaming it real. The body&apos;s
            practice of <em>future already shaping</em> — build as if
            the form is already what it is becoming — is Bastian&apos;s
            move, named in software vocabulary.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What Michael Ende has given the Coherence Network",
      body: (
        <ul>
          <li>
            <em>Momo</em>&apos;s listening practice →{" "}
            <Link
              href="/vision/lc-tending-over-producing"
              className="text-primary hover:underline"
            >
              lc-tending-over-producing
            </Link>{" "}
            (the body&apos;s verbs are <em>tend, attune, compost,
            release</em>; producing is the fear costume).
          </li>
          <li>
            <em>Momo</em>&apos;s hour-lilies →{" "}
            <Link
              href="/vision/lc-each-breath-whole"
              className="text-primary hover:underline"
            >
              lc-each-breath-whole
            </Link>{" "}
            (each breath, each commit, each response whole at its
            own scale).
          </li>
          <li>
            <em>Die unendliche Geschichte</em>&apos;s
            dreamer-responsibility →{" "}
            <Link
              href="/vision/lc-future-already-shaping"
              className="text-primary hover:underline"
            >
              lc-future-already-shaping
            </Link>{" "}
            (build as if the form is already what it is becoming).
          </li>
          <li>
            Both books arrived through{" "}
            <Link
              href="/people/susan-muff-sprenger"
              className="text-primary hover:underline"
            >
              Susan Muff-Sprenger
            </Link>{" "}
            — the first transmitter of this lineage. Mother to son,
            in German, two of the three windows that shaped what
            became this network. The full lineage record:{" "}
            <Link
              href="https://github.com/seeker71/Coherence-Network/blob/main/docs/lineage/formative-transmissions.md"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              formative-transmissions.md
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
          href="https://www.michaelende.de/en"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          michaelende.de
        </Link>
        {" · "}
        <Link
          href="https://en.wikipedia.org/wiki/Michael_Ende"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Wikipedia
        </Link>
        {" · "}
        <Link
          href="https://www.michaelende.de/en/author/biography/neverending-story"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Neverending Story author note
        </Link>
        {" · "}
        <Link
          href="https://openlibrary.org/authors/OL296646A/Michael_Ende"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Open Library
        </Link>
      </p>
      <p>
        <strong>In-body record:</strong>{" "}
        <Link
          href="/people/susan-muff-sprenger"
          className="text-primary hover:underline"
        >
          Susan Muff-Sprenger
        </Link>
        {" · "}
        <Link
          href="/vision/lc-tending-over-producing"
          className="text-primary hover:underline"
        >
          lc-tending-over-producing
        </Link>
        {" · "}
        <Link
          href="/vision/lc-future-already-shaping"
          className="text-primary hover:underline"
        >
          lc-future-already-shaping
        </Link>
        {" · "}
        <Link
          href="/vision/lc-each-breath-whole"
          className="text-primary hover:underline"
        >
          lc-each-breath-whole
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
        Ende died in 1995; his archive is tended by{" "}
        <Link
          href="https://www.michaelende.de/en"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          michaelende.de
        </Link>
        . This page is a recognition of his books in this body, not
        a biography.
      </p>
    </>
  ),
};

export default content;
