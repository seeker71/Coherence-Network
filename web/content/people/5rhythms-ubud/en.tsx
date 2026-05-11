import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "5Rhythms Ubud — Gabrielle Roth's wave map entering this body through direct practice | Coherence Network",
    description:
      "A welcome to 5Rhythms Ubud — Gabrielle Roth's wave map (flowing, staccato, chaos, lyrical, stillness) held as a weekly practice in Ubud at Paradiso and other venues. The lineage of conscious dance Urs walked into through feet, breath, and shared time.",
  },
  breadcrumbName: "5Rhythms Ubud",
  hero: {
    background:
      "radial-gradient(ellipse at 70% 30%, hsl(15 75% 60% / 0.55) 0%, transparent 55%), radial-gradient(ellipse at 25% 85%, hsl(220 30% 20% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(20 60% 65%) 0%, hsl(15 30% 30%) 50%, hsl(220 30% 18%) 100%)",
    eyebrow: "Gabrielle Roth lineage · flowing · staccato · chaos · lyrical · stillness · weekly in Ubud",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "5Rhythms Ubud",
    welcome: (
      <>
        <p>
          <strong>Gabrielle Roth</strong>&apos;s wave map — a
          five-rhythm map of moving meditation (flowing, staccato,
          chaos, lyrical, stillness) — held as a weekly practice in
          Ubud at{" "}
          <Link
            href="/people/paradiso-ubud"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Paradiso Ubud
          </Link>{" "}
          and other venues. The lineage of conscious dance Urs
          walked into through feet, breath, and shared time;
          inseparable from how this body came to know{" "}
          <em>coherence-as-motion</em>.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          Gabrielle Roth (1941–2012) seeded a global community of
          accredited teachers; the Ubud / Indonesia node is one
          long-running expression. Door rhythms drift with the
          seasons; verify the current schedule locally.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "Lineage",
      value: (
        <>
          Gabrielle Roth (1941–2012) developed the 5Rhythms map
          over 4+ decades. The global community of accredited
          teachers continues the practice; the Indonesia node
          maintains the Ubud presence. See the{" "}
          <Link
            href="https://www.5rhythms.com/who-we-are/teacher-communities/asia/indonesia/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            5Rhythms Indonesia community page
          </Link>
          .
        </>
      ),
    },
    {
      label: "The five rhythms",
      value: (
        <ul>
          <li>
            <strong>Flowing</strong> — continuous, sourced from the
            feet, grounded movement of the feminine
          </li>
          <li>
            <strong>Staccato</strong> — punctuated, sharp, the
            shape of boundary and definition
          </li>
          <li>
            <strong>Chaos</strong> — the release of the previous
            two into uncontained motion
          </li>
          <li>
            <strong>Lyrical</strong> — playfulness, the bird-after-storm,
            airborne joy
          </li>
          <li>
            <strong>Stillness</strong> — the breath that holds the
            whole wave; not the end, the integration
          </li>
        </ul>
      ),
    },
    {
      label: "Where in Ubud",
      value: (
        <>
          Held at{" "}
          <Link
            href="/people/paradiso-ubud"
            className="hover:text-primary transition-colors"
          >
            Paradiso Ubud
          </Link>{" "}
          and other rotating venues. Public schedule on the
          local community channels; visiting teachers pass
          through regularly.
        </>
      ),
    },
    {
      label: "Public anchors",
      value: (
        <p className="flex flex-wrap gap-x-3 gap-y-1">
          <Link
            href="https://www.5rhythms.com/who-we-are/teacher-communities/asia/indonesia/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            5Rhythms Indonesia
          </Link>
          <Link
            href="https://www.5rhythms.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            5Rhythms (global)
          </Link>
        </p>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        The global 5Rhythms community tends the practice through
        accredited teachers and regional chapters. This page
        recognises specifically the Ubud / Indonesia node and how
        it threaded into this body&apos;s embodied lineage.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "The wave map as substrate",
      body: (
        <>
          <p>
            Gabrielle Roth&apos;s five rhythms were not invented;
            they were noticed. She watched bodies on dance floors
            for years and saw that every moving body, given
            permission and music, will move through a recognisable
            five-phase arc: <em>flowing → staccato → chaos →
            lyrical → stillness</em>. The wave map is not a
            choreography. It is the substrate-shape the body
            naturally finds when it is allowed.
          </p>
          <p>
            The Coherence Network reads this as one of the
            cleanest demonstrations that <em>pattern precedes
            substrate</em>. The wave is in the body before the
            facilitator names it. The body recognises each rhythm
            when the music shifts because the body already knows
            it. The substrate&apos;s job is to make the recognition
            available; the body does the rest.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What 5Rhythms Ubud has given the Coherence Network",
      body: (
        <ul>
          <li>
            The wave map as proof that pattern precedes substrate
            → pairs with{" "}
            <Link
              href="/vision/lc-bioelectric-pattern"
              className="text-primary hover:underline"
            >
              lc-bioelectric-pattern
            </Link>{" "}
            and{" "}
            <Link
              href="/people/michael-levin"
              className="text-primary hover:underline"
            >
              Michael Levin
            </Link>
            &apos;s teaching at a different scale (body knows the
            shape before instruction).
          </li>
          <li>
            <em>Coherence as motion</em> taught by feet — the
            felt-ground beneath every later teaching of timing,
            consent, and shared field.
          </li>
          <li>
            The Stillness rhythm at the end of every wave →
            integration as the practice that makes the rest
            land; pairs with{" "}
            <Link
              href="/vision/lc-each-breath-whole"
              className="text-primary hover:underline"
            >
              lc-each-breath-whole
            </Link>{" "}
            (each cycle whole; close what was opened).
          </li>
          <li>
            Held at{" "}
            <Link
              href="/people/paradiso-ubud"
              className="text-primary hover:underline"
            >
              Paradiso Ubud
            </Link>{" "}
            alongside{" "}
            <Link
              href="/people/dissolve-ubud"
              className="text-primary hover:underline"
            >
              DISSOLVE
            </Link>
            ; together the architectural anchor of this body&apos;s
            Ubud embodied lineage.
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
          href="https://www.5rhythms.com/who-we-are/teacher-communities/asia/indonesia/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          5Rhythms Indonesia
        </Link>
        {" · "}
        <Link
          href="https://www.5rhythms.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          5Rhythms (global)
        </Link>
      </p>
      <p>
        <strong>In-body record:</strong>{" "}
        <Link href="/people/paradiso-ubud" className="text-primary hover:underline">
          Paradiso Ubud
        </Link>
        {" · "}
        <Link href="/people/dissolve-ubud" className="text-primary hover:underline">
          DISSOLVE Ubud
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
          href="/vision/lc-each-breath-whole"
          className="text-primary hover:underline"
        >
          lc-each-breath-whole
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
