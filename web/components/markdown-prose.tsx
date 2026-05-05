// Tiny markdown subset renderer for translated body prose.
//
// Used by surfaces like /silence/{slug} where the body of a section
// lives in messages/{lang}.json as a single string. The string carries
// a small set of inline markup:
//   - blank line separates paragraphs
//   - a paragraph whose lines all begin with "- " becomes a bullet list
//   - inline *text* renders as <em>
//   - inline [label](href) renders as a Link via the L() helper
//
// Anything richer (tables, headings, code) belongs in its own component.

import type { ReactNode } from "react";
import { L } from "@/components/inline-link";

let rendererKey = 0;

function renderInline(text: string, keyBase: string): ReactNode[] {
  const out: ReactNode[] = [];
  // First split on links, then handle *em* within each non-link chunk.
  const linkRe = /\[([^\]]+)\]\(([^)]+)\)/g;
  let lastIdx = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  const pushPlain = (chunk: string) => {
    if (!chunk) return;
    const emRe = /\*([^*\n]+)\*/g;
    let li = 0;
    let em: RegExpExecArray | null;
    while ((em = emRe.exec(chunk)) !== null) {
      if (em.index > li) out.push(chunk.slice(li, em.index));
      out.push(<em key={`${keyBase}-e${i++}`}>{em[1]}</em>);
      li = em.index + em[0].length;
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

export function MarkdownProse({ text }: { text: string }) {
  rendererKey++;
  const baseKey = `mp${rendererKey}`;
  const blocks = text.split(/\n\n+/).map((b) => b.trim()).filter(Boolean);
  return (
    <>
      {blocks.map((block, idx) => {
        const lines = block.split("\n").map((l) => l.trim());
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
