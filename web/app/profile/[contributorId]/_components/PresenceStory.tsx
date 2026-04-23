import { inlineMarkdownToHtml } from "@/lib/vision-utils";

/**
 * Renders a presence's story (markdown stored on the node's description)
 * as warm, readable prose — the contributor's own voice presented first,
 * before any metrics or keys. Supports paragraphs, ## and ### headings,
 * > blockquotes, inline bold / italic / links.
 *
 * The first `# Title` heading is stripped — the page already shows the
 * contributor's name as h1, so repeating it inline would read like a
 * rendering bug.
 */
export function PresenceStory({
  content,
  displayName,
}: {
  content: string | null | undefined;
  displayName: string;
}) {
  if (!content || !content.trim()) return null;

  // Strip leading `# Heading` if it matches the display name (or any single
  // h1 at the top of the content — the page already shows the name).
  let body = content.trim();
  if (body.startsWith("# ")) {
    const firstLineEnd = body.indexOf("\n");
    body = body.slice(firstLineEnd === -1 ? body.length : firstLineEnd + 1).trimStart();
  }

  // Also drop any YAML frontmatter if it leaked through
  if (body.startsWith("---\n")) {
    const end = body.indexOf("\n---\n", 4);
    if (end !== -1) body = body.slice(end + 5).trimStart();
  }

  const blocks = body.split(/\n\n+/);

  return (
    <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 sm:p-8 space-y-5">
      <p className="text-xs uppercase tracking-widest text-muted-foreground">
        Presence
      </p>
      <div className="space-y-5 max-w-3xl">
        {blocks.map((block, i) => {
          const trimmed = block.trim();
          if (!trimmed) return null;

          if (trimmed.startsWith("## ")) {
            return (
              <h2
                key={i}
                className="text-xl font-light text-stone-300 pt-3 pb-1"
              >
                {trimmed.slice(3)}
              </h2>
            );
          }
          if (trimmed.startsWith("### ")) {
            return (
              <h3
                key={i}
                className="text-base font-light text-stone-400 pt-2 pb-1"
              >
                {trimmed.slice(4)}
              </h3>
            );
          }
          if (trimmed.startsWith("> ")) {
            const quoteText = trimmed
              .split("\n")
              .map((l) => l.replace(/^>\s?/, ""))
              .join(" ");
            return (
              <blockquote
                key={i}
                className="border-l-2 border-amber-500/30 pl-4 italic text-foreground/80 leading-relaxed"
                dangerouslySetInnerHTML={{
                  __html: inlineMarkdownToHtml(quoteText),
                }}
              />
            );
          }
          if (trimmed === "---") {
            return <hr key={i} className="border-border/30 my-2" />;
          }

          // Regular paragraph — join wrapped lines into one flowing paragraph
          const paragraphText = trimmed.replace(/\n/g, " ");
          return (
            <p
              key={i}
              className="text-base text-foreground/85 leading-relaxed"
              dangerouslySetInnerHTML={{
                __html: inlineMarkdownToHtml(paragraphText),
              }}
            />
          );
        })}
      </div>
    </section>
  );
}
