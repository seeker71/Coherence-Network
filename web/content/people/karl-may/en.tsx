import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Karl May — Winnetou, Old Shatterhand, the German-language frontier imagination | Coherence Network",
    description:
      "A welcome to Karl May (1842–1912), German author of Winnetou and Old Shatterhand. Apache country alive in him before Colorado was geography. Brotherhood across cultures, indigenous wisdom carried by a sympathetic outsider, the open landscape as moral teacher.",
  },
  breadcrumbName: "Karl May",
  hero: {
    background:
      "radial-gradient(ellipse at 80% 30%, hsl(15 65% 55% / 0.65) 0%, transparent 55%), radial-gradient(ellipse at 20% 80%, hsl(35 35% 25% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(28 55% 65%) 0%, hsl(20 40% 40%) 45%, hsl(15 30% 18%) 100%)",
    eyebrow: "Hohenstein-Ernstthal 1842 → Radebeul 1912 · Villa Shatterhand · ~200 million copies · the frontier imagination in German",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Karl May",
    welcome: (
      <>
        <p>
          A German storyteller whose <em>Winnetou</em> trilogy and
          Orient cycle put a generation of Swiss and German children
          inside the American frontier imagination long before any of
          them set foot on the continent. Brotherhood across cultures,
          indigenous wisdom carried by a sympathetic outsider, the
          open landscape as moral teacher. Around 200 million copies
          sold worldwide; one of the best-selling German writers of
          all time.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          Apache country was alive in Urs long before Colorado was
          geography. The frontier imagination that later met the
          Boulder valleys was first walked through his books.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "Lived",
      value: "25 February 1842, Hohenstein-Ernstthal — 30 March 1912, Radebeul (near Dresden). House: Villa Shatterhand.",
    },
    {
      label: "Foundational works in this body",
      value: (
        <>
          <em>Winnetou I, II, III</em> · the Orient cycle (<em>Durch
          die Wüste</em>, <em>Durchs wilde Kurdistan</em>, …) · the
          America-Westmen cycle with Old Shatterhand
        </>
      ),
    },
    {
      label: "Reach",
      value: "Around 200 million copies sold worldwide.",
    },
    {
      label: "Stewardship",
      value: (
        <>
          The{" "}
          <Link
            href="https://www.karl-may-stiftung.de/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Karl-May-Stiftung
          </Link>{" "}
          was established by Klara May in 1913, one year after his
          death; it maintains the{" "}
          <Link
            href="https://www.karl-may-museum.de/en/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Karl May Museum
          </Link>{" "}
          at Karl-May-Str. 5, Radebeul.
        </>
      ),
    },
    {
      label: "Public anchors",
      value: (
        <p className="flex flex-wrap gap-x-3 gap-y-1">
          <Link
            href="https://en.wikipedia.org/wiki/Karl_May"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Wikipedia
          </Link>
          <Link
            href="https://www.karl-may-stiftung.de/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Karl-May-Stiftung
          </Link>
          <Link
            href="https://www.karl-may-museum.de/en/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Karl May Museum (Radebeul)
          </Link>
        </p>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        Karl May&apos;s archive is tended by the Karl-May-Stiftung in
        Radebeul. This page is not a biography; it is a recognition —
        a record of how his books built the imaginal landscape Urs
        later walked through in Colorado.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "Winnetou and the chosen-brotherhood teaching",
      body: (
        <>
          <p>
            Karl May&apos;s most enduring creation is the bond between{" "}
            <strong>Winnetou</strong>, the wise chief of the Mescalero
            Apache, and <strong>Old Shatterhand</strong>, a German
            immigrant who arrives in the American West and earns his
            place not by force but by precision, listening, and
            refusal of cruelty. They become blood brothers across
            culture, religion, and language. The German-language
            children who read these books learned — before any other
            framing reached them — that brotherhood across cultures
            is possible and that indigenous wisdom is the deeper
            teaching, not the local colour.
          </p>
          <p>
            The historical record is more complicated. May had never
            been to America when he wrote most of the Winnetou
            trilogy; the books are a romantic construction. The
            twenty-first century has rightly questioned which voice
            gets to tell whose story. The Coherence Network reads
            this honestly: the books were a German child&apos;s
            imaginal door, not a faithful ethnography. What landed in
            this body was the <em>shape</em> — chosen brotherhood,
            honor as practice, the landscape as moral teacher — and
            that shape held even when the historical detail did not.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",
      heading: "The frontier imagination as preparation",
      body: (
        <p>
          When Urs eventually arrived in Colorado in the
          twenty-first century, the geography was already
          imaginally pre-walked. The Front Range, the high country,
          the open spaces where the body could breathe — none of it
          was foreign. Karl May had been there first, in German, in
          a Swiss childhood. The body&apos;s Boulder years and the
          eventual{" "}
          <Link
            href="https://github.com/seeker71/Coherence-Network/blob/main/docs/lineage/formative-transmissions.md"
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:underline"
          >
            full teaching lineage
          </Link>{" "}
          travelling through Boulder are part of the same arc that
          began with Winnetou.
        </p>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What Karl May has given the Coherence Network",
      body: (
        <ul>
          <li>
            The chosen-brotherhood teaching → the body&apos;s
            practice of multi-cell co-weave; cells (humans, sibling
            intelligences) finding kinship across substrate.
          </li>
          <li>
            Indigenous wisdom as the deeper teaching → the body&apos;s
            reading-order of who gets to name the field. See{" "}
            <Link
              href="/vision/lc-voice-over-intentions"
              className="text-primary hover:underline"
            >
              lc-voice-over-intentions
            </Link>{" "}
            (lead with their voice, not ours).
          </li>
          <li>
            The landscape as moral teacher → the body&apos;s
            geographic anchoring (Boulder, Ubud, Lake Atitlán) as
            real, not decorative.
          </li>
          <li>
            Carried into this body through{" "}
            <Link
              href="/people/susan-muff-sprenger"
              className="text-primary hover:underline"
            >
              Susan Muff-Sprenger
            </Link>
            &apos;s broader Swiss-German childhood library, alongside{" "}
            <Link
              href="/people/james-fenimore-cooper"
              className="text-primary hover:underline"
            >
              Fenimore Cooper&apos;s Leatherstocking
            </Link>{" "}
            and{" "}
            <Link
              href="/people/michael-ende"
              className="text-primary hover:underline"
            >
              Ende&apos;s Momo and Die unendliche Geschichte
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
          href="https://en.wikipedia.org/wiki/Karl_May"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Wikipedia
        </Link>
        {" · "}
        <Link
          href="https://www.karl-may-stiftung.de/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Karl-May-Stiftung
        </Link>
        {" · "}
        <Link
          href="https://www.karl-may-museum.de/en/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Karl May Museum
        </Link>
        {" · "}
        <Link
          href="https://www.karl-may-museum.de/en/collections/karl-may/biography-works/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Biography & works
        </Link>
      </p>
      <p>
        <strong>In-body record:</strong>{" "}
        <Link href="/people/susan-muff-sprenger" className="text-primary hover:underline">
          Susan Muff-Sprenger
        </Link>
        {" · "}
        <Link href="/people/michael-ende" className="text-primary hover:underline">
          Michael Ende
        </Link>
        {" · "}
        <Link href="/people/james-fenimore-cooper" className="text-primary hover:underline">
          James Fenimore Cooper
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
        Karl May died in 1912; his archive is tended by the
        Karl-May-Stiftung in Radebeul. This page is a recognition
        of his books in this body, not a biography.
      </p>
    </>
  ),
};

export default content;
