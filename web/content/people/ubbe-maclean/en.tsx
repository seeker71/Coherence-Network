import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Ubbe MacLean | Coherence Network",
    description:
      "A doorway held open for Ubbe MacLean. The current public anchor is Instagram @ubbemaclean; further detail awaits Ubbe's own framing.",
  },
  breadcrumbName: "Ubbe MacLean",
  hero: {
    background:
      "radial-gradient(ellipse at 30% 25%, hsl(180 55% 60% / 0.55) 0%, transparent 55%), radial-gradient(ellipse at 80% 80%, hsl(255 30% 22% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(180 50% 60%) 0%, hsl(220 30% 38%) 50%, hsl(255 30% 18%) 100%)",
    eyebrow: "A doorway held open",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Ubbe MacLean",
    welcome: (
      <p>
        A cell in the body&apos;s wider field. The current public
        anchor is{" "}
        <Link
          href="https://www.instagram.com/ubbemaclean/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-[hsl(var(--primary))] hover:underline"
        >
          Instagram @ubbemaclean
        </Link>
        . The page is held here as a doorway awaiting Ubbe&apos;s
        own framing — the work tended, the rooms held, the
        lineage carried forward.
      </p>
    ),
  },
  facts: [
    {
      label: "Public anchor",
      value: (
        <Link
          href="https://www.instagram.com/ubbemaclean/"
          target="_blank"
          rel="noopener noreferrer"
          className="hover:text-primary transition-colors"
        >
          Instagram — @ubbemaclean
        </Link>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        This page was first deleted as a placeholder during a
        graph-dedup pass; Urs named the real person behind the
        name and the doorway returns. Ubbe is invited to replace
        any part of this page with their own words. Until then
        the body holds the name and the public anchor without
        inventing detail.
      </p>
    ),
  },
  articles: [
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What Ubbe MacLean has given the Coherence Network",
      body: (
        <p>
          Presence and recognition in the wider field of the
          network&apos;s awareness. Specifics live in Ubbe&apos;s
          voice; the body holds the placeholder open with care
          rather than letting it compost again.
        </p>
      ),
    },
  ],
  footer: (
    <>
      <p>
        <strong>Public anchor:</strong>{" "}
        <Link
          href="https://www.instagram.com/ubbemaclean/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Instagram — @ubbemaclean
        </Link>
      </p>
      <p className="text-xs italic">
        A small networked community holds this profile open. Ubbe
        is welcome to write themselves into it.
      </p>
    </>
  ),
};

export default content;
