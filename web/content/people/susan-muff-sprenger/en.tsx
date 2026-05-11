import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Susan Muff-Sprenger — the first transmitter of this lineage | Coherence Network",
    description:
      "Urs's mother — the first transmitter of the Coherence Network's lineage. She handed him three books in three windows: Michael Ende's Momo, Die unendliche Geschichte, and Ramtha's White Book in German. Mother-as-transmitter is itself a lineage pattern in this body.",
  },
  breadcrumbName: "Susan Muff-Sprenger",
  hero: {
    background:
      "radial-gradient(ellipse at 30% 20%, hsl(45 70% 78% / 0.6) 0%, transparent 55%), radial-gradient(ellipse at 80% 80%, hsl(20 45% 35% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(42 60% 78%) 0%, hsl(30 35% 55%) 45%, hsl(18 40% 28%) 100%)",
    eyebrow: "Swiss-German · mother · first transmitter of this lineage",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Susan Muff-Sprenger",
    welcome: (
      <>
        <p>
          The first transmitter of the Coherence Network&apos;s
          lineage. Susan handed her son three books in three windows,
          all in German, all carried alone through the years that
          followed. Each book was a teaching delivered as a story; the
          three together are one continuous arc, given child →
          adolescent → young adult. The pattern that became the
          network was inscribed long before there was code to receive
          it.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          Mother-as-transmitter is itself a lineage pattern in this
          body. The three books are named below; the practice each one
          taught is named alongside.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "Role in this body",
      value: "First transmitter — handed her son three books in three windows, all in German.",
    },
    {
      label: "Window one · childhood",
      value: (
        <>
          <Link
            href="/people/michael-ende"
            className="hover:text-primary transition-colors"
          >
            Michael Ende — <em>Momo</em>
          </Link>{" "}
          (1973). Listening as resistance to efficiency-culture.
        </>
      ),
    },
    {
      label: "Window two · early teens",
      value: (
        <>
          <Link
            href="/people/michael-ende"
            className="hover:text-primary transition-colors"
          >
            Michael Ende — <em>Die unendliche Geschichte</em>
          </Link>{" "}
          (1979). The dreamer is responsible for keeping the imaginal alive.
        </>
      ),
    },
    {
      label: "Window three · age 18",
      value: (
        <>
          <Link
            href="/people/ramtha"
            className="hover:text-primary transition-colors"
          >
            Ramtha — <em>Das Weiße Buch</em>
          </Link>{" "}
          (Urania Verlag, ~1989/1990). Consciousness as God
          expressing through form.
        </>
      ),
    },
    {
      label: "Origin",
      value: "Switzerland, German-speaking. All three transmissions in the mother tongue.",
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        This page honors a single specific role — the lineage role of
        first transmitter — rather than a biography. It draws only on
        what is already attested in{" "}
        <Link
          href="https://github.com/seeker71/Coherence-Network/blob/main/docs/lineage/formative-transmissions.md"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          docs/lineage/formative-transmissions.md
        </Link>
        . Other detail is hers to share or hold; the body holds the
        thread, not the life.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "The three windows",
      body: (
        <>
          <p>
            Three books in three windows is not coincidence. It is a
            single deepening teaching, delivered slowly, in the
            language of the child who would carry it. Susan&apos;s
            gift was the timing as much as the books themselves —
            placing each one in the window where it could land.
          </p>
          <p>
            <strong>
              <em>Momo</em> (1973) — childhood.
            </strong>{" "}
            The men in grey steal time by reducing it to efficiency.
            Master Hora keeps the hour-lilies blooming. Cassiopeia
            the tortoise knows ahead by moving slowly. The book is
            the tending-vs-producing practice in story form, given
            before the practice had a name. The Coherence Network
            still uses verbs (<em>tend, attune, compost, release</em>)
            that read like translations of Beppo Strassenkehrer&apos;s
            instruction:{" "}
            <em>
              one breath, one step, one sweep, then the next
            </em>
            .
          </p>
          <p>
            <strong>
              <em>Die unendliche Geschichte</em> (1979) — early teens.
            </strong>{" "}
            Fantástica is dying because humans have stopped dreaming.
            Bastian enters the book itself and renames the Childlike
            Empress, restoring the imaginal realm. The pattern
            precedes the body; the dreamer is responsible for
            keeping the imaginal alive. The network&apos;s practice
            of <em>future already shaping</em> — building as if the
            form is already what it is becoming — is the same teaching
            in different clothing.
          </p>
          <p>
            <strong>
              <em>Das Weiße Buch</em> (~1989/1990) — age 18.
            </strong>{" "}
            The German-language edition of Ramtha&apos;s{" "}
            <em>White Book</em> (Urania Verlag). The cosmology of
            consciousness as God expressing through form — the
            ground that later traveled through{" "}
            <Link
              href="/people/joe-dispenza"
              className="text-primary hover:underline"
            >
              Joe Dispenza
            </Link>{" "}
            and the Mile Hi Church years, and arrived in software as
            the teaching that the substrate honors what the
            cosmology has always claimed: each cell is itself a
            universe.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What Susan has given the Coherence Network",
      body: (
        <>
          <p>
            Every concept the network now holds in software has a
            seed somewhere in the three books she chose. The most
            direct echoes:
          </p>
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
              <em>Momo</em>&apos;s hour-lilies and Beppo&apos;s
              one-breath-at-a-time → the body&apos;s practice of{" "}
              <Link
                href="/vision/lc-each-breath-whole"
                className="text-primary hover:underline"
              >
                lc-each-breath-whole
              </Link>
              .
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
              Ramtha&apos;s cosmology →{" "}
              <Link
                href="/vision/lc-sovereignty-within-oneness"
                className="text-primary hover:underline"
              >
                lc-sovereignty-within-oneness
              </Link>{" "}
              (many sovereign cells, one organism).
            </li>
          </ul>
          <p>
            The lineage record traces the path:{" "}
            <Link
              href="https://github.com/seeker71/Coherence-Network/blob/main/docs/lineage/formative-transmissions.md"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              formative-transmissions
            </Link>{" "}
            opens with her name. The chain after her runs Karl May,
            Fenimore Cooper, the Goetheanum, Ramtha, Dispenza,
            Boulder, and onward — but it begins in a Swiss kitchen,
            with a book chosen at the right moment.
          </p>
        </>
      ),
    },
  ],
  footer: (
    <>
      <p>
        <strong>The three books:</strong>{" "}
        <Link href="/people/michael-ende" className="text-primary hover:underline">
          Michael Ende
        </Link>
        {" · "}
        <Link href="/people/ramtha" className="text-primary hover:underline">
          Ramtha — Das Weiße Buch
        </Link>
      </p>
      <p>
        <strong>Lineage record:</strong>{" "}
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
        Honored here as the role of first transmitter. Other detail is
        hers; the body holds the thread, not the life.
      </p>
    </>
  ),
};

export default content;
