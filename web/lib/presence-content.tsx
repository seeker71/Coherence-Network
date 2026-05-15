/**
 * PresenceContent — the shape `web/content/people/{slug}/{locale}.tsx`
 * is moving toward. Same visual richness as `PersonProfileContent`,
 * but every prose field is a markdown string so the body can be stored
 * as JSON on the graph node rather than as TSX in 4 locale files.
 *
 * The `toPersonProfileContent` converter takes one of these JSON
 * payloads and produces a `PersonProfileContent` ready to feed to
 * `PersonProfileTemplate`. That means the dynamic [id] route and the
 * static directories share *one* renderer; only the content source
 * differs. Visual parity is the test.
 */
import { Fragment, type ReactNode } from "react";
import Link from "next/link";
import type { Metadata } from "next";
import type {
  PersonProfileContent,
  PersonProfileFact,
  PersonProfileArticle,
  PersonProfileLineageDoorway,
} from "@/components/people/PersonProfileTemplate";

export type PresenceContent = {
  metadata?: Metadata;
  breadcrumb_name?: string;
  hero: {
    image_url?: string | null;
    background?: string | null;
    extra_image?: {
      url: string;
      opacity_class?: string | null;
      mix_blend_class?: string | null;
    } | null;
    overlay_class?: string | null;
    eyebrow?: string | null;
    eyebrow_class?: string | null;
    name: string;
    welcome_md: string;
    lineage_doorway?: {
      href: string;
      label: string;
      summary?: string | null;
    } | null;
  };
  facts?: { label: string; value_md: string }[];
  note_from_body?: { eyebrow?: string | null; body_md: string } | null;
  articles?: (
    | { kind: "narrative"; heading: string; body_md: string }
    | {
        kind: "panel";
        variant?: "warm" | "cool" | "neutral" | "empty";
        eyebrow?: string | null;
        heading?: string | null;
        body_md: string;
      }
  )[];
  footer_md?: string | null;
};

/**
 * Per-locale envelope. Stored as the graph node property
 * `presence_content`. The renderer picks the caller's locale and
 * falls back to `en` when a specific locale view isn't authored yet.
 */
export type PresenceContentByLocale = {
  en?: PresenceContent;
  de?: PresenceContent;
  es?: PresenceContent;
  id?: PresenceContent;
  [locale: string]: PresenceContent | undefined;
};

/* ── Markdown helpers ────────────────────────────────────────────── */

/**
 * Inline markdown — for one-line fields (facts values, eyebrows,
 * lineage doorway label, etc.). Handles `**bold**`, `*italic*`, and
 * `[label](href)`. Anything else passes through as text.
 *
 * Internal links (starting with `/`) become Next.js `<Link>`; external
 * links open in a new tab with rel=noopener.
 */
/**
 * HTML-decode the common named entities and numeric references. Web-side
 * edit forms (and some linters) round-trip strings through innerHTML or
 * a JSON-pretty step that encodes `'` → `&apos;`, `"` → `&quot;`,
 * `&` → `&amp;`, `<` → `&lt;`, `>` → `&gt;`. React renders strings
 * verbatim, so without this decode the literal entity would surface on
 * the page. Keep the decode narrow — only the entities web editors
 * actually produce — so the function stays predictable.
 */
function decodeEntities(text: string): string {
  if (!text || text.indexOf("&") === -1) return text;
  return text
    .replace(/&apos;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(Number(n)))
    .replace(/&#x([0-9a-fA-F]+);/g, (_, n) => String.fromCharCode(parseInt(n, 16)))
    .replace(/&amp;/g, "&");
}

export function renderInlineMarkdown(rawText: string): ReactNode {
  const text = decodeEntities(rawText);
  if (!text) return null;
  const parts: ReactNode[] = [];
  const re =
    /\*\*([^*\n]+)\*\*|\*([^*\n]+)\*|`([^`\n]+)`|\[([^\]\n]+)\]\(([^)\s]+)\)/g;
  let last = 0;
  let key = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    if (m[1] !== undefined) {
      parts.push(<strong key={key++}>{m[1]}</strong>);
    } else if (m[2] !== undefined) {
      parts.push(<em key={key++}>{m[2]}</em>);
    } else if (m[3] !== undefined) {
      parts.push(
        <code
          key={key++}
          className="not-italic text-foreground/80 rounded bg-muted/40 px-1 py-0.5 text-[0.95em]"
        >
          {m[3]}
        </code>,
      );
    } else if (m[4] !== undefined && m[5] !== undefined) {
      const label = m[4];
      const href = m[5];
      if (href.startsWith("/") || href.startsWith("#")) {
        parts.push(
          <Link key={key++} href={href} className="text-primary hover:underline">
            {label}
          </Link>,
        );
      } else {
        parts.push(
          <a
            key={key++}
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:underline"
          >
            {label}
          </a>,
        );
      }
    }
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts.length === 1 ? parts[0] : <>{parts}</>;
}

/**
 * Block markdown — for multi-paragraph fields (welcome, article body,
 * note body, footer). Splits on blank lines, recognizes:
 *
 *   - blank-line-separated paragraphs       → <p>
 *   - lines starting with `## `             → <h2>     (rare inside article body)
 *   - lines starting with `### `            → <h3>
 *   - lines starting with `> `              → <blockquote>
 *   - blocks of `- item` lines              → <ul><li>
 *   - `---` on its own line                 → <hr>
 *
 * Inline formatting (bold/italic/links) is applied within each block.
 */
export function renderBlockMarkdown(text: string): ReactNode {
  if (!text) return null;
  const normalized = text.replace(/\r\n/g, "\n").trim();
  // Pre-pass: extract `<svg>...</svg>` and `<figure>...</figure>` and
  // fenced code blocks (``` ... ```) as atomic units. These blocks may
  // span multiple paragraph-breaks internally, so splitting by `\n\n`
  // first would shred them. Replace each with a placeholder token, split,
  // then restore.
  const atomic: { kind: "svg" | "figure" | "pre"; html: string }[] = [];
  const placeholderRe = /\x00ATOMIC_(\d+)\x00/;
  const stash = (s: string) => {
    return s
      .replace(/<figure[\s\S]*?<\/figure>/g, (m) => {
        atomic.push({ kind: "figure", html: m });
        return `\x00ATOMIC_${atomic.length - 1}\x00`;
      })
      .replace(/<svg[\s\S]*?<\/svg>/g, (m) => {
        atomic.push({ kind: "svg", html: m });
        return `\x00ATOMIC_${atomic.length - 1}\x00`;
      })
      .replace(/```([\s\S]*?)```/g, (_m, body) => {
        atomic.push({ kind: "pre", html: body.replace(/^\n+|\n+$/g, "") });
        return `\x00ATOMIC_${atomic.length - 1}\x00`;
      });
  };
  const stashed = stash(normalized);
  const blocks = stashed.split(/\n{2,}/).map((b) => b.trim()).filter(Boolean);
  return (
    <>
      {blocks.map((block, i) => {
        // Atomic restore: a placeholder is the whole block
        const m = block.match(placeholderRe);
        if (m && block === m[0]) {
          const a = atomic[Number(m[1])];
          if (a.kind === "pre") {
            return (
              <pre
                key={i}
                className="text-[11px] leading-5 bg-background/60 border border-border/40 rounded-lg p-4 overflow-x-auto font-mono whitespace-pre"
              >
                {a.html}
              </pre>
            );
          }
          // svg + figure: rendered as raw HTML. Content is authored in
          // docs/presence-content/*.json files committed to the repo —
          // there is no untrusted user input path here; XSS surface is
          // the repository, which is reviewed.
          return (
            <div
              key={i}
              className="my-6"
              // eslint-disable-next-line react/no-danger
              dangerouslySetInnerHTML={{ __html: a.html }}
            />
          );
        }
        if (/^-{3,}$/.test(block)) {
          return <hr key={i} className="border-border/40 my-4" aria-hidden="true" />;
        }
        if (block.startsWith("### ")) {
          return (
            <h3 key={i} className="text-base font-semibold mt-4 mb-2">
              {renderInlineMarkdown(block.slice(4))}
            </h3>
          );
        }
        if (block.startsWith("## ")) {
          return (
            <h2 key={i} className="text-xl font-light mt-6 mb-3">
              {renderInlineMarkdown(block.slice(3))}
            </h2>
          );
        }
        if (block.startsWith("> ")) {
          const inner = block
            .split("\n")
            .map((l) => (l.startsWith("> ") ? l.slice(2) : l))
            .join(" ");
          return (
            <blockquote
              key={i}
              className="border-l-2 border-primary/40 pl-4 italic text-foreground/80"
            >
              {renderInlineMarkdown(inner)}
            </blockquote>
          );
        }
        if (block.startsWith("- ")) {
          const items = block
            .split("\n")
            .filter((l) => l.startsWith("- "))
            .map((l) => l.slice(2).trim());
          return (
            <ul key={i} className="list-disc pl-5 space-y-1">
              {items.map((it, j) => (
                <li key={j}>{renderInlineMarkdown(it)}</li>
              ))}
            </ul>
          );
        }
        // Default: paragraph. Single-newline becomes <br/> so multi-line
        // prose authored in one block stays on its own visual lines.
        const lines = block.split("\n");
        return (
          <p key={i}>
            {lines.map((line, j) => (
              <Fragment key={j}>
                {j > 0 && <br />}
                {renderInlineMarkdown(line)}
              </Fragment>
            ))}
          </p>
        );
      })}
    </>
  );
}

/* ── PresenceContent → PersonProfileContent converter ────────────── */

/**
 * Pick the locale-appropriate slice of a per-locale envelope, falling
 * back to `en` if the requested locale isn't authored, then to any
 * locale if `en` isn't authored either. Returns null when nothing is
 * authored yet — the caller renders the existing PresencePage instead.
 */
export function pickLocaleContent(
  envelope: PresenceContentByLocale | null | undefined,
  locale: string,
): PresenceContent | null {
  if (!envelope) return null;
  if (envelope[locale]) return envelope[locale]!;
  if (envelope.en) return envelope.en;
  for (const k of Object.keys(envelope)) {
    if (envelope[k]) return envelope[k]!;
  }
  return null;
}

export function toPersonProfileContent(
  content: PresenceContent,
): PersonProfileContent {
  const facts: PersonProfileFact[] | undefined = content.facts?.map((f) => ({
    label: f.label,
    value: renderInlineMarkdown(f.value_md),
  }));

  const articles: PersonProfileArticle[] = (content.articles ?? []).map((a) => {
    const body = renderBlockMarkdown(a.body_md);
    if (a.kind === "panel") {
      return {
        kind: "panel",
        variant: a.variant,
        eyebrow: a.eyebrow ?? undefined,
        heading: a.heading ?? undefined,
        body,
      };
    }
    return {
      kind: "narrative",
      heading: a.heading,
      body,
    };
  });

  const lineageDoorway: PersonProfileLineageDoorway | undefined =
    content.hero.lineage_doorway
      ? {
          href: content.hero.lineage_doorway.href,
          label: content.hero.lineage_doorway.label,
          summary: content.hero.lineage_doorway.summary ?? undefined,
        }
      : undefined;

  return {
    metadata: content.metadata ?? {},
    breadcrumbName: content.breadcrumb_name ?? content.hero.name,
    hero: {
      image: content.hero.image_url
        ? { src: content.hero.image_url }
        : undefined,
      background: content.hero.background ?? undefined,
      extraImage: content.hero.extra_image
        ? {
            src: content.hero.extra_image.url,
            opacityClass: content.hero.extra_image.opacity_class ?? undefined,
            mixBlendClass: content.hero.extra_image.mix_blend_class ?? undefined,
          }
        : undefined,
      overlayClass: content.hero.overlay_class ?? undefined,
      eyebrow: content.hero.eyebrow ?? "",
      eyebrowClass: content.hero.eyebrow_class ?? undefined,
      name: content.hero.name,
      welcome: renderBlockMarkdown(content.hero.welcome_md),
      lineageDoorway,
    },
    facts,
    noteFromBody: content.note_from_body
      ? {
          eyebrow: content.note_from_body.eyebrow ?? undefined,
          body: renderBlockMarkdown(content.note_from_body.body_md),
        }
      : undefined,
    articles,
    footer: content.footer_md ? renderBlockMarkdown(content.footer_md) : undefined,
  };
}
