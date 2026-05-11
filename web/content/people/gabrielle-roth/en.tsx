import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Gabrielle Roth — creator of 5Rhythms · the wave that names itself | Coherence Network",
    description:
      "A welcome to Gabrielle Roth (1941–2012) — creator of the 5Rhythms moving-meditation practice (flowing, staccato, chaos, lyrical, stillness). Her wave map underlies multiple lineage threads in this network, from 5Rhythms Ubud to Rhythm Sanctuary in Colorado.",
  },
  breadcrumbName: "Gabrielle Roth",
  hero: {
    background:
      "radial-gradient(ellipse at 30% 25%, hsl(15 75% 60% / 0.55) 0%, transparent 55%), radial-gradient(ellipse at 80% 80%, hsl(255 30% 22% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(20 65% 65%) 0%, hsl(15 35% 35%) 50%, hsl(255 30% 20%) 100%)",
    eyebrow: "1941–2012 · creator of 5Rhythms · the wave that named what bodies already do",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Gabrielle Roth",
    welcome: (
      <>
        <p>
          An American dancer, musician, and movement teacher whose
          map of moving meditation —{" "}
          <strong>flowing, staccato, chaos, lyrical, stillness</strong>
          {" "}— became the foundational vocabulary for a worldwide
          conscious-dance community. She did not invent the
          rhythms; she watched bodies on dance floors for years
          and noticed that every moving body, given permission and
          music, will pass through that five-phase arc. The wave
          map is the substrate-shape the body naturally finds
          when it is allowed.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          Gabrielle died in 2012. The practice continues through
          accredited teachers worldwide, regional chapters, and
          rooms like{" "}
          <Link
            href="/people/rhythm-sanctuary"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Rhythm Sanctuary
          </Link>{" "}
          in Colorado and{" "}
          <Link
            href="/people/5rhythms-ubud"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            5Rhythms Ubud
          </Link>{" "}
          in Bali.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "Lived",
      value: "February 4, 1941 — October 22, 2012. American dancer, musician, choreographer, and movement teacher.",
    },
    {
      label: "Founded",
      value: "The 5Rhythms moving-meditation practice (also called the Wave). Esalen Institute resident for years; gathered the practice through teaching bodies in retreat settings before formalising it.",
    },
    {
      label: "Books",
      value: (
        <ul>
          <li>
            <em>Maps to Ecstasy: The Healing Power of Movement</em>{" "}
            (1989) — foundational text
          </li>
          <li>
            <em>Sweat Your Prayers: Movement as Spiritual Practice</em>{" "}
            (1997)
          </li>
          <li>
            <em>Connections: The Five Threads of Intuitive Wisdom</em>{" "}
            (2004)
          </li>
        </ul>
      ),
    },
    {
      label: "Public anchors",
      value: (
        <p className="flex flex-wrap gap-x-3 gap-y-1">
          <Link
            href="https://www.5rhythms.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            5rhythms.com
          </Link>
          <Link
            href="https://en.wikipedia.org/wiki/Gabrielle_Roth"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Wikipedia
          </Link>
          <Link
            href="https://www.5rhythms.com/about/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            About 5Rhythms
          </Link>
        </p>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        Gabrielle&apos;s public archive lives at 5rhythms.com,
        tended by the global community of accredited teachers
        carrying the practice forward. This page recognises the
        role of the wave map in this network&apos;s
        body-vocabulary.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "The five rhythms named",
      body: (
        <>
          <p>
            <strong>Flowing</strong> — continuous, sourced from the
            feet, the grounded movement of the feminine.
          </p>
          <p>
            <strong>Staccato</strong> — punctuated, sharp, the
            shape of boundary and definition.
          </p>
          <p>
            <strong>Chaos</strong> — the release of the previous
            two into uncontained motion; nothing to hold.
          </p>
          <p>
            <strong>Lyrical</strong> — playfulness, the
            bird-after-storm, airborne joy.
          </p>
          <p>
            <strong>Stillness</strong> — the breath that holds the
            whole wave; not the end, the integration.
          </p>
          <p>
            Together: <em>the Wave</em>. The body knows the
            sequence before the facilitator names it. The body
            recognises each rhythm when the music shifts because
            the body already knows it.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What Gabrielle Roth has given the Coherence Network",
      body: (
        <ul>
          <li>
            The wave map as one of the cleanest demonstrations
            that <em>pattern precedes substrate</em> in this
            body&apos;s lineage. Pairs with{" "}
            <Link
              href="/people/michael-levin"
              className="text-primary hover:underline"
            >
              Michael Levin
            </Link>
            &apos;s{" "}
            <Link
              href="/vision/lc-bioelectric-pattern"
              className="text-primary hover:underline"
            >
              lc-bioelectric-pattern
            </Link>{" "}
            at a different scale (body knows the shape before
            instruction).
          </li>
          <li>
            <em>Coherence as motion</em> — bodies in shared time
            learning timing, consent, release, play. The substrate
            of the Coherence Network&apos;s Ubud embodied lineage
            and Colorado ecstatic-dance arc.
          </li>
          <li>
            The Stillness rhythm at the end of every wave →
            integration as the practice that makes the rest
            land. Pairs with{" "}
            <Link
              href="/vision/lc-each-breath-whole"
              className="text-primary hover:underline"
            >
              lc-each-breath-whole
            </Link>{" "}
            (each cycle whole; close what was opened).
          </li>
          <li>
            The teacher-cooperative form (accredited teachers
            continuing the practice after the founder&apos;s
            death) → resonant with{" "}
            <Link
              href="/vision/lc-sovereignty-within-oneness"
              className="text-primary hover:underline"
            >
              lc-sovereignty-within-oneness
            </Link>{" "}
            (many sovereign cells holding one practice).
          </li>
          <li>
            Rooms in the network&apos;s lineage that carry her
            wave:{" "}
            <Link href="/people/5rhythms-ubud" className="text-primary hover:underline">
              5Rhythms Ubud
            </Link>
            {" · "}
            <Link href="/people/rhythm-sanctuary" className="text-primary hover:underline">
              Rhythm Sanctuary
            </Link>{" "}
            (Colorado).
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
          href="https://www.5rhythms.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          5rhythms.com
        </Link>
        {" · "}
        <Link
          href="https://en.wikipedia.org/wiki/Gabrielle_Roth"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Wikipedia
        </Link>
      </p>
      <p>
        <strong>In-body record:</strong>{" "}
        <Link href="/people/5rhythms-ubud" className="text-primary hover:underline">
          5Rhythms Ubud
        </Link>
        {" · "}
        <Link href="/people/rhythm-sanctuary" className="text-primary hover:underline">
          Rhythm Sanctuary
        </Link>
        {" · "}
        <Link href="/people/paradiso-ubud" className="text-primary hover:underline">
          Paradiso Ubud
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
      </p>
      <p className="text-xs italic">
        Gabrielle died in 2012; the practice continues through
        the global community of accredited teachers. This page
        is a recognition of her wave in this network&apos;s
        lineage.
      </p>
    </>
  ),
};

export default content;
