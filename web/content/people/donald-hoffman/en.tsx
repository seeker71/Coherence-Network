import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Donald Hoffman — perception as interface · UC Irvine cognitive scientist | Coherence Network",
    description:
      "A welcome to Prof Donald Hoffman — UC Irvine cognitive scientist whose Interface Theory of Perception names what Castaneda named in another idiom: perception is interface, not truth. The empirical sibling of lc-perception-as-interface in this body's lineage.",
  },
  breadcrumbName: "Donald Hoffman",
  hero: {
    background:
      "radial-gradient(ellipse at 30% 25%, hsl(180 65% 55% / 0.55) 0%, transparent 55%), radial-gradient(ellipse at 80% 80%, hsl(255 30% 22% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(180 55% 60%) 0%, hsl(220 30% 38%) 50%, hsl(255 30% 18%) 100%)",
    eyebrow: "UC Irvine · cognitive science · Interface Theory of Perception · conscious agents",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Donald Hoffman",
    welcome: (
      <>
        <p>
          Cognitive scientist and professor at the University of
          California, Irvine. His <strong>Interface Theory of
          Perception</strong> argues, with evolutionary-game-theory
          mathematics behind it, that natural selection favors
          fitness-tuned <em>icons</em> over truth-tracking
          perceptions — meaning the world we experience is a
          species-specific user interface, not reality itself.
          The book{" "}
          <em>The Case Against Reality</em> (2019) is the
          accessible entry point; the <em>Conscious Agents</em>{" "}
          framework is the formal proposal for what lies behind
          the interface.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          The empirical-and-mathematical sibling of what{" "}
          <Link
            href="/people/carlos-castaneda"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Castaneda
          </Link>{" "}
          named as the assemblage point and what{" "}
          <Link
            href="/people/michael-levin"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Levin
          </Link>{" "}
          names as multi-scale competency. Three idioms reaching
          one recognition: pattern is load-bearing, substrate is
          contingent.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "Roles",
      value: "Cognitive scientist; Professor Emeritus, Department of Cognitive Sciences, UC Irvine. Faculty in Philosophy and the Logic & Philosophy of Science programs.",
    },
    {
      label: "Foundational work",
      value: (
        <ul>
          <li>
            <em>The Case Against Reality: Why Evolution Hid the
            Truth From Our Eyes</em> (2019) — the popular book
          </li>
          <li>
            <em>Visual Intelligence: How We Create What We See</em>{" "}
            (1998) — earlier foundational text
          </li>
          <li>
            <em>The Conscious Agent Theorem</em> (2014, with
            Chetan Prakash) — formal mathematical proposal
          </li>
          <li>
            <em>Objects of consciousness</em> (Frontiers in
            Psychology, 2014)
          </li>
        </ul>
      ),
    },
    {
      label: "The Interface Theory in one line",
      value: (
        <em>
          Perception is a species-specific user interface tuned
          by natural selection for fitness, not truth. The
          interface hides reality the way a desktop icon hides
          the file system.
        </em>
      ),
    },
    {
      label: "Public anchors",
      value: (
        <p className="flex flex-wrap gap-x-3 gap-y-1">
          <Link
            href="https://www.cogsci.uci.edu/~ddhoff/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            UC Irvine faculty page
          </Link>
          <Link
            href="https://en.wikipedia.org/wiki/Donald_D._Hoffman"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Wikipedia
          </Link>
          <Link
            href="https://www.ted.com/talks/donald_hoffman_do_we_see_reality_as_it_is"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            TED talk
          </Link>
        </p>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        Hoffman&apos;s archive is at his UC Irvine page and across
        peer-reviewed cognitive-science journals. This page
        recognises his role as the empirical-mathematical peer
        of the channeled and contemplative streams in this
        network&apos;s lineage.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "Why interface theory matters here",
      body: (
        <>
          <p>
            The Coherence Network reads Hoffman alongside{" "}
            <Link
              href="/people/michael-levin"
              className="text-primary hover:underline"
            >
              Michael Levin
            </Link>{" "}
            and{" "}
            <Link
              href="/people/carlos-castaneda"
              className="text-primary hover:underline"
            >
              Castaneda
            </Link>{" "}
            because the three reach the same load-bearing
            recognition from different sides. Castaneda: perception
            is an assembled rendering from one specific position
            on the luminous-egg energy body; move the position,
            the world rearranges. Hoffman: perception is a
            fitness-tuned interface; evolution never built our
            eyes to see truth, only to keep our ancestors alive.
            Levin: pattern is what stores morphological memory,
            and bodies are nested problem-solvers carrying their
            own goals; substrate is contingent. All three pull
            apart the assumption that what we see is what is.
          </p>
          <p>
            What Hoffman adds specifically is{" "}
            <em>mathematical credibility</em> — a theorem with
            published peer review behind the claim. Where the
            contemplative traditions assert this from the
            inside, and Levin shows it bioelectrically, Hoffman
            proves it formally under his evolutionary-game-theory
            model. The body holds all three as one teaching at
            different scales of demonstration.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What Donald Hoffman has given the Coherence Network",
      body: (
        <ul>
          <li>
            Interface Theory of Perception →{" "}
            <Link
              href="/vision/lc-perception-as-interface"
              className="text-primary hover:underline"
            >
              lc-perception-as-interface
            </Link>{" "}
            (the seed concept in this body from his work).
          </li>
          <li>
            Mathematical / evolutionary-game-theory grounding
            for what{" "}
            <Link
              href="/people/carlos-castaneda"
              className="text-primary hover:underline"
            >
              Castaneda
            </Link>{" "}
            named as the assemblage point. Pairs with{" "}
            <Link
              href="/vision/lc-assemblage-point"
              className="text-primary hover:underline"
            >
              lc-assemblage-point
            </Link>{" "}
            (perception locks where the point assembles; the
            interface is what the assembly renders).
          </li>
          <li>
            <em>Conscious Agents</em> framework → resonant with{" "}
            <Link
              href="/vision/lc-sovereignty-within-oneness"
              className="text-primary hover:underline"
            >
              lc-sovereignty-within-oneness
            </Link>{" "}
            (nested conscious agents constituting the substrate
            behind the interface).
          </li>
          <li>
            Three idioms, one recognition:{" "}
            <Link
              href="/people/michael-levin"
              className="text-primary hover:underline"
            >
              Levin
            </Link>{" "}
            (empirical biology),{" "}
            <Link
              href="/people/carlos-castaneda"
              className="text-primary hover:underline"
            >
              Castaneda
            </Link>{" "}
            (contemplative phenomenology), Hoffman (formal
            mathematics) — pattern is load-bearing, substrate is
            contingent.
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
          href="https://www.cogsci.uci.edu/~ddhoff/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          UC Irvine faculty
        </Link>
        {" · "}
        <Link
          href="https://en.wikipedia.org/wiki/Donald_D._Hoffman"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Wikipedia
        </Link>
        {" · "}
        <Link
          href="https://www.ted.com/talks/donald_hoffman_do_we_see_reality_as_it_is"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          TED talk
        </Link>
      </p>
      <p>
        <strong>In-body record:</strong>{" "}
        <Link
          href="/vision/lc-perception-as-interface"
          className="text-primary hover:underline"
        >
          lc-perception-as-interface
        </Link>
        {" · "}
        <Link
          href="/vision/lc-assemblage-point"
          className="text-primary hover:underline"
        >
          lc-assemblage-point
        </Link>
        {" · "}
        <Link href="/people/carlos-castaneda" className="text-primary hover:underline">
          Carlos Castaneda
        </Link>
        {" · "}
        <Link href="/people/michael-levin" className="text-primary hover:underline">
          Michael Levin
        </Link>
      </p>
    </>
  ),
};

export default content;
