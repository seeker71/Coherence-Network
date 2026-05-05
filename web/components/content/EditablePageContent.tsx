"use client";

import { useEffect, useMemo, useState } from "react";

import { useReadPing } from "@/hooks/useViewTracking";
import { getApiBase } from "@/lib/api";
import { inlineMarkdownToHtml } from "@/lib/vision-utils";
import { useLocale } from "@/components/MessagesProvider";

type PageView = {
  id: string;
  lang: string;
  content_title: string;
  content_description: string;
  content_markdown: string;
  status: string;
};

type TranslationListResponse = {
  items?: PageView[];
};

type EditablePageProps = {
  pageId: string;
  sourcePage: string;
  eyebrow?: string;
  title: string;
  description?: string;
  className?: string;
  eyebrowClassName?: string;
  titleClassName?: string;
  descriptionClassName?: string;
  markdownClassName?: string;
  showMarkdown?: boolean;
};

function chooseView(items: PageView[], lang: string): PageView | null {
  const canonical = items.filter((item) => item.status === "canonical");
  return (
    canonical.find((item) => item.lang === lang) ||
    canonical.find((item) => item.lang === "en") ||
    canonical[0] ||
    null
  );
}

function usePageView(pageId: string): PageView | null {
  const lang = useLocale();
  const [view, setView] = useState<PageView | null>(null);

  useEffect(() => {
    let alive = true;

    fetch(`${getApiBase()}/api/translations/page/${encodeURIComponent(pageId)}`, {
      cache: "no-store",
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((body: TranslationListResponse | null) => {
        if (!alive || !body?.items) return;
        setView(chooseView(body.items, lang));
      })
      .catch(() => {
        if (alive) setView(null);
      });

    return () => {
      alive = false;
    };
  }, [lang, pageId]);

  return view;
}

function MarkdownBlocks({
  content,
  className = "",
}: {
  content: string;
  className?: string;
}) {
  const blocks = useMemo(() => content.split(/\n{2,}/), [content]);

  if (!content.trim()) return null;

  return (
    <div className={className || "space-y-4 text-sm text-muted-foreground leading-relaxed"}>
      {blocks.map((block, index) => {
        const trimmed = block.trim();
        if (!trimmed) return null;
        if (trimmed.startsWith("# ") && !trimmed.startsWith("## ")) {
          return null;
        }
        if (trimmed.startsWith("## ") || trimmed.startsWith("### ")) {
          const isH3 = trimmed.startsWith("### ");
          const lines = trimmed.split("\n");
          const heading = lines[0].slice(isH3 ? 4 : 3).trim();
          const rest = lines.slice(1).join("\n").trim();
          return (
            <section key={`${heading}-${index}`} className="space-y-2">
              {isH3 ? (
                <h3 className="text-base font-medium text-foreground">{heading}</h3>
              ) : (
                <h2 className="text-xl font-semibold text-foreground">{heading}</h2>
              )}
              {rest && (
                <p
                  dangerouslySetInnerHTML={{ __html: inlineMarkdownToHtml(rest) }}
                />
              )}
            </section>
          );
        }
        if (trimmed.startsWith("> ")) {
          return (
            <blockquote
              key={`quote-${index}`}
              className="border-l-2 border-primary/40 pl-4 italic"
              dangerouslySetInnerHTML={{
                __html: inlineMarkdownToHtml(trimmed.slice(2).trim()),
              }}
            />
          );
        }
        if (trimmed.startsWith("- ")) {
          const items = trimmed
            .split("\n")
            .map((line) => line.trim())
            .filter((line) => line.startsWith("- "));
          return (
            <ul key={`list-${index}`} className="space-y-2 pl-5">
              {items.map((item, itemIndex) => (
                <li
                  key={`${index}-${itemIndex}`}
                  className="list-disc"
                  dangerouslySetInnerHTML={{
                    __html: inlineMarkdownToHtml(item.slice(2).trim()),
                  }}
                />
              ))}
            </ul>
          );
        }
        return (
          <p
            key={`p-${index}`}
            dangerouslySetInnerHTML={{ __html: inlineMarkdownToHtml(trimmed) }}
          />
        );
      })}
    </div>
  );
}

export function EditablePageIntro({
  pageId,
  sourcePage,
  eyebrow,
  title,
  description = "",
  className = "",
  eyebrowClassName = "text-sm text-muted-foreground",
  titleClassName = "text-3xl font-bold tracking-tight mb-2",
  descriptionClassName = "text-muted-foreground max-w-2xl leading-relaxed",
  markdownClassName,
  showMarkdown = true,
}: EditablePageProps) {
  const view = usePageView(pageId);
  const resolvedTitle = view?.content_title?.trim() || title;
  const resolvedDescription = view?.content_description?.trim() || description;
  const markdown = view?.content_markdown?.trim() || "";

  useReadPing({
    assetId: `page:${pageId}`,
    entityType: "page",
    entityId: pageId,
    sourcePage,
  });

  return (
    <div className={className}>
      {eyebrow && <p className={eyebrowClassName}>{eyebrow}</p>}
      <h1 className={titleClassName}>{resolvedTitle}</h1>
      {resolvedDescription && (
        <p className={descriptionClassName}>{resolvedDescription}</p>
      )}
      {showMarkdown && markdown && (
        <MarkdownBlocks
          content={markdown}
          className={markdownClassName || "mt-4 space-y-4 text-sm text-muted-foreground leading-relaxed"}
        />
      )}
    </div>
  );
}

export function PageReadPing({
  pageId,
  sourcePage,
}: {
  pageId: string;
  sourcePage: string;
}) {
  useReadPing({
    assetId: `page:${pageId}`,
    entityType: "page",
    entityId: pageId,
    sourcePage,
  });
  return null;
}

export function EditablePageMarkdown({
  pageId,
  className,
  containerClassName,
}: {
  pageId: string;
  className?: string;
  containerClassName?: string;
}) {
  const view = usePageView(pageId);
  const markdown = view?.content_markdown?.trim() || "";
  if (!markdown) return null;
  const blocks = <MarkdownBlocks content={markdown} className={className} />;
  if (containerClassName) {
    return <div className={containerClassName}>{blocks}</div>;
  }
  return blocks;
}
