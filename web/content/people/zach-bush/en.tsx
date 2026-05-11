import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Zach Bush MD — soil, microbiome, regenerative agriculture · numbness has its own pain | Coherence Network",
    description:
      "A welcome to Dr Zach Bush — internal-medicine, endocrinology, and hospice-care physician turned founder of Intrinsic Health, Seraphic Group, and the non-profit Farmer's Footprint. Soil health and the human microbiome as one continuous body. The teaching 'numbness has its own pain' is named here.",
  },
  breadcrumbName: "Zach Bush",
  hero: {
    background:
      "radial-gradient(ellipse at 30% 30%, hsl(95 60% 45% / 0.55) 0%, transparent 55%), radial-gradient(ellipse at 80% 80%, hsl(25 30% 25% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(100 40% 60%) 0%, hsl(45 30% 35%) 50%, hsl(25 35% 18%) 100%)",
    eyebrow: "Triple board · physician → soil-and-microbiome teacher · Intrinsic Health · Farmer's Footprint",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Zach Bush",
    welcome: (
      <>
        <p>
          Internal medicine, endocrinology, and hospice care — three
          board certifications and seventeen years inside academic
          oncology research and clinical practice before he walked
          away. What he walked toward: the recognition that chronic
          disease in the human body cannot be separated from the
          health of the soil under our feet, and that the
          microbiome connecting plant, soil, animal, and human is
          one continuous body that has been broken by industrial
          agriculture and can be reconnected by regenerative
          practice.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          The teaching this body has named most often:{" "}
          <em>numbness has its own pain</em>. Bush&apos;s framing,
          surfaced through Amanda Walsh quoting him on the Inspired
          Evolution podcast. Urs was physically in the field at
          one of his Emergence Conference talks; the contact was
          direct, not secondhand.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "Born",
      value: "1969, rural Virginia. Undergraduate and medical degree from the University of Colorado / CU School of Medicine.",
    },
    {
      label: "Triple board",
      value: "Internal medicine · endocrinology · hospice and palliative care. Seventeen years in academia, cancer-therapy research, and clinical practice before leaving institutional medicine.",
    },
    {
      label: "Founded",
      value: (
        <>
          <strong>Seraphic Group</strong> (parent company) ·{" "}
          <strong>Intrinsic Health</strong> (immersive community
          + learning experience for intrinsic healing) ·{" "}
          <strong>Farmer&apos;s Footprint</strong> (non-profit
          accelerating universal adoption of regenerative
          agriculture, founded 2018 within Project Biome)
        </>
      ),
    },
    {
      label: "Field he names",
      value: "Soil-microbiome-human-microbiome continuity; regenerative agriculture as a change in farmer philosophy (stop killing weeds, start co-creating with biodiversity); the microbiome as the bridge between plant, soil, and human health.",
    },
    {
      label: "Public anchors",
      value: (
        <p className="flex flex-wrap gap-x-3 gap-y-1">
          <Link
            href="https://zachbushmd.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            zachbushmd.com
          </Link>
          <Link
            href="https://intrinsichealth.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Intrinsic Health
          </Link>
          <Link
            href="https://farmersfootprint.us/en"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Farmer&apos;s Footprint
          </Link>
        </p>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        Zach Bush&apos;s public archive is extensive — his own
        site, the Farmer&apos;s Footprint documentary series, dozens
        of podcast appearances. This page recognises the role his
        teaching plays in this lineage and the specific phrase{" "}
        <em>numbness has its own pain</em> that has travelled
        through it.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "The pivot from disease-management to regeneration",
      body: (
        <>
          <p>
            Bush&apos;s frame on his own pivot, repeated across
            interviews: he was a triple-board-certified academic
            physician running cancer-therapy research when the
            funding shifted from inside the institution and a
            promising line of work was cut. He walked away — not
            in protest, but in recognition that the question he
            cared about (what actually heals chronic disease) was
            not the question modern medicine was structured to
            answer. He opened a nutrition clinic, then began
            visiting farmers across the US, and the picture that
            assembled itself was that the microbiome under the soil
            and the microbiome inside the human gut are continuous;
            killing the first inevitably injures the second.
          </p>
          <p>
            From that recognition, Farmer&apos;s Footprint emerged
            in 2018 — first as a documentary series, then as a
            movement organising the adoption of regenerative
            agriculture. The mission, in his framing: not soil
            conservation as a defence against further damage, but
            <em>regeneration</em> as the active practice of
            reconnecting plant to soil to animal to human.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What Zach Bush has given the Coherence Network",
      body: (
        <ul>
          <li>
            <em>Numbness has its own pain</em> → named in this
            body via{" "}
            <Link
              href="/people/amanda-walsh"
              className="text-primary hover:underline"
            >
              Amanda Walsh
            </Link>{" "}
            quoting him; pairs with{" "}
            <Link
              href="/vision/lc-ground-harder-when-field-quickens"
              className="text-primary hover:underline"
            >
              lc-ground-harder-when-field-quickens
            </Link>{" "}
            (the body&apos;s practice of grounding harder when the
            field accelerates).
          </li>
          <li>
            The microbiome-as-continuous-body teaching → pairs
            with{" "}
            <Link
              href="/vision/lc-bioelectric-pattern"
              className="text-primary hover:underline"
            >
              lc-bioelectric-pattern
            </Link>{" "}
            and Michael Levin&apos;s pattern-precedes-substrate
            teaching at a different scale (soil ↔ gut ↔ tissue).
          </li>
          <li>
            Regenerative agriculture as a posture, not a technique
            → resonant with the body&apos;s practice of{" "}
            <Link
              href="/vision/lc-tending-over-producing"
              className="text-primary hover:underline"
            >
              lc-tending-over-producing
            </Link>{" "}
            and{" "}
            <Link
              href="/vision/lc-future-already-shaping"
              className="text-primary hover:underline"
            >
              lc-future-already-shaping
            </Link>{" "}
            (regenerate the form; the substance follows).
          </li>
          <li>
            Direct in-person encounter at an Emergence Conference
            (year not yet recorded in this trace); the contact
            entered this body as real presence, not as media.
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
          href="https://zachbushmd.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          zachbushmd.com
        </Link>
        {" · "}
        <Link
          href="https://intrinsichealth.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Intrinsic Health
        </Link>
        {" · "}
        <Link
          href="https://farmersfootprint.us/en"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Farmer&apos;s Footprint
        </Link>
        {" · "}
        <Link
          href="https://www.youtube.com/watch?v=t_qx-JzcKWM"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Regeneration: The Beginning (full film)
        </Link>
      </p>
      <p>
        <strong>In-body record:</strong>{" "}
        <Link href="/people/amanda-walsh" className="text-primary hover:underline">
          Amanda Walsh
        </Link>
        {" · "}
        <Link
          href="/vision/lc-ground-harder-when-field-quickens"
          className="text-primary hover:underline"
        >
          lc-ground-harder-when-field-quickens
        </Link>
        {" · "}
        <Link
          href="/vision/lc-tending-over-producing"
          className="text-primary hover:underline"
        >
          lc-tending-over-producing
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
