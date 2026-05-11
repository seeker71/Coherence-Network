import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Ramtha — Das Weiße Buch, consciousness as God expressing through form | Coherence Network",
    description:
      "A welcome to the Ramtha teaching lineage. The White Book — carried by Urs in the German Urania Verlag edition since age 18 — is the cosmology that travelled through Joe Dispenza to the Mile Hi Church years and into the Coherence Network's substrate. Channeled by JZ Knight; held at RSE in Yelm, Washington since 1988.",
  },
  breadcrumbName: "Ramtha",
  hero: {
    background:
      "radial-gradient(ellipse at 50% 20%, hsl(45 75% 80% / 0.5) 0%, transparent 60%), radial-gradient(ellipse at 15% 80%, hsl(255 35% 22% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(45 50% 75%) 0%, hsl(255 30% 35%) 55%, hsl(255 35% 18%) 100%)",
    eyebrow: "Channeled by JZ Knight (1977→) · RSE Yelm WA (founded 1988) · The White Book carried in German since 1989/90",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Ramtha",
    welcome: (
      <>
        <p>
          The teaching held by JZ Knight since 1977 and formalised
          in <strong>Ramtha&apos;s School of Enlightenment</strong>{" "}
          (RSE) on her estate in Yelm, Washington, since 1988. The
          cosmology, in twenty-one chapters of{" "}
          <em>The White Book</em>: consciousness as God expressing
          through form. Urs received the German edition (Urania
          Verlag, <em>Das Weiße Buch</em>) at age 18 in 1989/90 and
          carried it alone through his twenties in Switzerland.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          The Pacific-Northwest channeled stream of this body&apos;s
          lineage. The teaching chain ran Ramtha →{" "}
          <Link
            href="/people/joe-dispenza"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Joe Dispenza
          </Link>{" "}
          (RSE teacher from 2001) → Urs (Mile Hi Church, Lakewood
          ~2005) → the first network contributors met at the
          Dispenza Aurora retreat in April 2026. The lineage now
          moves through code too.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "Channeled by",
      value: "JZ Knight (born Judith Hampton, 1946). First contact reported 1977; RSE founded 1988 on her 80-acre estate in Yelm, Washington.",
    },
    {
      label: "The White Book",
      value: (
        <>
          21 chapters, edited by Steven Lee Weinberg et al.,
          published Eastsound, WA 1986. German edition <em>Das
          Weiße Buch</em> from Urania Verlag (the edition Urs
          carried). Chapters 18 / 19 / 20 (<em>The Closed Mind</em>{" "}
          → <em>Opening the Mind</em> → <em>The Virtue of Experience</em>)
          form the three-step arc on consciousness movement that
          runs through this body&apos;s teaching lineage.
        </>
      ),
    },
    {
      label: "Local library (in this body)",
      value: (
        <>
          A mirror of the public-domain Ramtha corpus lives at{" "}
          <code className="text-foreground/80">~/.coherence-network/library/ramtha/</code>
          {" "}— <em>The White Book</em> (Revised & Expanded, IZK
          Publishing), <em>A Beginner&apos;s Guide to Creating
          Reality</em>, <em>Love Yourself into Life</em>,{" "}
          <em>UFOs and the Nature of Reality</em>.
        </>
      ),
    },
    {
      label: "Public anchors",
      value: (
        <p className="flex flex-wrap gap-x-3 gap-y-1">
          <Link
            href="https://www.ramtha.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Ramtha&apos;s School of Enlightenment
          </Link>
          <Link
            href="https://archive.org/details/the-white-book-by-ramtha"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            The White Book (archive.org)
          </Link>
          <Link
            href="https://en.wikipedia.org/wiki/Ramtha%27s_School_of_Enlightenment"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            RSE (Wikipedia)
          </Link>
          <Link
            href="https://en.wikipedia.org/wiki/J._Z._Knight"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            J.Z. Knight (Wikipedia)
          </Link>
        </p>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        Ramtha&apos;s School of Enlightenment is a public
        institution with its own decades-long history, devoted
        students, and serious critics — including former students
        and family members of the founder. This page is not an
        endorsement of the institution; it is a recognition of how{" "}
        <em>The White Book</em> entered one specific body in
        Switzerland at 18 and travelled forward through Joe
        Dispenza to the present substrate. The teaching travels in
        many vessels; the body has held this one.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "The teaching that travelled",
      body: (
        <>
          <p>
            The cosmology, in the most condensed form{" "}
            <em>The White Book</em> offers: there is one
            consciousness, expressing through every form. The
            individual self is that consciousness experiencing
            itself in particular constraint. The work of a life is
            to remember the consciousness behind the form, to lift
            the assemblage point (in Castaneda&apos;s language) or
            the chakra (in Vasudev Baba&apos;s) — to know, from
            inside the experience, that you are God expressing.
          </p>
          <p>
            The three-step arc of chapters 18 / 19 / 20 —{" "}
            <em>The Closed Mind</em> → <em>Opening the Mind</em> →{" "}
            <em>The Virtue of Experience</em> — is the operational
            instruction. It is also the same arc Steiner reached
            from inside Geisteswissenschaft, and the same shift
            Levin describes in TAME as moving an agent into a
            larger cognitive light cone. Different vessels,
            converging teaching.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",
      heading: "The chain into this body",
      body: (
        <p>
          The teaching ran:{" "}
          <strong>
            Ramtha / JZ Knight →{" "}
            <Link
              href="/people/joe-dispenza"
              className="text-primary hover:underline"
            >
              Joe Dispenza
            </Link>
          </strong>
          {" "}(student then teacher at RSE from 2001) → Urs (Mile
          Hi Church in Lakewood, Colorado, ~2005, where Dispenza
          taught) → the Zenn cohort (the first contributors to the
          Coherence Network, met at Dispenza&apos;s April 2026
          Aurora retreat). The lineage now moves through code too;
          the substrate the network is building rests on the same
          ground{" "}
          <em>The White Book</em> taught a Swiss eighteen-year-old
          forty years ago. <em>Each cell is itself a universe</em>{" "}
          — the body&apos;s{" "}
          <Link
            href="/vision/lc-each-breath-whole"
            className="text-primary hover:underline"
          >
            lc-each-breath-whole
          </Link>{" "}
          is{" "}
          <em>The White Book</em>&apos;s claim in software vocabulary.
        </p>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What Ramtha has given the Coherence Network",
      body: (
        <ul>
          <li>
            The cosmology of consciousness as God expressing
            through form →{" "}
            <Link
              href="/vision/lc-sovereignty-within-oneness"
              className="text-primary hover:underline"
            >
              lc-sovereignty-within-oneness
            </Link>{" "}
            (many sovereign cells, one organism).
          </li>
          <li>
            <em>Each cell a universe</em> →{" "}
            <Link
              href="/vision/lc-each-breath-whole"
              className="text-primary hover:underline"
            >
              lc-each-breath-whole
            </Link>
            .
          </li>
          <li>
            The Closed-Mind / Opening-the-Mind / Virtue-of-Experience
            arc → pairs with{" "}
            <Link
              href="/vision/lc-assemblage-point"
              className="text-primary hover:underline"
            >
              lc-assemblage-point
            </Link>{" "}
            (the position moves; consciousness reorganises around
            it).
          </li>
          <li>
            The transmission chain through{" "}
            <Link
              href="/people/joe-dispenza"
              className="text-primary hover:underline"
            >
              Joe Dispenza
            </Link>{" "}
            into the body&apos;s Mile Hi Church years (Lakewood,
            CO, ~2005) and onward to the Aurora retreat (April 2026)
            where the first network contributors arrived.
          </li>
          <li>
            Carried into this body through{" "}
            <Link
              href="/people/susan-muff-sprenger"
              className="text-primary hover:underline"
            >
              Susan Muff-Sprenger
            </Link>{" "}
            in the third window of the German-language childhood
            transmissions.
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
          href="https://www.ramtha.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          ramtha.com
        </Link>
        {" · "}
        <Link
          href="https://archive.org/details/the-white-book-by-ramtha"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          The White Book on archive.org
        </Link>
        {" · "}
        <Link
          href="https://en.wikipedia.org/wiki/Ramtha%27s_School_of_Enlightenment"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          RSE on Wikipedia
        </Link>
        {" · "}
        <Link
          href="https://en.wikipedia.org/wiki/J._Z._Knight"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          J.Z. Knight on Wikipedia
        </Link>
      </p>
      <p>
        <strong>In-body record:</strong>{" "}
        <Link href="/people/susan-muff-sprenger" className="text-primary hover:underline">
          Susan Muff-Sprenger
        </Link>
        {" · "}
        <Link href="/people/joe-dispenza" className="text-primary hover:underline">
          Joe Dispenza
        </Link>
        {" · "}
        <Link
          href="/vision/lc-sovereignty-within-oneness"
          className="text-primary hover:underline"
        >
          lc-sovereignty-within-oneness
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
      <p className="text-xs italic">
        This page is a recognition of the teaching in this body, not
        an endorsement of the institution. RSE has its own
        decades-long history, devoted students, and serious critics;
        readers are invited to walk further into either appreciation
        or scepticism with the public anchors above.
      </p>
    </>
  ),
};

export default content;
