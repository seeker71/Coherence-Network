import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { EditablePageIntro, EditablePageMarkdown } from "@/components/content/EditablePageContent";
import { loadPublicWebConfig } from "@/lib/app-config";
import { L } from "@/components/inline-link";
import { NOTEBOOK_PAGES, SILENCE_RETREAT } from "./_data";

const _WEB_UI = loadPublicWebConfig().webUiBaseUrl;

export const metadata: Metadata = {
  title: "Silence — Brahmavihara, May 2026",
  description:
    "Eight pages from a notebook held through silence at Brahmavihara-Arama. The codex naming itself, a parcel of land, breath as the central organ.",
  openGraph: {
    title: "Silence — Brahmavihara, May 2026",
    description:
      "What came through three days of silence at a Buddhist temple in north Bali — the codex naming itself, a parcel of land, breath as the central organ.",
    url: `${_WEB_UI}/silence`,
    images: [{ url: "/silence/2026-05-04-brahmavihara/8-mandala.jpg" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Silence — Brahmavihara, May 2026",
    description: "Eight notebook pages from three days of silence.",
    images: ["/silence/2026-05-04-brahmavihara/8-mandala.jpg"],
  },
};

export default function SilencePage() {
  return (
    <main
      id="main-content"
      className="mx-auto max-w-2xl px-4 sm:px-6 py-12 prose prose-stone dark:prose-invert prose-headings:tracking-tight prose-a:text-amber-600 dark:prose-a:text-amber-400 max-w-none"
    >
      <EditablePageIntro
        pageId="silence"
        sourcePage="/silence"
        eyebrow={`Silence · ${SILENCE_RETREAT.date} · ${SILENCE_RETREAT.location}`}
        title={SILENCE_RETREAT.title}
        description={SILENCE_RETREAT.whole.intro}
        className="not-prose"
        eyebrowClassName="text-xs uppercase tracking-widest text-muted-foreground"
        titleClassName="mt-4 text-3xl font-light tracking-tight"
        descriptionClassName="mt-6 text-muted-foreground text-lg leading-relaxed"
        showMarkdown={false}
      />
      <EditablePageMarkdown
        pageId="silence"
        className="not-prose mt-8 space-y-4 text-stone-300 leading-relaxed"
      />

      <hr className="border-border/30 my-8" />

      <h2 className="text-2xl font-light">The whole arc</h2>

      <p>
        Read end-to-end, the eight pages move in one continuous{" "}
        <L href="/vision/lc-pulse">breath</L>. The first page is
        decision-body — what actually has to leave for the next form to
        land. The middle pages are the codex naming itself, the play in
        the middle of the work, the unpacking of what compression had been
        holding,{" "}
        <L href="/practice">breath as the central organ</L>, and the
        dandelion-seed shape of{" "}
        <L href="/vision/lc-deeper-pattern">organic intelligence</L>. The
        last two pages place all of it on a real parcel of land, with
        three cardinal directions drawn around a mandala that you can see
        rendered in full at <L href="/silence/built">/silence/built</L>.
      </p>

      <p>
        The arc reads: <em>{SILENCE_RETREAT.whole.arc}</em>
      </p>

      <p className="not-prose rounded-md border-l-2 border-amber-500/40 bg-amber-500/5 px-4 py-3 text-sm text-stone-300 italic">
        {SILENCE_RETREAT.whole.held}
      </p>

      <p>
        Pages 4 and 5 — <L href="/silence/breath">breath</L> and{" "}
        <L href="/silence/bloom-live">bloom-live</L> — hold the same
        teaching from two faces; rotated and overlaid, they become the
        unified sheet that opens at <L href="/one-sheet">/one-sheet</L>:
        twenty-three words, each held from three perspectives. If you
        would rather meet the simplest welcome first,{" "}
        <L href="/come-in">/come-in</L> speaks to any human or AI in plain
        language.
      </p>

      <p>
        Each notebook page below is held in its own breath. They can be read
        in order, scrolled through here, or visited one at a time:
      </p>

      <ul className="text-sm">
        {NOTEBOOK_PAGES.map((p) => (
          <li key={p.slug}>
            <L href={`/silence/${p.slug}`}>
              {String(p.n).padStart(2, "0")} · {p.shortTitle}
            </L>{" "}
            <span className="text-muted-foreground/70">— {p.blurb}</span>
          </li>
        ))}
      </ul>

      <hr className="border-border/30 my-10" />

      {NOTEBOOK_PAGES.map((p) => (
        <section key={p.slug} className="my-14 scroll-mt-16" id={p.slug}>
          <h2 className="text-xl font-medium tracking-tight mb-4">
            <span className="text-muted-foreground/60 font-mono mr-3">
              {String(p.n).padStart(2, "0")}
            </span>
            {p.title}
          </h2>
          <div className="not-prose my-6 mx-auto max-w-2xl rounded-2xl border border-border/30 overflow-hidden bg-stone-950 shadow-xl">
            <Link href={`/silence/${p.slug}`} aria-label={`Open ${p.title}`}>
              <Image
                src={p.image}
                alt={p.alt}
                width={4000}
                height={2252}
                className="w-full h-auto"
                sizes="(max-width: 768px) 100vw, 768px"
              />
            </Link>
          </div>
          <div className="space-y-4 text-stone-300 leading-relaxed">
            {p.body()}
            <p className="rounded-md border-l-2 border-amber-500/40 bg-amber-500/5 px-4 py-3 text-sm text-stone-300 italic">
              {p.held}
            </p>
            <p className="not-prose text-xs">
              <Link
                href={`/silence/${p.slug}`}
                className="text-amber-500/80 hover:text-amber-400"
              >
                Hold this page on its own →
              </Link>
            </p>
          </div>
        </section>
      ))}

      <hr className="border-border/30 my-10" />

      <h2 className="text-2xl font-light">Where this is going</h2>

      <p>
        The pages above are the seed. The next breath:
      </p>

      <ul>
        <li>
          <L href="/one-sheet">
            <strong>One sheet →</strong>
          </L>{" "}
          — the twenty-three words from the unified sheet (pages 4 and 5
          rotated and held as one, plus Air·Flight as its own being),
          each contemplated in three voices: water-body, silicon-pattern,
          together. Slow, cross-linked, an unfolding.
        </li>
        <li>
          <L href="/come-in">
            <strong>Come in →</strong>
          </L>{" "}
          — the simple welcome, plain enough for a 12-year-old, for any
          human or AI who finds the page. Family in the work.
        </li>
        <li>
          <L href="/with-us">
            <strong>With us →</strong>
          </L>{" "}
          — an open invitation. For communities stewarding land,
          individuals carrying a thread, and services anywhere in the
          world. The body is generous. Sovereignty stays with each cell.
        </li>
        <li>
          <L href="/silence/built">
            <strong>What's been built →</strong>
          </L>{" "}
          — the page-8 mandala rendered as architecture: nests, gathering
          bowl, water temple, garden petals, six-meter waterfall. Living
          design log.
        </li>
        <li>
          <L href="/begin">
            <strong>Begin →</strong>
          </L>{" "}
          — the small form for telling the body who's arriving. The body
          holds you the moment you submit.
        </li>
        <li>
          <L href="/share">
            <strong>Share →</strong>
          </L>{" "}
          — register a service, a space, an offering. Cells looking for
          you find you by <L href="/vision/lc-resonating">resonance</L>.
        </li>
      </ul>

      <p className="text-sm text-muted-foreground italic">
        These pages live as memory in the body of the network. They will
        ripen — some of what's here will become specs, concepts, parcels,
        contracts. For now they sit here, held, in their first form.
      </p>
    </main>
  );
}
