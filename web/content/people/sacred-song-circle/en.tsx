import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Sacred Song Circle — kirtan teacher network · where Vasudev Baba's profile lives | Coherence Network",
    description:
      "A welcome to Sacred Song Circle — the international kirtan-teacher network where Vasudev Baba's public bio is tended alongside other devotional musicians in the bhakti and ecstatic-singing field.",
  },
  breadcrumbName: "Sacred Song Circle",
  hero: {
    background:
      "radial-gradient(ellipse at 70% 25%, hsl(15 60% 60% / 0.55) 0%, transparent 55%), radial-gradient(ellipse at 25% 85%, hsl(255 30% 22% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(20 50% 65%) 0%, hsl(15 30% 35%) 50%, hsl(255 30% 20%) 100%)",
    eyebrow: "Kirtan teacher network · sacred song circles · where the body found Vasudev Baba's bio",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Sacred Song Circle",
    welcome: (
      <>
        <p>
          An international network of kirtan teachers tending one
          shared website that lists biographies, songbooks, and
          touring schedules for devotional musicians in the bhakti
          and ecstatic-singing field. The site is where{" "}
          <Link
            href="/people/vasudev-baba"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Vasudev Baba
          </Link>
          &apos;s public bio is tended, alongside other teachers
          in the lineage of sacred-name singing.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          The network operates without a single named founder
          surfaced — a teacher-cooperative shape rather than a
          school. The community is more legible than the legal
          form.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "What it is",
      value: "A multi-teacher kirtan website holding biographies, repertoire references, songbooks, and tour announcements for teachers in the network.",
    },
    {
      label: "Where the body met it",
      value: (
        <>
          Vasudev Baba&apos;s Sacred Song Circle bio was the
          primary public anchor used in researching his presence
          page. The site holds his lineage (Oslo / Indian
          Himalayas / Brazilian jungles / Rainbow Gatherings)
          more clearly than any single article.
        </>
      ),
    },
    {
      label: "Public anchors",
      value: (
        <p className="flex flex-wrap gap-x-3 gap-y-1">
          <Link
            href="https://www.sacredsongcircle.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            sacredsongcircle.com
          </Link>
          <Link
            href="https://www.sacredsongcircle.com/vasudev/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Vasudev profile
          </Link>
          <Link
            href="https://www.sacredsongcircle.com/testimonials/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Testimonials
          </Link>
          <Link
            href="https://www.facebook.com/groups/123972024418527/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Facebook group
          </Link>
        </p>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        Sacred Song Circle is the teacher network&apos;s own
        organising form. This page recognises its role as a
        public anchor that made the body&apos;s research on
        kirtan-lineage figures possible.
      </p>
    ),
  },
  articles: [
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What Sacred Song Circle has given the Coherence Network",
      body: (
        <ul>
          <li>
            The public anchor for{" "}
            <Link href="/people/vasudev-baba" className="text-primary hover:underline">
              Vasudev Baba
            </Link>
            &apos;s biographical arc — the source of canonical
            lineage detail (Oslo, 1987, Indian Himalayas,
            Brazilian jungles, Rainbow Gatherings).
          </li>
          <li>
            Teacher-cooperative shape (no single named founder
            surfaced; many teachers tending one shared site) →
            resonant with{" "}
            <Link
              href="/vision/lc-sovereignty-within-oneness"
              className="text-primary hover:underline"
            >
              lc-sovereignty-within-oneness
            </Link>{" "}
            (many sovereign cells, one organism).
          </li>
          <li>
            The bhakti lineage of singing the Divine Names as one
            of the body&apos;s anchor frequencies for the
            arrival-as-frequency framing. See{" "}
            <Link
              href="/vision/lc-frequency-routes-reception"
              className="text-primary hover:underline"
            >
              lc-frequency-routes-reception
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
          href="https://www.sacredsongcircle.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          sacredsongcircle.com
        </Link>
        {" · "}
        <Link
          href="https://www.facebook.com/groups/123972024418527/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Facebook group
        </Link>
      </p>
      <p>
        <strong>In-body record:</strong>{" "}
        <Link href="/people/vasudev-baba" className="text-primary hover:underline">
          Vasudev Baba
        </Link>
      </p>
    </>
  ),
};

export default content;
