import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { cookies, headers } from "next/headers";

import { getApiBase } from "@/lib/api";
import { DEFAULT_LOCALE, isSupportedLocale, type LocaleCode } from "@/lib/locales";
import { createTranslator } from "@/lib/i18n";
import { MeetingSurface } from "@/components/MeetingSurface";
import { ProposalLift } from "@/components/ProposalLift";
import { ProposalOrigin } from "@/components/ProposalOrigin";

/**
 * /meet/[entityType]/[entityId] — full-screen meeting with a single entity.
 *
 * The premise: a screen is not consumption; it is a meeting. Two
 * organisms (viewer and content) come into contact and the meeting can
 * grow or shrink the vitality of each. This page renders that meeting.
 *
 * Top: two small vitality pulses — yours, theirs. Both animate when
 * a reaction lands. Middle: the entity hero. Bottom: a reaction bar
 * where every gesture visibly lifts both pulses.
 */

export const dynamic = "force-dynamic";

const SUPPORTED_TYPES = new Set([
  "concept",
  "idea",
  "spec",
  "contributor",
  "community",
  "workspace",
  "asset",
  "contribution",
  "story",
  "config",
  "insight",
  "agent_task",
  "agent_run",
  "proposal",
]);

interface EntityFacet {
  title: string;
  description: string;
  imageUrl?: string | null;
}

async function fetchEntityFacet(
  entityType: string,
  entityId: string,
  lang: LocaleCode,
): Promise<EntityFacet | null> {
  const base = getApiBase();
  const qs = `?lang=${lang}`;
  try {
    switch (entityType) {
      case "concept": {
        const res = await fetch(`${base}/api/concepts/${entityId}${qs}`, {
          cache: "no-store",
        });
        if (!res.ok) return null;
        const c = await res.json();
        return {
          title: c.name || entityId,
          description: c.description || "",
          imageUrl: c.visual_path || null,
        };
      }
      case "idea": {
        const res = await fetch(`${base}/api/ideas/${entityId}${qs}`, {
          cache: "no-store",
        });
        if (!res.ok) return null;
        const i = await res.json();
        return {
          title: i.name || i.id || entityId,
          description: i.description || "",
        };
      }
      case "spec": {
        const res = await fetch(`${base}/api/spec-registry/${entityId}${qs}`, {
          cache: "no-store",
        });
        if (!res.ok) return null;
        const s = await res.json();
        return {
          title: s.title || s.name || entityId,
          description: s.description || s.summary || "",
        };
      }
      case "contributor": {
        const res = await fetch(`${base}/api/contributors/${entityId}`, {
          cache: "no-store",
        });
        if (!res.ok) return null;
        const c = await res.json();
        return {
          title: c.name || c.display_name || entityId,
          description: c.bio || c.description || "",
        };
      }
      case "asset": {
        const res = await fetch(`${base}/api/assets/${entityId}`, {
          cache: "no-store",
        });
        if (!res.ok) return { title: entityId, description: "" };
        const a = await res.json();
        return {
          title: a.title || a.name || entityId,
          description: a.description || a.caption || "",
          imageUrl: a.image_url || a.url || null,
        };
      }
      case "contribution": {
        const res = await fetch(`${base}/api/contributions/${entityId}`, {
          cache: "no-store",
        });
        if (!res.ok) return { title: entityId, description: "" };
        const c = await res.json();
        return {
          title: c.summary || c.title || entityId,
          description: c.detail || c.notes || "",
        };
      }
      case "config": {
        // Config keys meet the viewer as "the dial that shapes this corner"
        const res = await fetch(`${base}/api/config/${entityId}`, {
          cache: "no-store",
        });
        if (!res.ok) return { title: entityId, description: "A configuration key." };
        const c = await res.json();
        return {
          title: c.key || entityId,
          description: c.description || `current value: ${JSON.stringify(c.value ?? "—")}`,
        };
      }
      case "insight": {
        const res = await fetch(`${base}/api/insights/${entityId}`, {
          cache: "no-store",
        });
        if (!res.ok) return { title: entityId, description: "An insight from the running organism." };
        const i = await res.json();
        return {
          title: i.title || i.summary || entityId,
          description: i.description || i.body || "",
        };
      }
      case "agent_task":
      case "agent_run": {
        const path = entityType === "agent_task" ? "agent-tasks" : "agent-runs";
        const res = await fetch(`${base}/api/${path}/${entityId}`, {
          cache: "no-store",
        });
        if (!res.ok) return { title: entityId, description: "" };
        const a = await res.json();
        return {
          title: a.title || a.name || a.idea_id || entityId,
          description: a.description || a.status || a.phase || "",
        };
      }
      case "proposal": {
        const res = await fetch(`${base}/api/proposals/${entityId}`, {
          cache: "no-store",
        });
        if (!res.ok) return null;
        const p = await res.json();
        const tally = p.tally
          ? ` — ${p.tally.status} · ${p.tally.counts.support + p.tally.counts.amplify} for, ${p.tally.counts.decline} against`
          : "";
        const lifted = p.resolved_as_idea_id
          ? `\n\n🌱 lifted into idea: ${p.resolved_as_idea_id}`
          : "";
        return {
          title: p.title || entityId,
          description: `${p.body || ""}${tally}${lifted}`.trim(),
        };
      }
      default:
        return { title: entityId, description: "" };
    }
  } catch {
    return null;
  }
}


// Human-readable label per entity type for page titles + OG previews.
const TYPE_LABEL: Record<string, string> = {
  concept: "Concept",
  idea: "Idea",
  spec: "Spec",
  contributor: "Contributor",
  community: "Community",
  workspace: "Workspace",
  asset: "Asset",
  contribution: "Contribution",
  story: "Story",
  config: "Config",
  insight: "Insight",
  agent_task: "Agent task",
  agent_run: "Agent run",
  proposal: "Proposal",
};


export async function generateMetadata({
  params,
}: {
  params: Promise<{ entityType: string; entityId: string }>;
}): Promise<Metadata> {
  const { entityType, entityId } = await params;
  if (!SUPPORTED_TYPES.has(entityType)) {
    return { title: "Meeting | Coherence Network" };
  }
  const cookieLocale = (await cookies()).get("NEXT_LOCALE")?.value;
  const headerLang = (await headers())
    .get("accept-language")
    ?.split(",")[0]
    ?.split("-")[0];
  const candidate = cookieLocale || headerLang;
  const lang: LocaleCode = isSupportedLocale(candidate) ? candidate : DEFAULT_LOCALE;

  const facet = await fetchEntityFacet(entityType, entityId, lang);
  if (!facet) {
    return { title: `${TYPE_LABEL[entityType] || entityType} | Coherence Network` };
  }

  const typeLabel = TYPE_LABEL[entityType] || entityType;
  const title = `${facet.title} — ${typeLabel}`;
  const description = (facet.description || "").slice(0, 280);
  const image = facet.imageUrl || undefined;

  return {
    title,
    description,
    openGraph: {
      type: "website",
      siteName: "Coherence Network",
      title,
      description,
      ...(image ? { images: [{ url: image, width: 1200, height: 630 }] } : {}),
    },
    twitter: {
      card: image ? "summary_large_image" : "summary",
      title,
      description,
      ...(image ? { images: [image] } : {}),
    },
  };
}


export default async function MeetingPage({
  params,
}: {
  params: Promise<{ entityType: string; entityId: string }>;
}) {
  const { entityType, entityId } = await params;
  if (!SUPPORTED_TYPES.has(entityType)) notFound();

  const cookieLocale = (await cookies()).get("NEXT_LOCALE")?.value;
  const headerLang = (await headers()).get("accept-language")?.split(",")[0]?.split("-")[0];
  const candidate = cookieLocale || headerLang;
  const lang: LocaleCode = isSupportedLocale(candidate) ? candidate : DEFAULT_LOCALE;
  const t = createTranslator(lang);

  const facet = await fetchEntityFacet(entityType, entityId, lang);
  if (!facet) notFound();

  return (
    <>
      <MeetingSurface
        entityType={entityType}
        entityId={entityId}
        title={facet.title}
        description={facet.description}
        imageUrl={facet.imageUrl || null}
        strings={{
          viewerPulse: t("meeting.viewerPulse"),
          contentPulse: t("meeting.contentPulse"),
          firstMeeting: t("meeting.firstMeeting"),
          familiar: t("meeting.familiar"),
          resonant: t("meeting.resonant"),
          quiet: t("meeting.quiet"),
          offer: t("meeting.offer"),
          dismiss: t("meeting.dismiss"),
          amplify: t("meeting.amplify"),
          inviteHint: t("meeting.inviteHint"),
          othersHereOne: t("meeting.othersHereOne"),
          othersHereMany: t("meeting.othersHereMany"),
          sayHeading: t("meeting.sayHeading"),
          sayNamePlaceholder: t("meeting.sayNamePlaceholder"),
          sayPlaceholder: t("meeting.sayPlaceholder"),
          saySubmit: t("meeting.saySubmit"),
          saySending: t("meeting.saySending"),
          saySent: t("meeting.saySent"),
          sayDismiss: t("meeting.sayDismiss"),
        }}
      />
      {entityType === "proposal" && (
        <div className="fixed bottom-28 left-0 right-0 px-4 z-20">
          <div className="max-w-md mx-auto">
            <ProposalLift proposalId={entityId} />
          </div>
        </div>
      )}
      {entityType === "idea" && (
        <div className="fixed bottom-28 left-0 right-0 px-4 z-20">
          <div className="max-w-md mx-auto">
            <ProposalOrigin ideaId={entityId} />
          </div>
        </div>
      )}
    </>
  );
}
