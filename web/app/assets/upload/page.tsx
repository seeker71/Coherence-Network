// Upload an asset — wires the POST /api/assets/register endpoint into a
// user-facing form. UploadForm handles file pick + type + description +
// SHA-256 hash computation; ConceptTagger fetches living-collective
// concepts and lets the user weight each tag from 0.0–1.0. The two
// compose into the AssetRegistrationCreate payload (R2 in
// specs/story-protocol-integration.md). The created asset's id surfaces
// as a link to the detail page so the contributor can immediately walk
// through the asset's IP status, storage links, and evidence surface.
"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { getApiBase } from "@/lib/api";

type Concept = {
  id: string;
  name?: string;
  title?: string;
};

type ConceptWeight = {
  concept_id: string;
  weight: number;
};

const ASSET_TYPES = [
  "BLUEPRINT",
  "IMAGE",
  "MODEL_3D",
  "VIDEO",
  "ARTICLE",
  "RESEARCH",
  "INSTRUCTION",
] as const;

type AssetType = (typeof ASSET_TYPES)[number];

// ConceptTagger — multi-select concept widget. Fetches living-collective
// concepts on mount, lets the user pick any subset and assign each a
// 0.0–1.0 weight via a slider. Produces the concept_tags array required
// by AssetRegistrationCreate.concept_tags.
function ConceptTagger({
  selected,
  onChange,
}: {
  selected: ConceptWeight[];
  onChange: (next: ConceptWeight[]) => void;
}) {
  const [concepts, setConcepts] = useState<Concept[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const res = await fetch(
          `${getApiBase()}/api/concepts/domain/living-collective`,
          { cache: "no-store" },
        );
        if (!res.ok) {
          if (!cancelled) {
            setError(`HTTP ${res.status}`);
            setLoading(false);
          }
          return;
        }
        const data = await res.json();
        const list: Concept[] = Array.isArray(data) ? data : data?.items ?? [];
        if (!cancelled) {
          setConcepts(list);
          setLoading(false);
        }
      } catch (err: any) {
        if (!cancelled) {
          setError(err?.message ?? "unknown error");
          setLoading(false);
        }
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedMap = useMemo(() => {
    const m = new Map<string, number>();
    for (const t of selected) m.set(t.concept_id, t.weight);
    return m;
  }, [selected]);

  const filtered = useMemo(() => {
    const f = filter.trim().toLowerCase();
    if (!f) return concepts.slice(0, 60);
    return concepts.filter((c) => {
      const label = (c.title || c.name || c.id || "").toLowerCase();
      return label.includes(f) || c.id?.toLowerCase().includes(f);
    }).slice(0, 60);
  }, [concepts, filter]);

  const toggle = (conceptId: string) => {
    if (selectedMap.has(conceptId)) {
      onChange(selected.filter((t) => t.concept_id !== conceptId));
    } else {
      onChange([...selected, { concept_id: conceptId, weight: 0.5 }]);
    }
  };

  const updateWeight = (conceptId: string, weight: number) => {
    onChange(
      selected.map((t) =>
        t.concept_id === conceptId ? { ...t, weight } : t,
      ),
    );
  };

  return (
    <div className="space-y-3">
      <div className="flex items-baseline justify-between gap-2">
        <label className="text-sm text-stone-300">Concept tags</label>
        <span className="text-xs text-stone-500">
          {selected.length} selected
        </span>
      </div>

      {selected.length > 0 && (
        <div className="space-y-2 rounded-xl border border-amber-500/20 bg-amber-500/5 p-3">
          {selected.map((tag) => (
            <div key={tag.concept_id} className="flex flex-wrap items-center gap-2 sm:gap-3">
              <span className="text-xs font-mono text-amber-200 flex-1 min-w-0 truncate">
                {tag.concept_id}
              </span>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={tag.weight}
                onChange={(e) => updateWeight(tag.concept_id, Number(e.target.value))}
                className="flex-1 min-w-[120px] accent-amber-400"
                aria-label={`Weight for ${tag.concept_id}`}
              />
              <span className="text-xs text-stone-300 w-10 text-right tabular-nums">
                {tag.weight.toFixed(2)}
              </span>
              <button
                type="button"
                onClick={() => toggle(tag.concept_id)}
                className="text-xs text-stone-400 hover:text-rose-300"
                aria-label={`Remove ${tag.concept_id}`}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}

      <input
        type="search"
        placeholder="Search concepts…"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        className="w-full rounded-md border border-stone-700 bg-stone-900/60 px-3 py-2 text-sm text-stone-200 placeholder-stone-500 focus:border-amber-400/60 focus:outline-none"
      />

      <div className="max-h-64 overflow-y-auto rounded-md border border-stone-800 bg-stone-950/60 p-2">
        {loading ? (
          <p className="text-xs text-stone-500 px-2 py-3">Loading concepts…</p>
        ) : error ? (
          <p className="text-xs text-rose-400 px-2 py-3">Concepts unavailable: {error}</p>
        ) : filtered.length === 0 ? (
          <p className="text-xs text-stone-500 px-2 py-3">No concepts match.</p>
        ) : (
          <ul className="grid gap-1">
            {filtered.map((c) => {
              const picked = selectedMap.has(c.id);
              const label = c.title || c.name || c.id;
              return (
                <li key={c.id}>
                  <button
                    type="button"
                    onClick={() => toggle(c.id)}
                    className={`w-full text-left rounded px-2 py-1.5 text-xs transition-colors ${
                      picked
                        ? "bg-amber-500/15 text-amber-100"
                        : "text-stone-300 hover:bg-stone-800/60"
                    }`}
                  >
                    <span className="font-mono text-stone-500 mr-2">
                      {picked ? "✓" : "·"}
                    </span>
                    {label}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}

async function sha256Hex(buffer: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", buffer);
  const bytes = new Uint8Array(digest);
  return Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

// UploadForm — file picker + asset_type select + description textarea +
// concept tags. On submit, POSTs to /api/assets/register with the full
// AssetRegistrationCreate payload. The contributor sees the resulting
// asset id as a link to the detail page on success, or inline error
// messages on failure.
function UploadForm() {
  const [file, setFile] = useState<File | null>(null);
  const [assetType, setAssetType] = useState<AssetType>("BLUEPRINT");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [creatorId, setCreatorId] = useState("");
  const [conceptTags, setConceptTags] = useState<ConceptWeight[]>([]);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ id: string } | null>(null);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setResult(null);

    if (!file) {
      setError("Pick a file first.");
      return;
    }
    if (!name.trim()) {
      setError("Name is required.");
      return;
    }
    if (!creatorId.trim()) {
      setError("Creator id is required.");
      return;
    }

    setSubmitting(true);
    try {
      const buffer = await file.arrayBuffer();
      const contentHash = await sha256Hex(buffer);

      const payload = {
        type: file.type || assetType,
        name: name.trim(),
        description: description.trim(),
        content_hash: contentHash,
        concept_tags: conceptTags,
        creator_id: creatorId.trim(),
        creation_cost_cc: "0",
        metadata: {
          asset_type: assetType,
          original_filename: file.name,
          size_bytes: file.size,
        },
      };

      const res = await fetch(`${getApiBase()}/api/assets/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`HTTP ${res.status}: ${text.slice(0, 200)}`);
      }
      const data = await res.json();
      setResult({ id: data.id });
    } catch (err: any) {
      setError(err?.message ?? "submission failed");
    } finally {
      setSubmitting(false);
    }
  };

  if (result) {
    const detailHref = `/assets/${encodeURIComponent(
      result.id.replace(/^asset:/, ""),
    )}`;
    return (
      <div className="rounded-xl border border-emerald-400/30 bg-emerald-500/5 p-6 space-y-3">
        <h2 className="text-lg font-light text-emerald-200">Asset registered</h2>
        <p className="text-sm text-stone-300">
          Your asset is on the graph. The IP-registration worker will pick it up
          and update its <code className="text-amber-200">ip_status</code> when
          the on-chain mint settles.
        </p>
        <p className="text-xs font-mono text-stone-400 break-all">{result.id}</p>
        <div className="flex flex-wrap gap-3 pt-2">
          <Link
            href={detailHref}
            className="rounded border border-amber-400/40 bg-amber-500/10 px-4 py-2 text-sm text-amber-100 hover:bg-amber-500/20 transition-colors"
          >
            Open asset →
          </Link>
          <button
            type="button"
            onClick={() => {
              setResult(null);
              setFile(null);
              setName("");
              setDescription("");
              setConceptTags([]);
            }}
            className="rounded border border-stone-700 px-4 py-2 text-sm text-stone-200 hover:border-amber-400/40 transition-colors"
          >
            Upload another
          </button>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="space-y-5">
      <div className="space-y-2">
        <label className="text-sm text-stone-300" htmlFor="file">
          File
        </label>
        <input
          id="file"
          type="file"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="block w-full text-sm text-stone-300 file:mr-3 file:rounded file:border-0 file:bg-amber-500/10 file:px-3 file:py-1.5 file:text-amber-200 file:hover:bg-amber-500/20"
        />
        {file && (
          <p className="text-xs text-stone-500">
            {file.name} · {(file.size / 1024).toFixed(1)} KB · {file.type || "no MIME"}
          </p>
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <label className="text-sm text-stone-300" htmlFor="asset_type">
            Asset type
          </label>
          <select
            id="asset_type"
            value={assetType}
            onChange={(e) => setAssetType(e.target.value as AssetType)}
            className="w-full rounded-md border border-stone-700 bg-stone-900/60 px-3 py-2 text-sm text-stone-200 focus:border-amber-400/60 focus:outline-none"
          >
            {ASSET_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-2">
          <label className="text-sm text-stone-300" htmlFor="creator_id">
            Creator id
          </label>
          <input
            id="creator_id"
            type="text"
            value={creatorId}
            onChange={(e) => setCreatorId(e.target.value)}
            placeholder="contributor:abc123"
            className="w-full rounded-md border border-stone-700 bg-stone-900/60 px-3 py-2 text-sm text-stone-200 placeholder-stone-500 focus:border-amber-400/60 focus:outline-none"
          />
        </div>
      </div>

      <div className="space-y-2">
        <label className="text-sm text-stone-300" htmlFor="name">
          Name
        </label>
        <input
          id="name"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Compound roof plan v3"
          className="w-full rounded-md border border-stone-700 bg-stone-900/60 px-3 py-2 text-sm text-stone-200 placeholder-stone-500 focus:border-amber-400/60 focus:outline-none"
        />
      </div>

      <div className="space-y-2">
        <label className="text-sm text-stone-300" htmlFor="description">
          Description
        </label>
        <textarea
          id="description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={4}
          placeholder="What this vessel carries and how it can be used."
          className="w-full rounded-md border border-stone-700 bg-stone-900/60 px-3 py-2 text-sm text-stone-200 placeholder-stone-500 focus:border-amber-400/60 focus:outline-none"
        />
      </div>

      <ConceptTagger selected={conceptTags} onChange={setConceptTags} />

      {error && (
        <p className="rounded border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">
          {error}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-3 pt-2">
        <button
          type="submit"
          disabled={submitting}
          className="rounded border border-amber-400/40 bg-amber-500/10 px-5 py-2 text-sm text-amber-100 hover:bg-amber-500/20 transition-colors disabled:opacity-50"
        >
          {submitting ? "Registering…" : "Register asset"}
        </button>
        <Link
          href="/assets"
          className="text-sm text-stone-400 hover:text-amber-200 transition-colors"
        >
          Cancel
        </Link>
      </div>
    </form>
  );
}

export default function AssetUploadPage() {
  return (
    <main className="bg-stone-950 min-h-screen">
      <div className="mx-auto max-w-3xl px-4 sm:px-6 py-6 sm:py-10 space-y-6">
        <nav
          className="text-sm text-stone-500 flex items-center gap-2"
          aria-label="breadcrumb"
        >
          <Link href="/" className="hover:text-amber-300 transition-colors">
            Home
          </Link>
          <span className="text-stone-700">/</span>
          <Link href="/assets" className="hover:text-amber-300 transition-colors">
            Assets
          </Link>
          <span className="text-stone-700">/</span>
          <span className="text-stone-300">Upload</span>
        </nav>

        <header className="space-y-2">
          <h1 className="text-2xl sm:text-4xl font-light text-stone-50 tracking-tight">
            Upload an asset
          </h1>
          <p className="text-sm text-stone-400 leading-relaxed">
            Register a digital vessel — blueprint, image, 3D model, video,
            article, research, or instruction — with its concept resonance.
            The registration mints a content-addressed graph node; the IP
            registration worker picks it up and surfaces its on-chain status
            on the detail page.
          </p>
        </header>

        <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 sm:p-7">
          <UploadForm />
        </section>
      </div>
    </main>
  );
}
