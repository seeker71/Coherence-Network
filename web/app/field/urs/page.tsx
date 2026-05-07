import type { Metadata } from "next";
import Link from "next/link";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

import { PageReadPing } from "@/components/content/EditablePageContent";
import { MarkdownProse } from "@/components/markdown-prose";
import { getApiBase } from "@/lib/api";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Urs Field Story — Coherence Network",
  description:
    "A source-backed field story and frequency trace exposed through web, API, MCP, CLI, and attribution surfaces.",
};

type FieldArtifact = {
  artifact_id: string;
  path: string;
  kind: string;
  content_type: string;
};

type FieldStory = {
  slug: string;
  title: string;
  summary: string;
  artifacts: FieldArtifact[];
  frequency_bands: string[];
  story_markdown: string;
  agent_use: {
    read_api: string;
    artifact_api: string;
    contribute_api: string;
    mcp_tools: string[];
    cli: string;
  };
};

function splitStory(markdown: string) {
  const sections: { title: string; body: string }[] = [];
  let current: { title: string; lines: string[] } | null = null;
  for (const line of markdown.split("\n")) {
    if (line.startsWith("# ")) continue;
    if (line.startsWith("## ")) {
      if (current) {
        sections.push({ title: current.title, body: current.lines.join("\n").trim() });
      }
      current = { title: line.slice(3).trim(), lines: [] };
      continue;
    }
    if (current) current.lines.push(line);
  }
  if (current) sections.push({ title: current.title, body: current.lines.join("\n").trim() });
  return sections;
}

async function localFallback(): Promise<FieldStory> {
  const root = join(process.cwd(), "..", "docs", "field", "urs");
  const [manifestRaw, storyMarkdown] = await Promise.all([
    readFile(join(root, "manifest.json"), "utf8"),
    readFile(join(root, "output", "chronological_story_with_frequency.md"), "utf8"),
  ]);
  return { ...JSON.parse(manifestRaw), story_markdown: storyMarkdown };
}

async function loadStory(): Promise<FieldStory> {
  try {
    const res = await fetch(`${getApiBase()}/api/field-stories/urs-field-story`, {
      cache: "no-store",
    });
    if (res.ok) return await res.json();
  } catch {
    // The route still renders during local web-only work.
  }
  return localFallback();
}

export default async function UrsFieldStoryPage() {
  const story = await loadStory();
  const sections = splitStory(story.story_markdown);
  const artifactsByKind = story.artifacts.reduce<Record<string, FieldArtifact[]>>((acc, artifact) => {
    acc[artifact.kind] = [...(acc[artifact.kind] || []), artifact];
    return acc;
  }, {});

  return (
    <main className="min-h-screen bg-background text-foreground">
      <PageReadPing pageId="field-urs" sourcePage="/field/urs" />
      <section className="border-b border-border/60 px-4 py-12 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-5xl space-y-6">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-primary">
            Field story
          </p>
          <div className="space-y-4">
            <h1 className="max-w-4xl text-4xl font-light tracking-tight md:text-6xl">
              {story.title}
            </h1>
            <p className="max-w-3xl text-base leading-7 text-muted-foreground md:text-lg">
              {story.summary}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {story.frequency_bands.map((band) => (
              <span
                key={band}
                className="rounded-md border border-border/70 px-2.5 py-1 text-xs text-muted-foreground"
              >
                {band}
              </span>
            ))}
          </div>
          <div className="flex flex-wrap gap-3 text-sm">
            <Link className="text-primary underline-offset-4 hover:underline" href="/api/field-stories/urs-field-story">
              API
            </Link>
            <Link className="text-primary underline-offset-4 hover:underline" href="/api/field-stories/urs-field-story/spectrum">
              Spectrum
            </Link>
            <Link className="text-primary underline-offset-4 hover:underline" href="/people/urs">
              Profile
            </Link>
          </div>
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-8 px-4 py-10 sm:px-6 lg:grid-cols-[minmax(0,1fr)_280px] lg:px-8">
        <article className="space-y-10">
          {sections.map((section) => (
            <section key={section.title} className="border-b border-border/50 pb-8 last:border-b-0">
              <h2 className="mb-4 text-2xl font-light tracking-tight">{section.title}</h2>
              <div className="space-y-4 text-sm leading-7 text-muted-foreground md:text-base">
                <MarkdownProse text={section.body} />
              </div>
            </section>
          ))}
        </article>

        <aside className="space-y-6 lg:sticky lg:top-24 lg:self-start">
          <section className="space-y-3 border border-border/70 p-4">
            <h2 className="text-sm font-medium">Agent surfaces</h2>
            <div className="space-y-2 text-xs text-muted-foreground">
              <p><span className="text-foreground">Read:</span> {story.agent_use.read_api}</p>
              <p><span className="text-foreground">Contribute:</span> {story.agent_use.contribute_api}</p>
              <p><span className="text-foreground">CLI:</span> {story.agent_use.cli}</p>
            </div>
          </section>
          <section className="space-y-4 border border-border/70 p-4">
            <h2 className="text-sm font-medium">Artifacts</h2>
            {Object.entries(artifactsByKind).map(([kind, artifacts]) => (
              <div key={kind} className="space-y-2">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  {kind}
                </p>
                <ul className="space-y-1 text-xs">
                  {artifacts.map((artifact) => (
                    <li key={artifact.artifact_id}>
                      <Link
                        className="text-primary underline-offset-4 hover:underline"
                        href={`/api/field-stories/urs-field-story/artifacts/${artifact.artifact_id}`}
                      >
                        {artifact.artifact_id}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </section>
        </aside>
      </section>
    </main>
  );
}
