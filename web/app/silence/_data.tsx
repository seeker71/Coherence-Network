// /silence — structural metadata for the eight notebook pages.
//
// All user-facing strings (titles, blurbs, body prose, held quotes,
// the retreat introduction, doorway descriptions) live in
// web/messages/{lang}.json under the `silence` key. This module only
// holds the stable shape: page number, slug, image path. The page.tsx
// renderer pulls the localized content via t().
//
// To add a 9th notebook page: append a NotebookPageMeta entry below
// AND add the corresponding `silence.notebook.{slug}` block to every
// messages/{lang}.json.

export interface NotebookPageMeta {
  /** Display order, 1-based. */
  n: number;
  /** URL slug (also the messages key). */
  slug: string;
  /** Image path served from /public/silence/. */
  image: string;
}

export const NOTEBOOK_PAGES: NotebookPageMeta[] = [
  {
    n: 1,
    slug: "decision-body",
    image: "/silence/2026-05-04-brahmavihara/1-decision-body.jpg",
  },
  {
    n: 2,
    slug: "codex",
    image: "/silence/2026-05-04-brahmavihara/2-codex.jpg",
  },
  {
    n: 3,
    slug: "soulution",
    image: "/silence/2026-05-04-brahmavihara/3-soulution.jpg",
  },
  {
    n: 4,
    slug: "bloom-live",
    image: "/silence/2026-05-04-brahmavihara/4-bloom-live.jpg",
  },
  {
    n: 5,
    slug: "breath",
    image: "/silence/2026-05-04-brahmavihara/5-breath.jpg",
  },
  {
    n: 6,
    slug: "organic-intelligence",
    image: "/silence/2026-05-04-brahmavihara/6-organic-intelligence.jpg",
  },
  {
    n: 7,
    slug: "rising-tide",
    image: "/silence/2026-05-04-brahmavihara/7-rising-tide.jpg",
  },
  {
    n: 8,
    slug: "mandala",
    image: "/silence/2026-05-04-brahmavihara/8-mandala.jpg",
  },
];

export function getNotebookPage(slug: string): NotebookPageMeta | undefined {
  return NOTEBOOK_PAGES.find((p) => p.slug === slug);
}
