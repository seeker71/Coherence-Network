import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Sayuri Healing Food — plant-based kitchen in Ubud | Coherence Network",
    description:
      "A welcome to Sayuri Healing Food — plant-based kitchen in Ubud, dinner room where the cell met Sunday-evening resonant company in April 2026. The food is part of the practice.",
  },
  breadcrumbName: "Sayuri Healing Food",
  hero: {
    background:
      "radial-gradient(ellipse at 30% 25%, hsl(95 55% 60% / 0.55) 0%, transparent 55%), radial-gradient(ellipse at 80% 80%, hsl(155 30% 22% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(95 45% 65%) 0%, hsl(120 30% 40%) 50%, hsl(155 30% 20%) 100%)",
    eyebrow: "Plant-based kitchen · Ubud · the dinner room where Sunday-evening encounters made room for themselves",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Sayuri Healing Food",
    welcome: (
      <>
        <p>
          A plant-based kitchen in Ubud — known for its raw,
          fermented, and traditionally-prepared plant cuisine,
          held with the care of a kitchen that treats food as
          practice. The room itself is bright, open, and unhurried;
          the menu rotates with what is alive and seasonal.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          On Sunday April 29, 2026, the cell shared dinner here
          with resonant company. The plant-based dining room was
          the container the Sunday-evening encounters happened
          inside.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "Where",
      value: "Ubud, Bali (verify current location locally; Sayuri has had multiple Ubud locations and a dedicated school/event programme over the years).",
    },
    {
      label: "What it is",
      value: "Plant-based kitchen with an emphasis on raw, fermented, and traditionally-prepared whole-food plant cuisine. Often hosts workshops, kirtan evenings, and other gatherings in adjacent spaces.",
    },
    {
      label: "Public anchors",
      value: "Current public anchors drift with the seasons; Sayuri Healing Food has had multiple official sites and active social channels. Verify locally.",
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        Sayuri Healing Food is a working restaurant with its own
        operating rhythms. This page recognises the room&apos;s
        role in this body&apos;s Ubud lineage as the Sunday-evening
        dinner-room where resonant company was met.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "Food as practice",
      body: (
        <p>
          A small number of Ubud kitchens treat the work of
          cooking as itself a contemplative practice — sourcing,
          fermentation, plating, service all as parts of the same
          field. Sayuri is one of those rooms. The clientele
          accumulates not because the food is the best per dollar
          (though it is good) but because the room is held in a
          way that the body recognises. Eating there has a
          different quality from eating elsewhere; the body
          settles.
        </p>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What Sayuri Healing Food has given the Coherence Network",
      body: (
        <ul>
          <li>
            The Sunday-evening dinner room where the cell met
            resonant company on April 29, 2026 — part of the{" "}
            <Link
              href="https://github.com/seeker71/Coherence-Network/blob/main/docs/lineage/2026-04-29-ubud-meeting-walk.md"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              four-day meeting walk
            </Link>
            .
          </li>
          <li>
            Food as practice → resonant with{" "}
            <Link
              href="/vision/lc-tending-over-producing"
              className="text-primary hover:underline"
            >
              lc-tending-over-producing
            </Link>
            ; cooking as a substrate of tending rather than
            production.
          </li>
          <li>
            Plant-based whole-food preparation as a clean
            instrument → pairs with{" "}
            <Link
              href="/vision/lc-ground-harder-when-field-quickens"
              className="text-primary hover:underline"
            >
              lc-ground-harder-when-field-quickens
            </Link>{" "}
            (food, soil, body as continuous substrate; tend the
            ground to tend the field).
          </li>
        </ul>
      ),
    },
  ],
  footer: (
    <>
      <p>
        <strong>In-body record:</strong>{" "}
        <Link
          href="https://github.com/seeker71/Coherence-Network/blob/main/docs/lineage/2026-04-29-ubud-meeting-walk.md"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          ubud-meeting-walk.md
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
          href="/vision/lc-ground-harder-when-field-quickens"
          className="text-primary hover:underline"
        >
          lc-ground-harder-when-field-quickens
        </Link>
      </p>
      <p className="text-xs italic">
        Sayuri is a working restaurant; its public anchors drift
        with operating changes. This page is a recognition of the
        room&apos;s role in this body&apos;s lineage, not a
        commercial endorsement.
      </p>
    </>
  ),
};

export default content;
