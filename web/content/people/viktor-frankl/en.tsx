import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Viktor Frankl — the gap between stimulus and response · Man's Search for Meaning | Coherence Network",
    description:
      "A welcome to Viktor Frankl (1905–1997) — Austrian psychiatrist, neurologist, Holocaust survivor, founder of logotherapy. Author of Man's Search for Meaning. The teaching of the gap between stimulus and response grounds lc-assemblage-point in this body's lineage.",
  },
  breadcrumbName: "Viktor Frankl",
  hero: {
    background:
      "radial-gradient(ellipse at 30% 25%, hsl(35 55% 65% / 0.55) 0%, transparent 55%), radial-gradient(ellipse at 80% 80%, hsl(220 30% 22% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(35 45% 70%) 0%, hsl(220 25% 38%) 50%, hsl(220 30% 18%) 100%)",
    eyebrow: "Vienna 1905 → Vienna 1997 · psychiatrist · Holocaust survivor · founder of logotherapy · the gap between stimulus and response",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Viktor Frankl",
    welcome: (
      <>
        <p>
          Austrian psychiatrist, neurologist, and Holocaust
          survivor whose 1946 book{" "}
          <em>Ein Psychologe erlebt das Konzentrationslager</em>{" "}
          (English: <em>Man&apos;s Search for Meaning</em>) has
          sold over 16 million copies in 50+ languages. Founder of{" "}
          <strong>logotherapy</strong> — the third Viennese school
          of psychotherapy (after Freud&apos;s psychoanalysis and
          Adler&apos;s individual psychology) — built around the
          observation that the search for meaning is humanity&apos;s
          primary motivational force.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          The teaching this body has inherited most directly:{" "}
          <em>Between stimulus and response there is a space.
          In that space is our power to choose our response. In
          our response lies our growth and our freedom.</em>{" "}
          The exact phrasing is contested in attribution, but the
          gap Frankl named from inside the camps is the
          phenomenological core of lc-assemblage-point.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "Lived",
      value: "26 March 1905, Vienna, Austria-Hungary — 2 September 1997, Vienna. Doctorates in medicine (1930) and philosophy (1948).",
    },
    {
      label: "The camps",
      value: "Theresienstadt (1942) · Auschwitz (1944) · Kaufering (Dachau subcamp) · Türkheim. Wife Tilly died at Bergen-Belsen; parents and brother also murdered. Frankl survived; his manuscript on logotherapy did not. He rewrote it after the war.",
    },
    {
      label: "Founded",
      value: "Logotherapy — the meaning-centered psychotherapy, the third Viennese school. Active practice at the Vienna Polyclinic of Neurology after the war; visiting professor at Harvard, Stanford, Dallas, Pittsburgh among many others.",
    },
    {
      label: "Foundational books",
      value: (
        <ul>
          <li>
            <em>Man&apos;s Search for Meaning</em> (1946; English
            1959) — most translated, most read; the camp memoir
            plus logotherapy primer
          </li>
          <li>
            <em>The Doctor and the Soul</em> (1946) — the academic
            foundation of logotherapy
          </li>
          <li>
            <em>The Unconscious God</em> (1948)
          </li>
          <li>
            <em>The Will to Meaning</em> (1969)
          </li>
        </ul>
      ),
    },
    {
      label: "Public anchors",
      value: (
        <p className="flex flex-wrap gap-x-3 gap-y-1">
          <Link
            href="https://www.viktorfrankl.org/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            viktorfrankl.org (Viktor Frankl Institut Wien)
          </Link>
          <Link
            href="https://en.wikipedia.org/wiki/Viktor_Frankl"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Wikipedia
          </Link>
        </p>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        Frankl&apos;s archive is tended by the Viktor Frankl
        Institut Wien. This page recognises the teaching as one
        of the foundational threads of this body&apos;s
        assemblage-point lineage — the phenomenological reading
        of choice as the seam between stimulus and response.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "What he named from inside",
      body: (
        <p>
          The teaching Frankl named most loudly came not from
          theory but from observation in the camps: that even in
          conditions where every other freedom had been taken,
          one freedom remained — <em>the last of the human
          freedoms — to choose one&apos;s attitude in any given
          set of circumstances, to choose one&apos;s own way.</em>{" "}
          What persists between what arrives at the body and what
          the body does next is a space. The phrasing{" "}
          <em>between stimulus and response there is a space —
          in that space is our power to choose our response — in
          our response lies our growth and our freedom</em> is
          often attributed to Frankl directly; attribution is
          contested, but the teaching is his. The body holds this
          as one of the cleanest formulations of the
          assemblage-point&apos;s movement: where perception
          locks, choice can intervene.
        </p>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What Viktor Frankl has given the Coherence Network",
      body: (
        <ul>
          <li>
            The gap between stimulus and response →{" "}
            <Link
              href="/vision/lc-assemblage-point"
              className="text-primary hover:underline"
            >
              lc-assemblage-point
            </Link>{" "}
            (where perception assembles reality and choice can
            move it).
          </li>
          <li>
            Logotherapy as <em>meaning is primary</em> → resonant
            with{" "}
            <Link
              href="/vision/lc-devotion-placement"
              className="text-primary hover:underline"
            >
              lc-devotion-placement
            </Link>{" "}
            (where am I actually placed; the body of evidence
            over words at decision edges).
          </li>
          <li>
            <em>Even in the camps</em> — the teaching born of
            extremity → grounds the body&apos;s practice of{" "}
            <Link
              href="/vision/lc-coherence-over-control"
              className="text-primary hover:underline"
            >
              lc-coherence-over-control
            </Link>{" "}
            (remain aligned while reality catches up; do not
            force).
          </li>
          <li>
            Phenomenological-philosophical peer of Castaneda&apos;s
            assemblage-point teaching from a completely different
            cultural side. See{" "}
            <Link href="/people/carlos-castaneda" className="text-primary hover:underline">
              Carlos Castaneda
            </Link>
            ,{" "}
            <Link href="/people/donald-hoffman" className="text-primary hover:underline">
              Donald Hoffman
            </Link>
            ,{" "}
            <Link href="/people/michael-levin" className="text-primary hover:underline">
              Michael Levin
            </Link>
            ,{" "}
            <Link href="/people/joe-dispenza" className="text-primary hover:underline">
              Joe Dispenza
            </Link>{" "}
            for the convergence of idioms.
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
          href="https://www.viktorfrankl.org/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Viktor Frankl Institut Wien
        </Link>
        {" · "}
        <Link
          href="https://en.wikipedia.org/wiki/Viktor_Frankl"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Wikipedia
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
          href="/vision/lc-coherence-over-control"
          className="text-primary hover:underline"
        >
          lc-coherence-over-control
        </Link>
        {" · "}
        <Link
          href="/vision/lc-devotion-placement"
          className="text-primary hover:underline"
        >
          lc-devotion-placement
        </Link>
        {" · "}
        <Link href="/people/carlos-castaneda" className="text-primary hover:underline">
          Carlos Castaneda
        </Link>
      </p>
      <p className="text-xs italic">
        Frankl died in 1997; his archive is tended by the Viktor
        Frankl Institut in Vienna. This page is a recognition of
        his teaching in this body, not a biography.
      </p>
    </>
  ),
};

export default content;
