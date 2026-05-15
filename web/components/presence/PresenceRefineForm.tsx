"use client";

/**
 * PresenceRefineForm — the visitor's hands on the primary data.
 *
 * Three sections, each saving independently to the API so a visitor
 * who only wants to fix a typo doesn't have to confront the rest:
 *
 *   1. Identity   — name, tagline, slug, image, description
 *   2. Presences  — public URLs across platforms (presences[] array)
 *   3. Influences — graph edges, with a spectrum-colored picker for
 *                   the edge type
 *
 * Mutations write through the existing graph endpoints:
 *   PATCH  /api/graph/nodes/{id}
 *   POST   /api/edges
 *   DELETE /api/edges/{edge_id}
 *
 * No auth gate today — the whole network is wiki-shape. Edits land
 * immediately and are visible to everyone.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";
import { readIdentity } from "@/lib/identity";
import {
  EDGE_FAMILIES,
  EDGE_TYPE_TO_FAMILY,
  edgeTypeLabel,
  familyForEdgeType,
  hsl,
  type EdgeFamilySlug,
} from "@/lib/edge-spectrum";

type GraphNode = {
  id: string;
  type: string;
  name?: string;
  description?: string;
  slug?: string | null;
  tagline?: string | null;
  image_url?: string | null;
  presences?: { provider: string; url: string }[];
  presence_content?: PresenceContentEnvelope | null;
};

/* ── presence_content shape (mirrors web/lib/presence-content.tsx) ── */

type PresenceFact = { label: string; value_md: string };
type PresenceArticle = {
  kind: "narrative" | "panel";
  variant?: "warm" | "cool" | "neutral" | "empty";
  eyebrow?: string;
  heading?: string;
  body_md: string;
};
type PresenceContent = {
  hero?: {
    eyebrow?: string;
    welcome_md?: string;
  };
  facts?: PresenceFact[];
  note_from_body?: { eyebrow?: string; body_md: string } | null;
  articles?: PresenceArticle[];
  footer_md?: string;
};
type PresenceContentEnvelope = {
  en?: PresenceContent;
  [locale: string]: PresenceContent | undefined;
};

/**
 * Attribution headers for every PATCH this form makes. The audit log
 * uses these to distinguish web edits from sync-script writes from
 * raw API calls; the visitor's contributor id (when known) lands as
 * the author so revision history reads who-did-what.
 */
function attributedHeaders(): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Edit-Source": "web",
  };
  try {
    const { contributorId, name } = readIdentity();
    if (contributorId) headers["X-Edit-Author"] = contributorId;
    else if (name) headers["X-Edit-Author"] = name;
  } catch {
    // identity unavailable — anonymous edit, audit log records empty author
  }
  return headers;
}

type Edge = {
  id: string;
  from_id: string;
  to_id: string;
  type: string;
  from_node?: { id: string; name: string; type: string; slug?: string | null };
  to_node?: { id: string; name: string; type: string; slug?: string | null };
};

const ALL_EDGE_TYPES: { type: string; family: EdgeFamilySlug }[] = Object.entries(
  EDGE_TYPE_TO_FAMILY,
)
  .map(([type, family]) => ({ type, family: family as EdgeFamilySlug }))
  .sort((a, b) => a.type.localeCompare(b.type));

export function PresenceRefineForm({ node }: { node: GraphNode }) {
  return (
    <div className="space-y-10">
      <IdentitySection node={node} />
      <ContentSection node={node} />
      <PresencesSection node={node} />
      <InfluencesSection node={node} />
      <footer className="pt-6 border-t border-border/30">
        <Link
          href={`/people/${encodeURIComponent(node.slug || node.id)}`}
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← back to the page
        </Link>
      </footer>
    </div>
  );
}

// ── 1. Identity ─────────────────────────────────────────────────────

function IdentitySection({ node }: { node: GraphNode }) {
  const [name, setName] = useState(node.name || "");
  const [tagline, setTagline] = useState(node.tagline || "");
  const [slug, setSlug] = useState(node.slug || "");
  const [imageUrl, setImageUrl] = useState(node.image_url || "");
  const [description, setDescription] = useState(node.description || "");
  const [status, setStatus] = useState<SaveStatus>("idle");

  async function save() {
    setStatus("saving");
    const res = await fetch(
      `${getApiBase()}/api/graph/nodes/${encodeURIComponent(node.id)}`,
      {
        method: "PATCH",
        headers: attributedHeaders(),
        body: JSON.stringify({
          name,
          description,
          properties: {
            tagline: tagline || null,
            slug: slug || null,
            image_url: imageUrl || null,
          },
        }),
      },
    );
    setStatus(res.ok ? "saved" : "error");
    if (res.ok) setTimeout(() => setStatus("idle"), 2400);
  }

  return (
    <Section
      title="Identity"
      hint="Name, tagline, the doorway slug, the hero image, and the body of writing about this presence."
    >
      <Field label="Name">
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className={inputClass}
        />
      </Field>
      <Field label="Tagline" hint="One short sentence in their voice. ≤200 chars.">
        <input
          type="text"
          value={tagline}
          maxLength={200}
          onChange={(e) => setTagline(e.target.value)}
          className={inputClass}
        />
      </Field>
      <Field
        label="Slug"
        hint="The human-readable URL: /people/{slug}. Lowercase, hyphens."
      >
        <input
          type="text"
          value={slug}
          onChange={(e) => setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-"))}
          className={inputClass}
        />
      </Field>
      <Field label="Hero image URL" hint="A current, present-day image. HTTPS.">
        <input
          type="url"
          value={imageUrl}
          onChange={(e) => setImageUrl(e.target.value)}
          className={inputClass}
        />
        {imageUrl && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={imageUrl}
            alt=""
            className="mt-2 w-24 h-24 rounded-lg object-cover border border-border/40"
          />
        )}
      </Field>
      <Field
        label="Description"
        hint="Long-form body. Multiple paragraphs welcome. Their voice when possible; never invent words they didn't say."
      >
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={10}
          className={`${inputClass} font-mono text-xs leading-relaxed`}
        />
      </Field>
      <SaveBar status={status} onSave={save} label="Save identity" />
    </Section>
  );
}

// ── 1b. Page content (presence_content) ─────────────────────────────

/**
 * The structured `presence_content` is what `PersonProfileTemplate`
 * renders into the page chrome (hero eyebrow + welcome, facts grid,
 * note-from-body, articles, footer). Until this section existed, the
 * fields lived only in `docs/presence-content/{slug}.json` or on the
 * graph — outside contributors had to PATCH the API by hand to refine
 * them. This is the web-side form that closes that gap.
 *
 * Only renders when the node already carries presence_content. The
 * page chrome (hero background gradient, overlay class, extra_image)
 * is left out of the editor on purpose — those are styling chrome,
 * not the visitor's own voice; the renderer's defaults carry them.
 */
function ContentSection({ node }: { node: GraphNode }) {
  const envelope = (node.presence_content as PresenceContentEnvelope | undefined) || {};
  const initial: PresenceContent = envelope.en || envelope[Object.keys(envelope)[0] || ""] || {};
  const [eyebrow, setEyebrow] = useState(initial.hero?.eyebrow || "");
  const [welcomeMd, setWelcomeMd] = useState(initial.hero?.welcome_md || "");
  const [facts, setFacts] = useState<PresenceFact[]>(initial.facts || []);
  const [noteEyebrow, setNoteEyebrow] = useState(initial.note_from_body?.eyebrow || "");
  const [noteBody, setNoteBody] = useState(initial.note_from_body?.body_md || "");
  const [articles, setArticles] = useState<PresenceArticle[]>(initial.articles || []);
  const [footerMd, setFooterMd] = useState(initial.footer_md || "");
  const [status, setStatus] = useState<SaveStatus>("idle");

  // When the node arrives without presence_content yet, render nothing —
  // a blank editor isn't useful and the API surface to mint a fresh
  // envelope from scratch belongs in a different flow (sync script or
  // the original page authoring).
  if (!node.presence_content) return null;

  async function save() {
    setStatus("saving");
    const nextContent: PresenceContent = {
      hero: {
        ...(initial.hero || {}),
        eyebrow: eyebrow || undefined,
        welcome_md: welcomeMd || "",
      },
      facts: facts.filter((f) => f.label.trim() || f.value_md.trim()),
      note_from_body: noteBody.trim()
        ? { eyebrow: noteEyebrow || undefined, body_md: noteBody }
        : null,
      articles: articles.filter((a) => a.body_md.trim()),
      footer_md: footerMd || undefined,
    };
    const nextEnvelope: PresenceContentEnvelope = { ...envelope, en: nextContent };
    const res = await fetch(
      `${getApiBase()}/api/graph/nodes/${encodeURIComponent(node.id)}`,
      {
        method: "PATCH",
        headers: attributedHeaders(),
        body: JSON.stringify({
          properties: { presence_content: nextEnvelope },
        }),
      },
    );
    setStatus(res.ok ? "saved" : "error");
    if (res.ok) setTimeout(() => setStatus("idle"), 2400);
  }

  return (
    <Section
      title="Page content"
      hint="The eyebrow, welcome, facts grid, note from this body, articles, and footer that render on the public page. Use `**bold**`, `*italic*`, `[label](/path)` for internal links and `[label](https://…)` for external, `## Heading` for section breaks in article bodies."
    >
      <Field label="Hero eyebrow">
        <input
          type="text"
          value={eyebrow}
          onChange={(e) => setEyebrow(e.target.value)}
          placeholder="The teacher who held the room"
          className={inputClass}
        />
      </Field>
      <Field label="Welcome paragraph(s)" hint="Lands directly under the name in the hero. Multiple paragraphs separated by blank lines.">
        <textarea
          value={welcomeMd}
          onChange={(e) => setWelcomeMd(e.target.value)}
          rows={5}
          className={`${inputClass} font-mono text-xs leading-relaxed`}
        />
      </Field>

      <div className="space-y-2 pt-2">
        <p className="text-[11px] uppercase tracking-[0.12em] font-medium text-muted-foreground">
          Facts grid
        </p>
        <ul className="space-y-2">
          {facts.map((f, i) => (
            <li key={i} className="space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <input
                  type="text"
                  value={f.label}
                  onChange={(e) => {
                    const next = facts.slice();
                    next[i] = { ...next[i], label: e.target.value };
                    setFacts(next);
                  }}
                  placeholder="Label"
                  className={`${inputClass} max-w-[14rem]`}
                />
                <button
                  type="button"
                  onClick={() => setFacts(facts.filter((_, j) => j !== i))}
                  className="text-xs text-muted-foreground hover:text-foreground px-2 py-1.5"
                >
                  remove
                </button>
              </div>
              <textarea
                value={f.value_md}
                onChange={(e) => {
                  const next = facts.slice();
                  next[i] = { ...next[i], value_md: e.target.value };
                  setFacts(next);
                }}
                rows={2}
                placeholder="Value (markdown allowed)"
                className={`${inputClass} font-mono text-xs`}
              />
            </li>
          ))}
        </ul>
        <button
          type="button"
          onClick={() => setFacts([...facts, { label: "", value_md: "" }])}
          className="text-sm text-[hsl(var(--primary))] hover:opacity-80"
        >
          + add a fact
        </button>
      </div>

      <div className="space-y-2 pt-4 border-t border-border/30">
        <p className="text-[11px] uppercase tracking-[0.12em] font-medium text-muted-foreground">
          Note from this body
        </p>
        <Field label="Eyebrow (optional)">
          <input
            type="text"
            value={noteEyebrow}
            onChange={(e) => setNoteEyebrow(e.target.value)}
            placeholder="A note from this body"
            className={inputClass}
          />
        </Field>
        <Field label="Body" hint="Leave empty to remove the note entirely.">
          <textarea
            value={noteBody}
            onChange={(e) => setNoteBody(e.target.value)}
            rows={4}
            className={`${inputClass} font-mono text-xs leading-relaxed`}
          />
        </Field>
      </div>

      <div className="space-y-3 pt-4 border-t border-border/30">
        <p className="text-[11px] uppercase tracking-[0.12em] font-medium text-muted-foreground">
          Articles
        </p>
        <ul className="space-y-4">
          {articles.map((a, i) => (
            <li key={i} className="space-y-2 rounded-lg border border-border/40 p-3">
              <div className="flex flex-wrap items-center gap-2">
                <select
                  value={a.kind}
                  onChange={(e) => {
                    const next = articles.slice();
                    next[i] = { ...next[i], kind: e.target.value as PresenceArticle["kind"] };
                    setArticles(next);
                  }}
                  className={`${inputClass} max-w-[10rem]`}
                >
                  <option value="narrative">narrative</option>
                  <option value="panel">panel</option>
                </select>
                {a.kind === "panel" && (
                  <select
                    value={a.variant || "neutral"}
                    onChange={(e) => {
                      const next = articles.slice();
                      next[i] = {
                        ...next[i],
                        variant: e.target.value as PresenceArticle["variant"],
                      };
                      setArticles(next);
                    }}
                    className={`${inputClass} max-w-[8rem]`}
                  >
                    <option value="warm">warm</option>
                    <option value="cool">cool</option>
                    <option value="neutral">neutral</option>
                    <option value="empty">empty</option>
                  </select>
                )}
                <button
                  type="button"
                  onClick={() => setArticles(articles.filter((_, j) => j !== i))}
                  className="ml-auto text-xs text-muted-foreground hover:text-foreground px-2 py-1.5"
                >
                  remove
                </button>
              </div>
              {a.kind === "panel" && (
                <input
                  type="text"
                  value={a.eyebrow || ""}
                  onChange={(e) => {
                    const next = articles.slice();
                    next[i] = { ...next[i], eyebrow: e.target.value };
                    setArticles(next);
                  }}
                  placeholder="Eyebrow (panel only)"
                  className={inputClass}
                />
              )}
              <input
                type="text"
                value={a.heading || ""}
                onChange={(e) => {
                  const next = articles.slice();
                  next[i] = { ...next[i], heading: e.target.value };
                  setArticles(next);
                }}
                placeholder="Heading"
                className={inputClass}
              />
              <textarea
                value={a.body_md}
                onChange={(e) => {
                  const next = articles.slice();
                  next[i] = { ...next[i], body_md: e.target.value };
                  setArticles(next);
                }}
                rows={6}
                placeholder="Body (markdown). Blank lines separate paragraphs."
                className={`${inputClass} font-mono text-xs leading-relaxed`}
              />
            </li>
          ))}
        </ul>
        <button
          type="button"
          onClick={() =>
            setArticles([
              ...articles,
              { kind: "narrative", heading: "", body_md: "" },
            ])
          }
          className="text-sm text-[hsl(var(--primary))] hover:opacity-80"
        >
          + add an article
        </button>
      </div>

      <Field label="Footer" hint="The closing block under the influence web. Markdown allowed.">
        <textarea
          value={footerMd}
          onChange={(e) => setFooterMd(e.target.value)}
          rows={3}
          className={`${inputClass} font-mono text-xs leading-relaxed`}
        />
      </Field>

      <SaveBar status={status} onSave={save} label="Save page content" />
    </Section>
  );
}

// ── 2. Public presences ─────────────────────────────────────────────

function PresencesSection({ node }: { node: GraphNode }) {
  const [items, setItems] = useState<{ provider: string; url: string }[]>(
    node.presences || [],
  );
  const [status, setStatus] = useState<SaveStatus>("idle");

  async function save() {
    setStatus("saving");
    const res = await fetch(
      `${getApiBase()}/api/graph/nodes/${encodeURIComponent(node.id)}`,
      {
        method: "PATCH",
        headers: attributedHeaders(),
        body: JSON.stringify({ properties: { presences: items } }),
      },
    );
    setStatus(res.ok ? "saved" : "error");
    if (res.ok) setTimeout(() => setStatus("idle"), 2400);
  }

  return (
    <Section
      title="Beyond the network"
      hint="Public URLs the world reaches them through. The provider is auto-detected from the URL."
    >
      <ul className="space-y-2">
        {items.map((p, i) => (
          <li key={i} className="flex flex-wrap items-center gap-2">
            <input
              type="text"
              value={p.provider}
              onChange={(e) => {
                const next = items.slice();
                next[i] = { ...next[i], provider: e.target.value };
                setItems(next);
              }}
              placeholder="provider"
              className={`${inputClass} max-w-[10rem]`}
            />
            <input
              type="url"
              value={p.url}
              onChange={(e) => {
                const next = items.slice();
                next[i] = {
                  ...next[i],
                  url: e.target.value,
                  provider: next[i].provider || providerForUrl(e.target.value),
                };
                setItems(next);
              }}
              placeholder="https://…"
              className={`${inputClass} flex-1 min-w-[16rem]`}
            />
            <button
              type="button"
              onClick={() => setItems(items.filter((_, j) => j !== i))}
              className="text-xs text-muted-foreground hover:text-foreground px-2 py-1.5"
            >
              remove
            </button>
          </li>
        ))}
      </ul>
      <button
        type="button"
        onClick={() => setItems([...items, { provider: "", url: "" }])}
        className="text-sm text-[hsl(var(--primary))] hover:opacity-80"
      >
        + add a presence
      </button>
      <SaveBar status={status} onSave={save} label="Save presences" />
    </Section>
  );
}

function providerForUrl(url: string): string {
  try {
    const u = new URL(url);
    const host = u.hostname.replace(/^www\./, "").toLowerCase();
    if (host.includes("youtube.com") || host.includes("youtu.be")) return "youtube";
    if (host.includes("instagram.com")) return "instagram";
    if (host.includes("tiktok.com")) return "tiktok";
    if (host.includes("spotify.com")) return "spotify";
    if (host.includes("bandcamp.com")) return "bandcamp";
    if (host.includes("apple.com")) return "apple-music";
    if (host.includes("soundcloud.com")) return "soundcloud";
    if (host === "x.com" || host === "twitter.com") return "x";
    if (host.includes("facebook.com")) return "facebook";
    if (host.includes("substack.com")) return "substack";
    if (host.includes("patreon.com")) return "patreon";
    return host;
  } catch {
    return "";
  }
}

// ── 3. Influences (graph edges) ─────────────────────────────────────

function InfluencesSection({ node }: { node: GraphNode }) {
  const [edges, setEdges] = useState<Edge[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    (async () => {
      const r = await fetch(
        `${getApiBase()}/api/graph/nodes/${encodeURIComponent(
          node.id,
        )}/edges?direction=both`,
      );
      if (r.ok) {
        const body = await r.json();
        const items: Edge[] = Array.isArray(body) ? body : body?.items ?? [];
        setEdges(items);
      }
      setLoaded(true);
    })();
  }, [node.id]);

  async function removeEdge(edgeId: string) {
    const res = await fetch(
      `${getApiBase()}/api/edges/${encodeURIComponent(edgeId)}`,
      { method: "DELETE" },
    );
    if (res.ok) setEdges(edges.filter((e) => e.id !== edgeId));
  }

  async function addEdge(toId: string, edgeType: string) {
    const res = await fetch(`${getApiBase()}/api/edges`, {
      method: "POST",
      headers: attributedHeaders(),
      body: JSON.stringify({
        from_id: node.id,
        to_id: toId,
        type: edgeType,
      }),
    });
    if (res.ok) {
      const created = await res.json();
      setEdges([created, ...edges]);
    }
  }

  return (
    <Section
      title="Influences and connections"
      hint="Each relationship paints the spectrum of its family. Add or remove the threads that weave this presence into the field."
    >
      {!loaded ? (
        <div className="h-12 animate-pulse rounded-lg bg-muted/40" />
      ) : (
        <>
          <ul className="space-y-1">
            {edges.length === 0 && (
              <li className="text-sm text-muted-foreground italic">
                No relationships yet.
              </li>
            )}
            {edges.map((e) => {
              const isOutgoing = e.from_id === node.id;
              const other = isOutgoing ? e.to_node : e.from_node;
              const family = familyForEdgeType(e.type);
              const fg = `hsl(${family.dark.hue} ${family.dark.saturation}% ${family.dark.lightness}%)`;
              return (
                <li
                  key={e.id}
                  className="flex items-center gap-2 py-1 px-2 rounded-md hover:bg-card/40"
                >
                  <span
                    aria-hidden="true"
                    className="w-2 h-2 rounded-full shrink-0"
                    style={{ background: fg }}
                  />
                  <span
                    className="text-[10px] uppercase tracking-[0.1em] shrink-0"
                    style={{ color: fg }}
                  >
                    {isOutgoing ? "→" : "←"} {edgeTypeLabel(e.type)}
                  </span>
                  <span className="text-sm text-foreground/85 truncate flex-1">
                    {other?.name || other?.id || "—"}
                  </span>
                  <button
                    type="button"
                    onClick={() => removeEdge(e.id)}
                    className="text-xs text-muted-foreground hover:text-foreground px-2"
                  >
                    remove
                  </button>
                </li>
              );
            })}
          </ul>
          <AddEdgeForm onAdd={addEdge} />
        </>
      )}
    </Section>
  );
}

function AddEdgeForm({
  onAdd,
}: {
  onAdd: (toId: string, edgeType: string) => Promise<void> | void;
}) {
  const [toId, setToId] = useState("");
  const [edgeType, setEdgeType] = useState("inspired-by");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!toId.trim() || !edgeType) return;
    setBusy(true);
    await onAdd(toId.trim(), edgeType);
    setToId("");
    setBusy(false);
  }

  const family = familyForEdgeType(edgeType);
  const fg = `hsl(${family.dark.hue} ${family.dark.saturation}% ${family.dark.lightness}%)`;

  return (
    <form onSubmit={submit} className="mt-3 flex flex-wrap items-center gap-2">
      <select
        value={edgeType}
        onChange={(e) => setEdgeType(e.target.value)}
        className={`${inputClass} max-w-[14rem] font-medium`}
        style={{ color: fg, borderColor: `color-mix(in oklch, ${fg} 30%, transparent)` }}
      >
        {EDGE_FAMILIES.map((fam) => (
          <optgroup key={fam.slug} label={fam.name}>
            {ALL_EDGE_TYPES.filter((et) => et.family === fam.slug).map((et) => (
              <option key={et.type} value={et.type}>
                {edgeTypeLabel(et.type)}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
      <input
        type="text"
        value={toId}
        onChange={(e) => setToId(e.target.value)}
        placeholder="other presence id (e.g. contributor:aubrey-marcus)"
        className={`${inputClass} flex-1 min-w-[18rem]`}
      />
      <button
        type="submit"
        disabled={busy || !toId.trim()}
        className="rounded-full px-4 py-1.5 text-xs font-medium border disabled:opacity-50"
        style={{
          color: fg,
          borderColor: `color-mix(in oklch, ${fg} 45%, transparent)`,
          background: `color-mix(in oklch, ${fg} 10%, transparent)`,
        }}
      >
        {busy ? "…" : "add"}
      </button>
    </form>
  );
}

// ── shared bits ─────────────────────────────────────────────────────

type SaveStatus = "idle" | "saving" | "saved" | "error";

function Section({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3 rounded-2xl border border-border/40 bg-card/30 p-5">
      <header className="space-y-1">
        <h2 className="text-xs uppercase tracking-[0.18em] font-semibold text-[hsl(var(--primary))]">
          {title}
        </h2>
        {hint && <p className="text-xs text-muted-foreground/80">{hint}</p>}
      </header>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block space-y-1">
      <span className="text-[11px] uppercase tracking-[0.12em] font-medium text-muted-foreground">
        {label}
      </span>
      {hint && (
        <span className="block text-[11px] text-muted-foreground/70 italic">
          {hint}
        </span>
      )}
      {children}
    </label>
  );
}

function SaveBar({
  status,
  onSave,
  label,
}: {
  status: SaveStatus;
  onSave: () => void | Promise<void>;
  label: string;
}) {
  return (
    <div className="flex items-center gap-3 pt-2">
      <button
        type="button"
        onClick={onSave}
        disabled={status === "saving"}
        className="rounded-full bg-[hsl(var(--primary))] px-5 py-1.5 text-xs font-medium text-[hsl(var(--primary-foreground))] hover:opacity-90 disabled:opacity-50"
      >
        {status === "saving" ? "saving…" : label}
      </button>
      {status === "saved" && (
        <span className="text-xs text-[hsl(var(--chart-2))]">✓ saved</span>
      )}
      {status === "error" && (
        <span className="text-xs text-rose-400">couldn&apos;t save — try again</span>
      )}
    </div>
  );
}

const inputClass =
  "w-full rounded-md border border-border/60 bg-background/60 px-3 py-1.5 text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-2 focus:ring-[hsl(var(--primary)/0.4)] focus:border-[hsl(var(--primary)/0.5)]";
