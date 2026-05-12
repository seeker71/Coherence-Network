import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Mile Hi Church — Lakewood, Colorado · the room where Joe Dispenza first met this body | Coherence Network",
    description:
      "A welcome to Mile Hi Church in Lakewood, Colorado — a large New Thought / Religious Science community. The Centers for Spiritual Living congregation where Joe Dispenza taught around 2005, the first room in which Urs encountered his teaching live.",
  },
  breadcrumbName: "Mile Hi Church",
  hero: {
    background:
      "radial-gradient(ellipse at 35% 25%, hsl(195 55% 60% / 0.55) 0%, transparent 55%), radial-gradient(ellipse at 80% 80%, hsl(255 30% 22% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(195 50% 65%) 0%, hsl(220 30% 38%) 50%, hsl(255 30% 18%) 100%)",
    eyebrow: "Lakewood, Colorado · New Thought / Religious Science · the room where the Ramtha → Dispenza chain reached Urs",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Mile Hi Church",
    welcome: (
      <>
        <p>
          A large New Thought / Religious Science congregation in
          Lakewood, Colorado, part of the Centers for Spiritual
          Living movement. The room where{" "}
          <Link
            href="/people/joe-dispenza"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Joe Dispenza
          </Link>{" "}
          taught around 2005, and the first room in which Urs
          encountered his teaching live — the lineage node where
          the channeled-cosmology stream from{" "}
          <Link
            href="/people/ramtha"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Ramtha
          </Link>{" "}
          arrived in this body through a physical room rather than
          through a book.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          The Religious Science tradition was founded by Ernest
          Holmes in the early twentieth century; Mile Hi has been
          one of its prominent Colorado congregations for decades.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "Where",
      value: (
        <Link
          href="https://maps.app.goo.gl/?q=Mile+Hi+Church+9077+W+Alameda+Ave+Lakewood+CO"
          target="_blank"
          rel="noopener noreferrer"
          className="hover:text-primary transition-colors"
        >
          9077 W. Alameda Avenue, Lakewood, Colorado
        </Link>
      ),
    },
    {
      label: "Tradition",
      value: "New Thought / Religious Science (Ernest Holmes lineage); affiliated with the Centers for Spiritual Living.",
    },
    {
      label: "Encounter in this body",
      value: (
        <>
          ~2005 — Urs heard{" "}
          <Link
            href="/people/joe-dispenza"
            className="hover:text-primary transition-colors"
          >
            Joe Dispenza
          </Link>{" "}
          teach live in this room. The first time the teaching
          arrived not as a book but as a body in a hall.
        </>
      ),
    },
    {
      label: "Public anchors",
      value: (
        <p className="flex flex-wrap gap-x-3 gap-y-1">
          <Link
            href="https://milehichurch.org/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            milehichurch.org
          </Link>
          <Link
            href="https://csl.org/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Centers for Spiritual Living
          </Link>
        </p>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        Mile Hi Church is a working congregation with its own
        ongoing programme. This page recognises the room&apos;s
        role as the physical-arrival anchor of the Dispenza
        teaching in this network&apos;s lineage.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "The lineage chain through this room",
      body: (
        <p>
          The teaching chain in this body runs:{" "}
          <strong>
            <Link href="/people/ramtha" className="text-primary hover:underline">
              Ramtha / JZ Knight
            </Link>{" "}
            →{" "}
            <Link href="/people/joe-dispenza" className="text-primary hover:underline">
              Joe Dispenza
            </Link>
          </strong>{" "}
          (RSE student then teacher from 2001){" "}
          <strong>→ Urs</strong> (Mile Hi Church, ~2005){" "}
          <strong>→ Zenn cohort</strong> (Aurora retreat, April
          2026). Mile Hi is the link between the published
          cosmology and the present-day cohort. A Colorado room
          on a Sunday morning, a teacher whose books were already
          on shelves around the world, and one cell from
          Switzerland who happened to be living within driving
          distance.
        </p>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What Mile Hi Church has given the Coherence Network",
      body: (
        <ul>
          <li>
            The physical-arrival room for{" "}
            <Link
              href="/people/joe-dispenza"
              className="text-primary hover:underline"
            >
              Joe Dispenza
            </Link>
            &apos;s teaching in this body — the Ramtha-to-software
            chain reached Urs through this Lakewood hall.
          </li>
          <li>
            The New Thought / Religious Science tradition&apos;s
            posture (consciousness creates form; the universe is
            an inside job) as foundational vocabulary → resonant
            with{" "}
            <Link
              href="/vision/lc-sovereignty-within-oneness"
              className="text-primary hover:underline"
            >
              lc-sovereignty-within-oneness
            </Link>{" "}
            and{" "}
            <Link
              href="/vision/lc-arrival-as-recognition"
              className="text-primary hover:underline"
            >
              lc-arrival-as-recognition
            </Link>
            .
          </li>
          <li>
            Part of the body&apos;s Colorado anchor (Boulder
            Ecstatic Dance, Mile Hi Lakewood, Aurora retreat
            April 2026, Emergence Conference at GaiaSphere) →
            cluster mapped in{" "}
            <Link
              href="https://github.com/seeker71/Coherence-Network/blob/main/docs/lineage/2026-04-29-constellation-of-cells.md"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              the constellation-of-cells record
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
          href="https://milehichurch.org/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          milehichurch.org
        </Link>
        {" · "}
        <Link
          href="https://csl.org/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Centers for Spiritual Living
        </Link>
      </p>
      <p>
        <strong>In-body record:</strong>{" "}
        <Link href="/people/joe-dispenza" className="text-primary hover:underline">
          Joe Dispenza
        </Link>
        {" · "}
        <Link href="/people/ramtha" className="text-primary hover:underline">
          Ramtha
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
