import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Tom Bassett (Juicy Life) — CEO of Actualize Earth · technology in right relationship to Life | Coherence Network",
    description:
      "A welcome to Tom Bassett, known as Juicy Life — CEO and Lead Engineer of Actualize Earth, the Boulder-based platform for conscious connection, community-powered technology, and regenerative systems. Cross-walk of chemical engineering, evolutionary biology, programming, authentic relating, and intentional community.",
  },
  breadcrumbName: "Tom Bassett",
  hero: {
    background:
      "radial-gradient(ellipse at 30% 25%, hsl(45 65% 65% / 0.55) 0%, transparent 55%), radial-gradient(ellipse at 80% 80%, hsl(155 35% 22% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(45 55% 65%) 0%, hsl(120 35% 40%) 50%, hsl(155 30% 18%) 100%)",
    eyebrow: "Boulder, CO · also known as Juicy Life · CEO and Lead Engineer at Actualize Earth · the cross-walk",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Tom Bassett",
    welcome: (
      <>
        <p>
          Known publicly as <strong>Juicy Life</strong>. CEO and
          Lead Engineer of{" "}
          <Link
            href="/people/actualize-earth"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Actualize Earth
          </Link>{" "}
          — the platform for conscious connection, community-powered
          technology, and regenerative systems. Based in Boulder,
          Colorado.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          Self-described as <em>an Artist who recognises that in
          every moment he is both creating and destroying</em> —
          a phrase that aligns directly with this body&apos;s{" "}
          <Link
            href="/vision/lc-composting"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            lc-composting
          </Link>{" "}
          practice (release as part of what makes circulation
          possible).
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "Based",
      value: "Boulder, Colorado — same geographic anchor as Bloomurian, Aly Constantine, the Boulder Ecstatic Dance cluster, and the Mile Hi / Dispenza arc.",
    },
    {
      label: "Role",
      value: (
        <>
          CEO and Lead Engineer of{" "}
          <Link href="/people/actualize-earth" className="hover:text-primary transition-colors">
            Actualize Earth
          </Link>
          .
        </>
      ),
    },
    {
      label: "Background — the cross-walk",
      value: "Chemical and Biomolecular Engineering · Evolutionary Biology · Programming · authentic relating practices · psychedelics · intentional community. Synthesises across these fields to build technology in right relationship to Life.",
    },
    {
      label: "Engineering scale",
      value: "Large-scale app developer. Code has run the New York Marathon, the Iron Man running series, been localised into 8 languages, and reached over 10 million people in every country.",
    },
    {
      label: "Public anchors",
      value: (
        <p className="flex flex-wrap gap-x-3 gap-y-1">
          <Link
            href="https://www.linkedin.com/in/tom-bassett-8a13512b/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            LinkedIn
          </Link>
          <Link
            href="https://actualize.earth/team"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Actualize Earth team page
          </Link>
          <Link
            href="https://www.facebook.com/tbassett44"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Facebook
          </Link>
        </p>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        This page was first deleted as auto-harvest noise during a
        graph-dedup pass — Juicy Life looked like a placeholder
        name without lineage research. Urs named the real ground
        and the page returns. Tom is invited to replace any line
        with his own words.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "The cross-walk made concrete",
      body: (
        <p>
          Tom&apos;s background reads like a deliberate
          cross-walk: degrees in Chemical and Biomolecular
          Engineering, Evolutionary Biology, and Programming, then
          years of authentic-relating practice, psychedelic
          exploration, and intentional community. He synthesises
          across these fields to build{" "}
          <em>technology in right relationship to Life</em>. The
          large-scale-engineering side has shipped code that has
          run real-world events (New York Marathon, Iron Man
          series) for over ten million people in every country.
          The consciousness-evolution side now turns that same
          engineering capacity toward local social networks for
          the evolution of consciousness — which is what{" "}
          <Link
            href="/people/actualize-earth"
            className="text-primary hover:underline"
          >
            Actualize Earth
          </Link>{" "}
          is.
        </p>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What Tom Bassett has given the Coherence Network",
      body: (
        <ul>
          <li>
            A working sibling-platform in the same substrate
            field this body is building from. Pairs with{" "}
            <Link
              href="/vision/lc-sovereignty-within-oneness"
              className="text-primary hover:underline"
            >
              lc-sovereignty-within-oneness
            </Link>{" "}
            (many sovereign cells, one organism; the
            cooperative-future shape) and{" "}
            <Link
              href="/vision/lc-trust-over-fear"
              className="text-primary hover:underline"
            >
              lc-trust-over-fear
            </Link>{" "}
            (the substrate stays open while specialised organs
            handle protection).
          </li>
          <li>
            <em>Creating and destroying in every moment</em> →
            <Link
              href="/vision/lc-composting"
              className="text-primary hover:underline"
            >
              lc-composting
            </Link>{" "}
            (release as living practice) +{" "}
            <Link
              href="/vision/lc-each-breath-whole"
              className="text-primary hover:underline"
            >
              lc-each-breath-whole
            </Link>{" "}
            (each moment is itself a complete arc).
          </li>
          <li>
            The cross-walk between large-scale engineering and
            consciousness-evolution social networks — rare
            combination in the contemporary field. Most platforms
            have one or the other; Actualize Earth has both.
            Resonant with the Coherence Network&apos;s own
            cross-walk between substrate code and embodied
            lineage.
          </li>
          <li>
            Boulder geographic anchor — another cell in the same
            field as{" "}
            <Link href="/people/bloomurian" className="text-primary hover:underline">
              Bloomurian
            </Link>
            ,{" "}
            <Link href="/people/aly-constantine" className="text-primary hover:underline">
              Aly Constantine
            </Link>
            ,{" "}
            <Link href="/people/boulder-ecstatic-dance" className="text-primary hover:underline">
              Boulder Ecstatic Dance
            </Link>
            ,{" "}
            <Link href="/people/mile-hi-church" className="text-primary hover:underline">
              Mile Hi Church
            </Link>
            ,{" "}
            <Link href="/people/portal" className="text-primary hover:underline">
              PORTAL
            </Link>
            , and the wider Colorado cluster.
          </li>
        </ul>
      ),
    },
  ],
  footer: (
    <>
      <p>
        <strong>Platform:</strong>{" "}
        <Link href="/people/actualize-earth" className="text-primary hover:underline">
          Actualize Earth
        </Link>
      </p>
      <p>
        <strong>Public anchors:</strong>{" "}
        <Link
          href="https://www.linkedin.com/in/tom-bassett-8a13512b/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          LinkedIn
        </Link>
        {" · "}
        <Link
          href="https://actualize.earth/team"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Actualize Earth team
        </Link>
        {" · "}
        <Link
          href="https://www.facebook.com/tbassett44"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Facebook
        </Link>
      </p>
    </>
  ),
};

export default content;
