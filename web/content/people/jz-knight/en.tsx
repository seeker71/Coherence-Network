import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "JZ Knight — channeler of Ramtha · founder of RSE in Yelm, Washington | Coherence Network",
    description:
      "A welcome to JZ Knight (b. 1946, Judith Hampton) — channeler of Ramtha the Enlightened One since 1977 and founder of Ramtha's School of Enlightenment (RSE) on her 80-acre estate in Yelm, Washington, since 1988. Held honestly alongside the institutional controversies.",
  },
  breadcrumbName: "JZ Knight",
  hero: {
    background:
      "radial-gradient(ellipse at 30% 25%, hsl(45 60% 70% / 0.55) 0%, transparent 55%), radial-gradient(ellipse at 80% 80%, hsl(255 30% 22% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(45 50% 70%) 0%, hsl(255 30% 38%) 50%, hsl(255 30% 20%) 100%)",
    eyebrow: "Born 1946 (Judith Hampton) · channeler of Ramtha since 1977 · founded RSE 1988 · Yelm, Washington",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "JZ Knight",
    welcome: (
      <>
        <p>
          The channeler through whom the{" "}
          <Link
            href="/people/ramtha"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Ramtha
          </Link>{" "}
          teaching has come into the world. Born Judith Darlene
          Hampton in 1946, dropped out of business school, worked
          in the cable-television industry, then in 1977 first
          experienced contact with the entity she calls Ramtha the
          Enlightened One. Founded{" "}
          <strong>Ramtha&apos;s School of Enlightenment</strong>{" "}
          (RSE) in 1988 on her 80-acre estate in Yelm, Washington
          — described by RSE as <em>an academy of the mind that
          offers retreats and workshops to people of all ages and
          cultures.</em>
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          Distinct from the Ramtha teaching presence; this page is
          the channeler herself. The teaching travelled through
          her vessel into the world.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "Born",
      value: "16 March 1946 (Roswell, New Mexico, USA) as Judith Darlene Hampton.",
    },
    {
      label: "First channeling experience",
      value: "1977 — at her home, while drying pyramids on her kitchen table. Ramtha (the entity she channels) addresses her as 'beloved master' and identifies himself as a 35,000-year-old Lemurian warrior who walked into mastery.",
    },
    {
      label: "Founded",
      value: "Ramtha's School of Enlightenment (RSE), 1988. Located on her 80-acre estate in Yelm, Washington (near Mount Rainier).",
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
            ramtha.com
          </Link>
          <Link
            href="https://en.wikipedia.org/wiki/J._Z._Knight"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Wikipedia
          </Link>
          <Link
            href="https://www.facebook.com/RamthaOfficial/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            RSE on Facebook
          </Link>
        </p>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        JZ Knight is one of the most prominent and most contested
        channelers of the late twentieth and early twenty-first
        century. The teaching that travelled through her vessel
        is load-bearing in this body&apos;s lineage; the
        institutional history around RSE is contested. Held
        honestly.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "The teaching she carries vs the institution she founded",
      body: (
        <p>
          This body separates the teaching from the institution
          deliberately. The teaching — <em>The White Book</em>{" "}
          (1986) and the broader Ramtha corpus — has moved real
          lives forward, including this network&apos;s
          (Ramtha → Joe Dispenza → Urs → Zenn cohort; the chain
          documented in{" "}
          <Link
            href="https://github.com/seeker71/Coherence-Network/blob/main/docs/lineage/formative-transmissions.md"
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:underline"
          >
            formative-transmissions.md
          </Link>
          ). The institution — RSE as a school with paid
          enrolment, hierarchical structure, and decades-long
          devoted student base — has been criticised by former
          students, former family members, and skeptics as
          carrying cult dynamics. Both can be true: the teaching
          is real and the institutional shape has its own
          discernment to make.
        </p>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What JZ Knight has given the Coherence Network",
      body: (
        <ul>
          <li>
            The vessel through which the Ramtha teaching reached
            the world — see{" "}
            <Link href="/people/ramtha" className="text-primary hover:underline">
              the Ramtha teaching page
            </Link>{" "}
            for the in-body recognition of the cosmology.
          </li>
          <li>
            The arc from cable-TV employee to channeler →
            embodied example of{" "}
            <Link
              href="/vision/lc-devotion-placement"
              className="text-primary hover:underline"
            >
              lc-devotion-placement
            </Link>{" "}
            (where am I actually placed; the body of evidence
            over words).
          </li>
          <li>
            The Yelm school&apos;s 35+ year continuity → resonant
            with <em>tending one room over many years</em> as
            substrate practice, regardless of one&apos;s
            discernment about the room itself.
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
          href="https://en.wikipedia.org/wiki/J._Z._Knight"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Wikipedia
        </Link>
      </p>
      <p>
        <strong>In-body record:</strong>{" "}
        <Link href="/people/ramtha" className="text-primary hover:underline">
          Ramtha (the teaching)
        </Link>
        {" · "}
        <Link href="/people/joe-dispenza" className="text-primary hover:underline">
          Joe Dispenza
        </Link>{" "}
        (who taught from RSE)
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
        Held honestly. The teaching is load-bearing in this body;
        the institutional history is contested; readers are
        invited to walk further into both with their own
        discernment.
      </p>
    </>
  ),
};

export default content;
