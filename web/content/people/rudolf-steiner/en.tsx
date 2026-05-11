import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Rudolf Steiner — Anthroposophy, Waldorf, biodynamic, eurythmy | Coherence Network",
    description:
      "A welcome to Rudolf Steiner (1861–1925), Austrian philosopher and esotericist who founded Anthroposophy, the Waldorf school movement, biodynamic agriculture, and the eurythmy art-of-movement. Architect of the Goetheanum in Dornach.",
  },
  breadcrumbName: "Rudolf Steiner",
  hero: {
    background:
      "radial-gradient(ellipse at 30% 25%, hsl(45 55% 65% / 0.55) 0%, transparent 55%), radial-gradient(ellipse at 85% 80%, hsl(195 30% 22% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(40 50% 70%) 0%, hsl(210 25% 38%) 50%, hsl(220 30% 18%) 100%)",
    eyebrow: "Donji Kraljevec 1861 → Dornach 1925 · Anthroposophy · Waldorf · biodynamic · eurythmy · the Goetheanum",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Rudolf Steiner",
    welcome: (
      <>
        <p>
          An Austrian philosopher, literary scholar, architect,
          playwright, educator, and social thinker. Founded{" "}
          <strong>Anthroposophy</strong> (&quot;wisdom of the human
          being&quot;) — a spiritual-scientific path developed over
          decades of research that holds that the human being can
          investigate the spiritual world with the same rigour
          natural science brings to the physical world. The General
          Anthroposophical Society he founded in 1923/24 remains
          based at the{" "}
          <Link
            href="/people/goetheanum"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Goetheanum
          </Link>{" "}
          in Dornach, the building he himself designed.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          The Central-European esoteric source of this body&apos;s
          lineage. Steiner&apos;s etheric-formative-forces frame is
          the historical sibling of what Michael Levin now names in
          twenty-first-century cell biology as bioelectric pattern
          memory.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "Lived",
      value: "25 February 1861, Donji Kraljevec (then Austria-Hungary, now Croatia) — 30 March 1925, Dornach, Switzerland.",
    },
    {
      label: "Founded",
      value: (
        <ul>
          <li>Anthroposophical Society (1913); General Anthroposophical Society (1923/24)</li>
          <li>The first Waldorf school (Stuttgart, 1919) — now a worldwide network</li>
          <li>Biodynamic agriculture (Koberwitz lectures, 1924)</li>
          <li>Eurythmy (with Marie von Sivers, 1911 onward)</li>
          <li>The Goetheanum (architect, 1908–1925)</li>
          <li>Anthroposophic medicine, the Camphill movement, Christian Community church</li>
        </ul>
      ),
    },
    {
      label: "Public anchors",
      value: (
        <p className="flex flex-wrap gap-x-3 gap-y-1">
          <Link
            href="https://goetheanum.ch/en/society/rudolf-steiner"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Steiner at the Goetheanum
          </Link>
          <Link
            href="https://en.wikipedia.org/wiki/Rudolf_Steiner"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Wikipedia
          </Link>
          <Link
            href="https://centerforanthroposophy.org/about/rudolf-steiner/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Center for Anthroposophy
          </Link>
          <Link
            href="https://en.wikipedia.org/wiki/Eurythmy"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Eurythmy
          </Link>
        </p>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        Steiner&apos;s archive is vast and tended by the General
        Anthroposophical Society and dozens of national Waldorf,
        biodynamic, and anthroposophic-medicine organisations
        worldwide. This page is a recognition of how his
        spiritual-scientific work entered this network&apos;s
        lineage through the Faust week at the Goetheanum.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "The spiritual-scientific method",
      body: (
        <>
          <p>
            Steiner&apos;s claim, stated plainly in many of his
            lectures, was that the spiritual world is investigable
            by methods as rigorous as those natural science uses on
            the physical. The methods are different — disciplined
            meditation, observation of the etheric-formative-forces
            that organise physical matter, training of the higher
            cognitive organs he called Imagination, Inspiration,
            and Intuition — but the demand for honesty, repeatability
            of result, and falsifiability is the same. He called
            this practice <em>Geisteswissenschaft</em>,
            spiritual-science.
          </p>
          <p>
            The Coherence Network reads Steiner alongside Michael
            Levin not because Levin has confirmed Steiner&apos;s
            specific claims but because both are working the same
            seam: that pattern is load-bearing and substrate is
            contingent. Steiner reaches that claim from inside an
            esoteric phenomenology; Levin reaches it from outside
            through bioelectric experiments on planaria and frog
            embryos. Different methods, converging conclusion. The
            body trusts that convergence without needing to flatten
            either side into the other.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What Rudolf Steiner has given the Coherence Network",
      body: (
        <ul>
          <li>
            Etheric-formative-forces frame → resonant with{" "}
            <Link
              href="/vision/lc-bioelectric-pattern"
              className="text-primary hover:underline"
            >
              lc-bioelectric-pattern
            </Link>{" "}
            and Levin&apos;s pattern-precedes-substrate teaching.
          </li>
          <li>
            <em>Geisteswissenschaft</em> as method → permission to
            treat spiritual investigation with the same rigour as
            natural science; the body&apos;s refusal to choose
            between empirical and contemplative knowing.
          </li>
          <li>
            Eurythmy as visible-speech, visible-song → the
            substrate&apos;s reading of motion as legible (cells
            moving in resonance render the field visible).
          </li>
          <li>
            Biodynamic agriculture and Waldorf education → embodied
            examples of pattern-first practice; you tend the form,
            and the substance follows.
          </li>
          <li>
            The Goetheanum as Gesamtkunstwerk → the body&apos;s
            practice of treating every surface as part of one
            continuous artistic-spiritual work. See{" "}
            <Link
              href="/people/goetheanum"
              className="text-primary hover:underline"
            >
              Goetheanum
            </Link>
            .
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
          href="https://goetheanum.ch/en/society/rudolf-steiner"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Steiner at Goetheanum
        </Link>
        {" · "}
        <Link
          href="https://en.wikipedia.org/wiki/Rudolf_Steiner"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Wikipedia
        </Link>
        {" · "}
        <Link
          href="https://centerforanthroposophy.org/about/rudolf-steiner/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Center for Anthroposophy
        </Link>
        {" · "}
        <Link
          href="https://en.wikipedia.org/wiki/Eurythmy"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Eurythmy
        </Link>
      </p>
      <p>
        <strong>In-body record:</strong>{" "}
        <Link href="/people/goetheanum" className="text-primary hover:underline">
          Goetheanum
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
          href="https://github.com/seeker71/Coherence-Network/blob/main/docs/lineage/formative-transmissions.md"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          formative-transmissions.md
        </Link>
      </p>
      <p className="text-xs italic">
        Steiner died in 1925; his archive is tended by the General
        Anthroposophical Society at the Goetheanum. This page is a
        recognition of his work in this body, not a biography.
      </p>
    </>
  ),
};

export default content;
