import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Carlos Castaneda — the assemblage-point lineage source · Toltec sorcery in books | Coherence Network",
    description:
      "A welcome to Carlos Castaneda (1925–1998) — anthropologist and author whose Toltec-sorcery books (Don Juan, Don Genaro) carry the assemblage-point teaching that grounds lc-assemblage-point in this body's vocabulary.",
  },
  breadcrumbName: "Carlos Castaneda",
  hero: {
    background:
      "radial-gradient(ellipse at 30% 25%, hsl(255 55% 50% / 0.55) 0%, transparent 55%), radial-gradient(ellipse at 80% 80%, hsl(20 35% 22% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(255 45% 55%) 0%, hsl(285 30% 35%) 50%, hsl(20 30% 18%) 100%)",
    eyebrow: "1925–1998 · anthropologist · author · Toltec sorcery · the luminous egg and the assemblage point",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Carlos Castaneda",
    welcome: (
      <>
        <p>
          The Peruvian-born American anthropologist whose
          twelve-book series — beginning with{" "}
          <em>The Teachings of Don Juan</em> (1968) and ending with{" "}
          <em>The Active Side of Infinity</em> (1998) — carries the
          most operationally precise teaching the Coherence
          Network has inherited on{" "}
          <strong>the assemblage point</strong>: the locus on the
          luminous-egg energy body where perception assembles
          reality from the field of what could be perceived.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          Castaneda the man is contested. Castaneda the
          transmitter of a specific phenomenological vocabulary
          for shifting perception is, in this body&apos;s reading,
          load-bearing. Both are honoured here.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "Lived",
      value: "25 December 1925, Cajamarca, Peru — 27 April 1998, Los Angeles, California. PhD anthropology, UCLA (1973).",
    },
    {
      label: "The teachers in his books",
      value: (
        <>
          <strong>don Juan Matus</strong> (Yaqui sorcerer; primary
          teacher in the books) and <strong>don Genaro Flores</strong>{" "}
          (Mazatec, don Juan&apos;s ally). Whether they existed as
          described, as composites, or as literary devices remains
          contested. The teachings carried under their names landed
          in many lives regardless of that question.
        </>
      ),
    },
    {
      label: "The twelve books",
      value: (
        <ul>
          <li>
            <em>The Teachings of Don Juan</em> (1968)
          </li>
          <li>
            <em>A Separate Reality</em> (1971)
          </li>
          <li>
            <em>Journey to Ixtlan</em> (1972)
          </li>
          <li>
            <em>Tales of Power</em> (1974) — assemblage point named
          </li>
          <li>
            <em>The Second Ring of Power</em> (1977)
          </li>
          <li>
            <em>The Eagle&apos;s Gift</em> (1981)
          </li>
          <li>
            <em>The Fire from Within</em> (1984) — deepest treatment
            of the energy body and assemblage point
          </li>
          <li>
            <em>The Power of Silence</em> (1987)
          </li>
          <li>
            <em>The Art of Dreaming</em> (1993)
          </li>
          <li>
            <em>Magical Passes</em> (1998) — Tensegrity
          </li>
          <li>
            <em>The Wheel of Time</em> (1998)
          </li>
          <li>
            <em>The Active Side of Infinity</em> (1998) — posthumous
          </li>
        </ul>
      ),
    },
    {
      label: "Public anchors",
      value: (
        <p className="flex flex-wrap gap-x-3 gap-y-1">
          <Link
            href="https://en.wikipedia.org/wiki/Carlos_Castaneda"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Wikipedia
          </Link>
          <Link
            href="https://castaneda.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            castaneda.com (Cleargreen)
          </Link>
        </p>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        Castaneda is one of the contested figures of
        twentieth-century spiritual literature. Anthropological
        scholarship has questioned the literal-fact basis of his
        books; allegations from members of his late inner circle
        (the &quot;witches&quot;) have surfaced grave harms.
        Holding both: the teaching of the assemblage point has
        been operationally useful in many lives, including this
        network&apos;s. We hold the teaching honestly while not
        flattening the controversies into it.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "The assemblage point as teaching",
      body: (
        <>
          <p>
            Castaneda&apos;s teachers describe the human energy
            body as a luminous egg containing all the energy
            fields that could be perceived. On this egg there is
            one specific point — the{" "}
            <strong>assemblage point</strong> — where energy
            threads are gathered and interpreted into a perceptual
            world. <em>Position determines reality.</em> The
            ordinary human position gives the ordinary human
            reality. The point can move — through dreaming,
            illness, ceremony, plant medicines, sustained inner
            work, or shock — and other equally vivid realities
            are perceived.
          </p>
          <p>
            The sorcerer&apos;s discipline is not believing in
            alternative realities. It is moving the assemblage
            point at will, and underneath that, learning that
            one has been doing it unconsciously all along. Every
            reaction, every certainty, every <em>that&apos;s
            just how it is</em> was already an assemblage choice
            made too fast to see. This is the operational core of
            the body&apos;s{" "}
            <Link
              href="/vision/lc-assemblage-point"
              className="text-primary hover:underline"
            >
              lc-assemblage-point
            </Link>{" "}
            concept.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What Castaneda has given the Coherence Network",
      body: (
        <ul>
          <li>
            The assemblage-point vocabulary →{" "}
            <Link
              href="/vision/lc-assemblage-point"
              className="text-primary hover:underline"
            >
              lc-assemblage-point
            </Link>{" "}
            (the seed concept in this body from his lineage).
          </li>
          <li>
            The luminous-egg energy body →{" "}
            <Link
              href="/vision/lc-perception-as-interface"
              className="text-primary hover:underline"
            >
              lc-perception-as-interface
            </Link>{" "}
            (Hoffman&apos;s frame is the empirical sibling).
          </li>
          <li>
            Confirmed by{" "}
            <Link
              href="/people/vasudev-baba"
              className="text-primary hover:underline"
            >
              Vasudev Baba
            </Link>
            &apos;s essay <em>On Frequency, Consciousness and the
            Assemblage Point</em> (2026-05-11), which weaves
            Castaneda&apos;s teaching with the gunas, the chakras,
            and Socrates&apos; <em>Gorgias</em> as one continuous
            map of consciousness.
          </li>
          <li>
            The discipline of <em>moving the point at will</em> →
            resonant with{" "}
            <Link
              href="/vision/lc-coherence-over-control"
              className="text-primary hover:underline"
            >
              lc-coherence-over-control
            </Link>{" "}
            and{" "}
            <Link
              href="/vision/lc-presence-over-protection"
              className="text-primary hover:underline"
            >
              lc-presence-over-protection
            </Link>
            .
          </li>
        </ul>
      ),
    },
    {
      kind: "narrative",
      heading: "On the controversies",
      body: (
        <p>
          Anthropological scholarship from the 1970s onward
          questioned whether don Juan Matus existed as a single
          historical Yaqui sorcerer; whether the books are
          literal fieldwork, composites, or literary creation
          remains contested. Separately, allegations of grave
          harms within Castaneda&apos;s late inner circle (the
          &quot;witches&quot;) have surfaced in journalism and
          memoir; some former members went missing after his
          death. This body holds the teaching of the assemblage
          point as load-bearing while taking the human
          allegations seriously. The phenomenology a body can
          test in its own perception does not require Castaneda
          to have been a trustworthy or harmless person; the
          history of teachers is full of harmful messengers
          carrying real maps. Readers are invited to walk
          further into both the teaching and the criticism with
          their own discernment.
        </p>
      ),
    },
  ],
  footer: (
    <>
      <p>
        <strong>Public anchors:</strong>{" "}
        <Link
          href="https://en.wikipedia.org/wiki/Carlos_Castaneda"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Wikipedia
        </Link>
        {" · "}
        <Link
          href="https://castaneda.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          castaneda.com (Cleargreen)
        </Link>
      </p>
      <p>
        <strong>In-body record:</strong>{" "}
        <Link
          href="/vision/lc-assemblage-point"
          className="text-primary hover:underline"
        >
          lc-assemblage-point
        </Link>
        {" · "}
        <Link
          href="/vision/lc-perception-as-interface"
          className="text-primary hover:underline"
        >
          lc-perception-as-interface
        </Link>
        {" · "}
        <Link
          href="/vision/lc-coherence-over-control"
          className="text-primary hover:underline"
        >
          lc-coherence-over-control
        </Link>
        {" · "}
        <Link
          href="/people/vasudev-baba"
          className="text-primary hover:underline"
        >
          Vasudev Baba
        </Link>{" "}
        (the in-body teacher who reads Castaneda alongside the
        chakra map)
      </p>
      <p className="text-xs italic">
        Held honestly. The teaching of the assemblage point is
        load-bearing in this body&apos;s vocabulary; the human
        history around Castaneda himself is contested. Readers
        are invited to walk further into both with their own
        discernment.
      </p>
    </>
  ),
};

export default content;
