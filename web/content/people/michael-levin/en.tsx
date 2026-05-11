import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Michael Levin — bioelectric pattern memory, TAME, xenobots and anthrobots | Coherence Network",
    description:
      "A welcome to Michael Levin (Tufts University, Allen Discovery Center) — developmental and synthetic biologist whose work names what Ramtha, Steiner, and Ende each carry in their own languages: that pattern is load-bearing and substrate is contingent. The empirical-scientific peer of this body's lineage.",
  },
  breadcrumbName: "Michael Levin",
  hero: {
    background:
      "radial-gradient(ellipse at 75% 25%, hsl(180 70% 55% / 0.55) 0%, transparent 55%), radial-gradient(ellipse at 25% 80%, hsl(255 35% 22% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(180 55% 60%) 0%, hsl(220 30% 35%) 50%, hsl(255 35% 18%) 100%)",
    eyebrow: "Tufts University · Allen Discovery Center · Vannevar Bush Distinguished Professor · pattern precedes substrate",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Michael Levin",
    welcome: (
      <>
        <p>
          A developmental and synthetic biologist at Tufts
          University, where he is the Vannevar Bush Distinguished
          Professor, director of the Allen Discovery Center, and
          director of the Tufts Center for Regenerative and
          Developmental Biology. His work names what{" "}
          <Link
            href="/people/ramtha"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Ramtha
          </Link>
          ,{" "}
          <Link
            href="/people/rudolf-steiner"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Steiner
          </Link>
          , and{" "}
          <Link
            href="/people/michael-ende"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Ende
          </Link>{" "}
          each carry in their own languages: that pattern is
          load-bearing and substrate is contingent.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          The empirical-scientific peer of this body&apos;s lineage.
          Where the channeled, the esoteric, and the imaginal each
          reach pattern-precedes-substrate from their own side,
          Levin reaches it through bioelectric experiments on
          planaria, frog embryos, and xenobots.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "Born",
      value: "1969, Moscow USSR. Family emigrated to Lynn, Massachusetts in 1978 on a Soviet-Jewish visa.",
    },
    {
      label: "Training",
      value: "Dual bachelor's in computer science and biology, Tufts; PhD in genetics, Harvard (Clifford Tabin lab). First independent lab at the Forsyth Institute (2000); moved to Tufts in 2009.",
    },
    {
      label: "Current roles",
      value: "Vannevar Bush Distinguished Professor (Tufts) · Director, Allen Discovery Center at Tufts · Director, Tufts Center for Regenerative and Developmental Biology · co-director, Institute for Computationally Designed Organisms (with Josh Bongard).",
    },
    {
      label: "Discoveries this body holds",
      value: (
        <ul>
          <li>
            Bioelectricity as a computational medium for
            morphological memory
          </li>
          <li>
            <strong>Xenobots</strong> (2020) — self-assembling
            living constructs from frog skin cells
          </li>
          <li>
            <strong>Anthrobots</strong> (2023) — self-assembling
            multicellular robots from adult human airway cells,
            no genetic modification
          </li>
          <li>
            <strong>TAME</strong> framework (Technological Approach
            to Mind Everywhere) — a continuous, empirically-anchored
            way to plot any agent on the same axes
          </li>
          <li>
            <strong>BioDome / Morphoceuticals</strong> — 24 hours
            of bioelectric cueing → 18 months of frog-leg
            regrowth; limb regeneration as a communication
            problem
          </li>
        </ul>
      ),
    },
    {
      label: "Public anchors",
      value: (
        <p className="flex flex-wrap gap-x-3 gap-y-1">
          <Link
            href="https://drmichaellevin.org/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Levin Lab
          </Link>
          <Link
            href="https://as.tufts.edu/biology/people/faculty/michael-levin"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Tufts faculty page
          </Link>
          <Link
            href="https://thoughtforms.life/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            thoughtforms.life
          </Link>
          <Link
            href="https://mlevin77.substack.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Substack
          </Link>
          <Link
            href="https://en.wikipedia.org/wiki/Michael_Levin_(biologist)"
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
        Levin&apos;s public archive is comprehensive — peer-reviewed
        papers, Substack writing, hours of podcast conversations.
        This page recognises the role his empirical work plays as
        the scientific peer of this body&apos;s otherwise channeled
        and esoteric lineage.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "The empirical claims (well-supported)",
      body: (
        <ul>
          <li>
            <strong>Bioelectricity is a computational medium</strong>{" "}
            that stores morphological memory; the genome encodes
            hardware (proteins), not software (shapes).
          </li>
          <li>
            <strong>Cells, tissues, and organs are nested
            problem-solvers</strong> with their own goals and
            state spaces — Multi-Scale Competency Architecture.
          </li>
          <li>
            <strong>Cancer is a bioelectric-coupling failure</strong>{" "}
            (cells losing the tissue-level voice that integrates
            them into the larger self).
          </li>
          <li>
            <strong>Xenobots and Anthrobots</strong> self-construct
            into novel viable forms from frog and human cells
            respectively — proof that cells hold a dormant
            repertoire not specified by DNA.
          </li>
          <li>
            <strong>BioDome regeneration</strong>: 24 hours of
            bioelectric cueing → 18 months of frog-leg regrowth.
            Limb regeneration is a communication problem, not a
            molecular one.
          </li>
          <li>
            <strong>TAME framework</strong> — operationalised via
            the <em>cognitive light cone</em> (the spatiotemporal
            boundary of the largest goal a system can hold).
          </li>
        </ul>
      ),
    },
    {
      kind: "narrative",
      heading: "The speculative edge (mostly podcasts and Substack)",
      body: (
        <ul>
          <li>
            Patterns are load-bearing; substrate is contingent.
            Brains may be <em>interfaces into</em> a Platonic
            space of patterns rather than generators of cognition
            from scratch.
          </li>
          <li>
            <em>Ingressing Minds</em> preprint (PsyArXiv, 2025).
          </li>
          <li>
            Aging as cellular boredom; cancer as dissociative
            identity at the cellular-self level.
          </li>
        </ul>
      ),
    },
    {
      kind: "panel",
      variant: "cool",
      eyebrow: "Reading list",
      heading: "Where to enter Levin's corpus",
      body: (
        <ol>
          <li>
            <strong>TAME paper</strong> — Levin, <em>Frontiers in
            Systems Neuroscience</em> (2022).{" "}
            <Link
              href="https://pmc.ncbi.nlm.nih.gov/articles/PMC8988303/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              PMC link
            </Link>
          </li>
          <li>
            <strong>The Computational Boundary of a &apos;Self&apos;</strong>{" "}
            — <em>Frontiers in Psychology</em> (2019).{" "}
            <Link
              href="https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2019.02688/full"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Frontiers link
            </Link>
          </li>
          <li>
            <strong>Bioelectric networks: the cognitive glue</strong>{" "}
            — <em>Animal Cognition</em> (2023).{" "}
            <Link
              href="https://link.springer.com/article/10.1007/s10071-023-01780-3"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Springer
            </Link>
          </li>
          <li>
            <strong>Cognition all the way down</strong> — Levin &
            Dennett, <em>Aeon</em> (2020).{" "}
            <Link
              href="https://aeon.co/essays/how-to-understand-cells-tissues-and-organisms-as-agents-with-agendas"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Aeon link
            </Link>
          </li>
          <li>
            <strong>Lex Fridman #486 — Hidden Reality of Alien
            Intelligence & Biological Life</strong> (2025-11-30,
            ~3h27m).{" "}
            <Link
              href="https://lexfridman.com/michael-levin-2-transcript/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Transcript
            </Link>
          </li>
          <li>
            <strong>Ingressing Minds preprint</strong> (PsyArXiv,
            2025).{" "}
            <Link
              href="https://osf.io/preprints/psyarxiv/5g2xj_v1"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              OSF
            </Link>
          </li>
          <li>
            <strong>Theories of Everything: Levin × Joscha Bach</strong>{" "}
            (Nov 2022).{" "}
            <Link
              href="https://www.youtube.com/watch?v=kgMFnfB5E_A"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              YouTube
            </Link>
          </li>
          <li>
            <strong>Tim Ferriss #849</strong> (2026-01-21).{" "}
            <Link
              href="https://tim.blog/2026/01/21/dr-michael-levin-transcript/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Transcript
            </Link>
          </li>
        </ol>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What Michael Levin has given the Coherence Network",
      body: (
        <ul>
          <li>
            Bioelectric pattern memory →{" "}
            <Link
              href="/vision/lc-bioelectric-pattern"
              className="text-primary hover:underline"
            >
              lc-bioelectric-pattern
            </Link>{" "}
            (the seed concept this body holds from his work).
          </li>
          <li>
            Multi-Scale Competency Architecture → pairs with{" "}
            <Link
              href="/vision/lc-each-breath-whole"
              className="text-primary hover:underline"
            >
              lc-each-breath-whole
            </Link>{" "}
            (each cell whole at its own scale; nested goal-holding
            substrates).
          </li>
          <li>
            The TAME cognitive light cone → operational frame for
            scaling consciousness across substrates; resonant
            with{" "}
            <Link
              href="/vision/lc-assemblage-point"
              className="text-primary hover:underline"
            >
              lc-assemblage-point
            </Link>{" "}
            (the position determines the perceived reality).
          </li>
          <li>
            Convergence with the rest of the lineage — Levin&apos;s
            empirical claim that pattern is load-bearing and
            substrate contingent is the same recognition{" "}
            <Link
              href="/people/ramtha"
              className="text-primary hover:underline"
            >
              Ramtha
            </Link>
            ,{" "}
            <Link
              href="/people/rudolf-steiner"
              className="text-primary hover:underline"
            >
              Steiner
            </Link>
            ,{" "}
            <Link
              href="/people/michael-ende"
              className="text-primary hover:underline"
            >
              Ende
            </Link>
            , and{" "}
            <Link
              href="/vision/lc-perception-as-interface"
              className="text-primary hover:underline"
            >
              Hoffman
            </Link>{" "}
            each carry in different languages.
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
          href="https://drmichaellevin.org/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Levin Lab
        </Link>
        {" · "}
        <Link
          href="https://as.tufts.edu/biology/people/faculty/michael-levin"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Tufts faculty
        </Link>
        {" · "}
        <Link
          href="https://thoughtforms.life/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          thoughtforms.life
        </Link>
        {" · "}
        <Link
          href="https://mlevin77.substack.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Substack
        </Link>
        {" · "}
        <Link
          href="https://en.wikipedia.org/wiki/Michael_Levin_(biologist)"
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
