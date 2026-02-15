"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type LineageEntry = {
  page_path: string;
  page_title: string;
  idea_id: string;
  root_idea_id: string;
  origin_type: "system" | "external_contributor";
  system_tied: boolean;
  origin_note: string;
  spec?: { id?: string; path?: string };
  spec_url?: string;
  process_doc?: string;
  process_doc_url?: string;
  source_refs?: string[];
  endpoint_examples?: Array<{ method: string; path: string; example: string }>;
};

function normalizePath(pathname: string): string {
  if (!pathname) return "/";
  const clean = pathname.split("?")[0].replace(/\/+$/, "") || "/";
  if (/^\/project\/[^/]+\/[^/]+$/.test(clean)) return "/project/[ecosystem]/[name]";
  return clean;
}

export default function PageLineageBanner() {
  const pathname = usePathname();
  const pagePath = useMemo(() => normalizePath(pathname || "/"), [pathname]);
  const [entry, setEntry] = useState<LineageEntry | null>(null);
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await fetch(
          `${API_URL}/api/inventory/page-lineage?page_path=${encodeURIComponent(pagePath)}`,
          { cache: "no-store" }
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        if (cancelled) return;
        setEntry((json.entry || null) as LineageEntry | null);
        setMissing(!json.entry);
      } catch {
        if (cancelled) return;
        setEntry(null);
        setMissing(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [pagePath]);

  const ontologyUrl = `${API_URL}/api/inventory/page-lineage?page_path=${encodeURIComponent(pagePath)}`;
  const ideaUrl = entry ? `${API_URL}/api/ideas/${encodeURIComponent(entry.idea_id)}` : "";
  const rootIdeaUrl = entry ? `${API_URL}/api/ideas/${encodeURIComponent(entry.root_idea_id)}` : "";

  return (
    <div className="border-b border-border bg-muted/40 px-4 py-2 text-xs">
      {!entry && missing && (
        <p className="text-destructive">
          Missing page lineage mapping for <code>{pagePath}</code>. Add it in <code>api/config/page_lineage.json</code>.
        </p>
      )}
      {entry && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span>
            idea:{" "}
            <a className="underline" href={ideaUrl} target="_blank" rel="noreferrer">
              {entry.idea_id}
            </a>
          </span>
          <span>
            root idea:{" "}
            <a className="underline" href={rootIdeaUrl} target="_blank" rel="noreferrer">
              {entry.root_idea_id}
            </a>
          </span>
          <span>
            ontology:{" "}
            <a className="underline" href={ontologyUrl} target="_blank" rel="noreferrer">
              /api/inventory/page-lineage
            </a>
          </span>
          {entry.spec_url && (
            <span>
              spec:{" "}
              <a className="underline" href={entry.spec_url} target="_blank" rel="noreferrer">
                {entry.spec?.id || entry.spec?.path}
              </a>
            </span>
          )}
          {entry.process_doc_url && (
            <span>
              process/pseudocode:{" "}
              <a className="underline" href={entry.process_doc_url} target="_blank" rel="noreferrer">
                {entry.process_doc}
              </a>
            </span>
          )}
          {entry.source_refs?.[0] && (
            <span>
              source: <code>{entry.source_refs[0]}</code>
            </span>
          )}
          {entry.endpoint_examples?.[0] && (
            <span>
              endpoint example: <code>{entry.endpoint_examples[0].method} {entry.endpoint_examples[0].path}</code>
            </span>
          )}
          {entry.origin_type === "external_contributor" && (
            <span className="text-amber-700">
              contributor-origin idea {entry.system_tied ? "linked" : "not yet linked"} to core system
            </span>
          )}
          {entry.origin_type === "system" && <span className="text-muted-foreground">system-origin idea</span>}
          <Link className="underline" href="/portfolio">
            inspect in portfolio
          </Link>
        </div>
      )}
    </div>
  );
}
