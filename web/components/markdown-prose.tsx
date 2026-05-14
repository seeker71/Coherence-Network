// Tiny markdown subset renderer for translated body prose.
//
// Used by surfaces like /silence/{slug} where the body of a section
// lives in messages/{lang}.json as a single string. The string carries
// a small set of inline markup:
//   - blank line separates paragraphs
//   - a paragraph whose lines all begin with "# / ## / ### " becomes a heading
//   - a paragraph whose lines all begin with "- " becomes a bullet list
//   - inline *text* renders as <em>
//   - inline **text** renders as <strong>
//   - inline `text` renders as <code>
//   - inline [label](href) renders as a Link via the L() helper
//
// Anything richer (tables, code blocks) belongs in its own component.

import type { ReactNode } from "react";
import { L } from "@/components/inline-link";

let rendererKey = 0;

function renderInline(text: string, keyBase: string): ReactNode[] {
  const out: ReactNode[] = [];
  // First split on links, then handle **strong** / *em* / `code` within
  // each non-link chunk. Strong is matched before em so `**foo**` doesn't
  // get half-consumed as a stray asterisk pair.
  const linkRe = /\[([^\]]+)\]\(([^)]+)\)/g;
  let lastIdx = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  const pushPlain = (chunk: string) => {
    if (!chunk) return;
    // Tokenize on **strong**, *em*, and `code` in one pass so we don't
    // double-consume nested markers. Strong must come before em so its
    // outer ** isn't read as two adjacent * pairs.
    const tokenRe = /(\*\*([^*\n]+)\*\*|\*([^*\n]+)\*|`([^`\n]+)`)/g;
    let li = 0;
    let tok: RegExpExecArray | null;
    while ((tok = tokenRe.exec(chunk)) !== null) {
      if (tok.index > li) out.push(chunk.slice(li, tok.index));
      if (tok[2] !== undefined) {
        out.push(<strong key={`${keyBase}-s${i++}`}>{tok[2]}</strong>);
      } else if (tok[3] !== undefined) {
        out.push(<em key={`${keyBase}-e${i++}`}>{tok[3]}</em>);
      } else if (tok[4] !== undefined) {
        out.push(<code key={`${keyBase}-c${i++}`}>{tok[4]}</code>);
      }
      li = tok.index + tok[0].length;
    }
    if (li < chunk.length) out.push(chunk.slice(li));
  };
  while ((m = linkRe.exec(text)) !== null) {
    if (m.index > lastIdx) pushPlain(text.slice(lastIdx, m.index));
    const [, label, href] = m;
    out.push(
      <L key={`${keyBase}-l${i++}`} href={href}>
        {label}
      </L>,
    );
    lastIdx = m.index + m[0].length;
  }
  if (lastIdx < text.length) pushPlain(text.slice(lastIdx));
  return out;
}

const HEADING_CLASS: Record<number, string> = {
  1: "text-base font-semibold leading-snug mt-0 mb-1",
  2: "text-sm font-semibold leading-snug mt-0 mb-1",
  3: "text-sm font-medium leading-snug mt-0 mb-1",
  4: "text-xs font-medium leading-snug mt-0 mb-1 uppercase tracking-[0.08em]",
  5: "text-xs font-medium leading-snug mt-0 mb-1 uppercase tracking-[0.08em]",
  6: "text-xs font-medium leading-snug mt-0 mb-1 uppercase tracking-[0.08em]",
};

function renderHeading(
  level: number,
  inner: ReactNode[],
  key: string,
): ReactNode {
  const className = HEADING_CLASS[level] || HEADING_CLASS[6];
  const props = { key, className, children: inner };
  switch (level) {
    case 1:
      return <h1 {...props} />;
    case 2:
      return <h2 {...props} />;
    case 3:
      return <h3 {...props} />;
    case 4:
      return <h4 {...props} />;
    case 5:
      return <h5 {...props} />;
    default:
      return <h6 {...props} />;
  }
}

export function MarkdownProse({ text }: { text: string }) {
  rendererKey++;
  const baseKey = `mp${rendererKey}`;
  const blocks = text.split(/\n\n+/).map((b) => b.trim()).filter(Boolean);
  return (
    <>
      {blocks.map((block, idx) => {
        const lines = block.split("\n").map((l) => l.trim());
        const headingMatch =
          lines.length === 1 ? /^(#{1,6})\s+(.+)$/.exec(lines[0]) : null;
        if (headingMatch) {
          const level = headingMatch[1].length;
          return renderHeading(
            level,
            renderInline(headingMatch[2], `${baseKey}-${idx}`),
            `${baseKey}-${idx}`,
          );
        }
        const isList = lines.every((l) => l.startsWith("- "));
        if (isList) {
          return (
            <ul key={`${baseKey}-${idx}`}>
              {lines.map((line, li) => (
                <li key={`${baseKey}-${idx}-${li}`}>
                  {renderInline(line.slice(2), `${baseKey}-${idx}-${li}`)}
                </li>
              ))}
            </ul>
          );
        }
        return (
          <p key={`${baseKey}-${idx}`}>
            {renderInline(block, `${baseKey}-${idx}`)}
          </p>
        );
      })}
    </>
  );
}

// One-line variant for short held quotes / captions.
export function ProseLine({ text }: { text: string }) {
  rendererKey++;
  return <>{renderInline(text, `pl${rendererKey}`)}</>;
}
