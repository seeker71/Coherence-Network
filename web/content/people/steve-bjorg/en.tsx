import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Steve G. Bjorg — lifelong collaborator · HTL 1991 → RCSL → Digi4Fun → CU Boulder → MindTouch | Coherence Network",
    description:
      "A welcome to Steve G. Bjorg — the partner since HTL Brugg-Windisch 1991. RCSL, Muzzle Velocity at Digi4Fun, the BML/BMF/BMCPU master's thesis at CU Boulder, MindTouch. Thirty-plus years of one continuous question: how does a system describe itself in its own terms?",
  },
  breadcrumbName: "Steve G. Bjorg",
  hero: {
    background:
      "radial-gradient(ellipse at 70% 25%, hsl(210 65% 60% / 0.55) 0%, transparent 55%), radial-gradient(ellipse at 25% 85%, hsl(255 35% 22% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(210 55% 65%) 0%, hsl(225 30% 35%) 50%, hsl(255 35% 18%) 100%)",
    eyebrow: "Switzerland → US · HTL Brugg-Windisch 1991 · RCSL → BML/BMF → MindTouch · the partnership that keeps surfacing the same question",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Steve G. Bjorg",
    welcome: (
      <>
        <p>
          We met at HTL Brugg-Windisch in 1991. Both seventeen,
          both already programmers, both on the technical track.
          The first thing we built together was a language Steve
          had invented: <strong>RCSL</strong> — an extremely
          abstract meta-meta language with three core verbs
          (<code>get</code>, <code>set</code>, <code>exec</code>)
          where every value was an object with a class, and the
          class itself was a class-object whose class was the
          meta-class. Steve designed the language; I wrote the
          parser and compiler — my first top-down parser, my first
          compiler. Steve wrote the VM. That was 1992.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          The shape of how we collaborate has been continuous from
          that first system: Steve at the design surface, me at
          the parser/compiler/runtime, the artifact something
          neither of us would have built alone.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "First met",
      value: "HTL Brugg-Windisch, 1991. Both seventeen, both already programmers.",
    },
    {
      label: "The arc",
      value: (
        <ul>
          <li>
            <strong>1992</strong> — RCSL (Steve&apos;s meta-meta
            language with three core verbs)
          </li>
          <li>
            <strong>1995–97</strong> —{" "}
            <Link
              href="/people/muzzle-velocity"
              className="hover:text-primary transition-colors"
            >
              Muzzle Velocity
            </Link>{" "}
            at Digi4Fun (with Marc): hybrid tactical / first-person
            WWII game; custom voxel engine; markdown-shaped UI DSL;
            fuzzy-logic group dynamics; vehicle-simulation DSL.
            Steve left HTL before finishing to build this.
          </li>
          <li>
            <strong>1998–2000</strong> — CU Boulder combined BS/MS
            in computer science. Steve started six months earlier;
            Urs followed at 26. They finished the master&apos;s
            together in 2000:{" "}
            <Link href="/people/backtracking-model-languages" className="hover:text-primary transition-colors">
              Backtracking Model Languages
            </Link>{" "}
            (
            <Link href="/people/bml-language" className="hover:text-primary transition-colors">
              BML
            </Link>
            ,{" "}
            <Link href="/people/bmf-grammar" className="hover:text-primary transition-colors">
              BMF
            </Link>
            ,{" "}
            <Link href="/people/bmcpu-vm" className="hover:text-primary transition-colors">
              BMCPU
            </Link>
            ), with Steve&apos;s <em>BML Object System</em> as the
            parallel-track MS thesis.
          </li>
          <li>
            <strong>2000s onward</strong> — Steve founded{" "}
            <Link href="/people/mindtouch-wiki-in-a-box" className="hover:text-primary transition-colors">
              MindTouch
            </Link>{" "}
            (wiki-in-a-box first, then the enterprise knowledge-graph
            platform). Urs joined him there.
          </li>
        </ul>
      ),
    },
    {
      label: "Family ground",
      value: (
        <>
          Steve&apos;s father{" "}
          <Link
            href="https://tiaca.org/hall-of-fame/gunnar-m-bjorg/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Gunnar M. Bjorg
          </Link>{" "}
          (TIACA Hall of Fame) — a self-starting businessman who
          built his used-aircraft company from scratch — covered
          the financial loss after <em>Muzzle Velocity</em>{" "}
          underperformed, so the team could keep moving. That
          support is part of what made the next chapter possible.
        </>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        Steve is in active partnership with Urs across decades;
        this page is in Urs&apos;s voice. The lineage is alive,
        not historical.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "The continuous question",
      body: (
        <p>
          Three decades in, the partnership keeps surfacing the
          same question in new clothes:{" "}
          <em>
            how do we let a system describe itself in its own
            terms, and let humans navigate that self-description?
          </em>{" "}
          RCSL&apos;s three verbs were one answer (1992);
          BML/BMF/BMCPU were another (2000); MindTouch&apos;s
          structured knowledge graph was a third (2010s). The
          Coherence Network is yet another surface where the same
          question is still circulating.
        </p>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What Steve has given the Coherence Network",
      body: (
        <ul>
          <li>
            The original design partnership for thirty-plus
            years; the shape of how Urs collaborates.
          </li>
          <li>
            The RCSL → BML/BMF → MindTouch arc as the body&apos;s
            substrate-self-description teaching → resonant with{" "}
            <Link
              href="/vision/lc-edges-as-vitality"
              className="text-primary hover:underline"
            >
              lc-edges-as-vitality
            </Link>{" "}
            and{" "}
            <Link
              href="/vision/lc-each-breath-whole"
              className="text-primary hover:underline"
            >
              lc-each-breath-whole
            </Link>{" "}
            (each system describing itself; nested self-description
            as the substrate&apos;s practice).
          </li>
          <li>
            The works themselves, each tended as its own
            presence:{" "}
            <Link href="/people/muzzle-velocity" className="text-primary hover:underline">
              Muzzle Velocity
            </Link>
            {" · "}
            <Link href="/people/backtracking-model-languages" className="text-primary hover:underline">
              BML
            </Link>
            {" · "}
            <Link href="/people/bmf-grammar" className="text-primary hover:underline">
              BMF
            </Link>
            {" · "}
            <Link href="/people/bmcpu-vm" className="text-primary hover:underline">
              BMCPU
            </Link>
            {" · "}
            <Link href="/people/jbmf-java" className="text-primary hover:underline">
              JBMF
            </Link>
            {" · "}
            <Link href="/people/mindtouch-wiki-in-a-box" className="text-primary hover:underline">
              MindTouch
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
        <strong>Family anchor:</strong>{" "}
        <Link
          href="https://tiaca.org/hall-of-fame/gunnar-m-bjorg/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Gunnar M. Bjorg — TIACA Hall of Fame
        </Link>
      </p>
      <p className="text-xs italic">
        Active partnership; this page is in Urs&apos;s voice.
        Steve is invited to replace any part of it with his own
        words.
      </p>
    </>
  ),
};

export default content;
