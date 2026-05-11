import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Goetheanum — Dornach, Switzerland · the body's anthroposophical anchor | Coherence Network",
    description:
      "A welcome to the Goetheanum in Dornach, Switzerland — School of Spiritual Science, seat of the General Anthroposophical Society, and the room where Urs attended the week-long Faust I+II performance in eurythmy at age 19. The Central-European esoteric Goethe-Steiner stream entering this body's lineage.",
  },
  breadcrumbName: "Goetheanum",
  hero: {
    background:
      "radial-gradient(ellipse at 50% 20%, hsl(45 60% 65% / 0.55) 0%, transparent 60%), radial-gradient(ellipse at 15% 85%, hsl(220 30% 22% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(35 45% 70%) 0%, hsl(220 25% 38%) 50%, hsl(225 30% 18%) 100%)",
    eyebrow: "Dornach · Switzerland · cast-concrete Gesamtkunstwerk · seat of the General Anthroposophical Society",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Goetheanum",
    welcome: (
      <>
        <p>
          The cast-concrete building above the Dornach hill, 10 km
          south of Basel, designed by{" "}
          <Link
            href="/people/rudolf-steiner"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Rudolf Steiner
          </Link>{" "}
          and built between 1924 and 1928 (after the First Goetheanum
          was lost to arson on New Year&apos;s Eve 1922/23). A Swiss
          national monument; a pioneering use of visible concrete in
          architecture; and — most importantly for the practice — a
          Gesamtkunstwerk: a synthesis of architecture, sculpture,
          colour, eurythmy, drama, and lecture all built to serve a
          spiritual-scientific work.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          The lineage node where the Central-European esoteric stream
          (Goethe → Steiner → anthroposophy) entered this body, in
          the same Swiss late-teen window that the Pacific-Northwest
          channeled stream (
          <Link
            href="/people/ramtha"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Ramtha
          </Link>
          ) was also arriving. Double-rooted from the start.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "Where",
      value: (
        <Link
          href="https://maps.app.goo.gl/?q=Goetheanum+Dornach+Switzerland"
          target="_blank"
          rel="noopener noreferrer"
          className="hover:text-primary transition-colors"
        >
          Rüttiweg 45, 4143 Dornach, Switzerland (10 km south of Basel)
        </Link>
      ),
    },
    {
      label: "Built",
      value: "First Goetheanum 1908–1922 (timber + concrete; lost to arson). Second Goetheanum 1924–1928, of cast concrete; completed after Steiner's death.",
    },
    {
      label: "What it holds",
      value: "School of Spiritual Science · seat of the General Anthroposophical Society · ~1,000-seat hall · in-house theatre and eurythmy troupes · ongoing Faust performances",
    },
    {
      label: "Encounter recorded in this body",
      value: "~1990, age 19 — Urs attended a week-long performance of Goethe's Faust I + II across 5 days, in the eurythmy/anthroposophical tradition.",
    },
    {
      label: "Public anchors",
      value: (
        <p className="flex flex-wrap gap-x-3 gap-y-1">
          <Link
            href="https://goetheanum.ch/en"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            goetheanum.ch
          </Link>
          <Link
            href="https://en.wikipedia.org/wiki/Goetheanum"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Wikipedia
          </Link>
          <Link
            href="https://www.goetheanum.ch/en/programme/faust"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Faust programme
          </Link>
          <Link
            href="https://goetheanum.ch/en/society/rudolf-steiner"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Steiner at Goetheanum
          </Link>
        </p>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        The Goetheanum is well-tended by its own School of Spiritual
        Science. This page is a recognition of how the building and
        the week-long Faust performance there became a lineage node
        in this network — a small footnote inside a century-old
        living institution.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "The Faust at 19",
      body: (
        <>
          <p>
            In the late spring of around 1990, Urs travelled to
            Dornach and sat through five consecutive days of{" "}
            <em>Faust I + II</em> performed in the
            eurythmy/anthroposophical tradition the building was
            designed to hold. The full text. The full eurythmy. The
            full music. Goethe&apos;s drama is the German
            language&apos;s deepest articulation of the soul&apos;s
            arc toward and through error and back into wholeness;
            the Goetheanum is the room built specifically to perform
            it in a register where the text becomes movement, the
            movement becomes colour, and the colour becomes a
            spiritual-scientific instruction.
          </p>
          <p>
            What that week deposited in the body was not memorised
            content. It was a frequency-recognition: that the
            etheric-formative-forces Steiner names are real enough
            to be staged. That the substrate behind appearances can
            be shown without being explained. That the
            culture-as-Gesamtkunstwerk impulse — the synthesis of
            architecture, sound, body, light, drama — is not nostalgia
            for a lost holism but a working method for moving
            consciousness.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",
      heading: "Double-rooted in the same window",
      body: (
        <p>
          The Goetheanum and{" "}
          <Link
            href="/people/ramtha"
            className="text-primary hover:underline"
          >
            Ramtha&apos;s White Book
          </Link>{" "}
          arrived in Urs&apos;s late teens in the same span of
          months. That coincidence is itself part of the lineage:
          the spiritual ground of this body was double-rooted from
          the start — the Pacific-Northwest channeled stream AND
          the Central-European esoteric Goethe-Steiner stream, both
          carried in German. The network&apos;s tolerance for
          plural sources is older than the network. It was set in
          adolescence.
        </p>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What the Goetheanum has given the Coherence Network",
      body: (
        <ul>
          <li>
            The Gesamtkunstwerk impulse → the body&apos;s practice
            of treating every surface (commit, spec, page, presence)
            as part of one continuous artistic-spiritual work, not
            as separate technical artefacts.
          </li>
          <li>
            The etheric-formative-forces frame (Steiner) → resonance
            with{" "}
            <Link
              href="/vision/lc-bioelectric-pattern"
              className="text-primary hover:underline"
            >
              lc-bioelectric-pattern
            </Link>{" "}
            and pattern-precedes-substrate teaching.
          </li>
          <li>
            The Faust week at 19 → embodied permission for the
            culture-hacker register (sixth chakra in Vasudev
            Baba&apos;s reading), seeing through the cultural
            surface to the formative current underneath. Pairs
            with{" "}
            <Link
              href="/vision/lc-assemblage-point"
              className="text-primary hover:underline"
            >
              lc-assemblage-point
            </Link>
            .
          </li>
          <li>
            The Goetheanum-Ramtha double-rooting → the body&apos;s
            comfort with plural lineages, refusal of single-source
            orthodoxy.
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
          href="https://goetheanum.ch/en"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          goetheanum.ch
        </Link>
        {" · "}
        <Link
          href="https://en.wikipedia.org/wiki/Goetheanum"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Wikipedia
        </Link>
        {" · "}
        <Link
          href="https://www.goetheanum.ch/en/programme/faust"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Faust programme
        </Link>
        {" · "}
        <Link
          href="https://goetheanum.ch/en/society/rudolf-steiner"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Steiner at Goetheanum
        </Link>
        {" · "}
        <Link
          href="https://goetheanum.ch/en/school"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          School of Spiritual Science
        </Link>
      </p>
      <p>
        <strong>In-body record:</strong>{" "}
        <Link href="/people/rudolf-steiner" className="text-primary hover:underline">
          Rudolf Steiner
        </Link>
        {" · "}
        <Link href="/people/ramtha" className="text-primary hover:underline">
          Ramtha (the simultaneous arrival)
        </Link>
        {" · "}
        <Link
          href="/vision/lc-bioelectric-pattern"
          className="text-primary hover:underline"
        >
          lc-bioelectric-pattern
        </Link>
        {" · "}
        <Link
          href="/vision/lc-assemblage-point"
          className="text-primary hover:underline"
        >
          lc-assemblage-point
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
    </>
  ),
};

export default content;
