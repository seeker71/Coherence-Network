"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { getApiBase } from "@/lib/api";

const ASSET_TYPES = [
  {
    value: "BLUEPRINT",
    label: "Blueprint",
    description: "Physical or digital design file (3D model, CAD, plans)",
  },
  {
    value: "DESIGN",
    label: "Design",
    description: "Architectural or spatial design",
  },
  {
    value: "RESEARCH",
    label: "Research",
    description: "Documentation, data, or analysis",
  },
] as const;

export default function CreatorSubmitPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [assetType, setAssetType] = useState("BLUEPRINT");
  const [description, setDescription] = useState("");
  const [communityTags, setCommunityTags] = useState("");
  const [fileUrl, setFileUrl] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const tags = communityTags
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean)
        .slice(0, 10);
      const body = {
        type: assetType,
        description: `${name}\n\n${description}\n\nSource: ${fileUrl}`,
        metadata: {
          name,
          community_tags: tags,
          source_url: fileUrl,
        },
      };
      const response = await fetch(`${getApiBase()}/api/assets`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!response.ok) {
        const text = await response.text();
        setError(`HTTP ${response.status}: ${text}`);
        return;
      }
      const data = await response.json();
      const id = data.id || data.asset_id;
      if (id) {
        router.push(`/assets/${id}/proof`);
      } else {
        setError("Submission succeeded but no asset id was returned.");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="max-w-2xl mx-auto px-6 py-12">
      <nav
        className="text-sm text-stone-500 mb-8 flex items-center gap-2"
        aria-label="breadcrumb"
      >
        <Link href="/" className="hover:text-amber-400/80 transition-colors">
          Home
        </Link>
        <span className="text-stone-700">/</span>
        <Link
          href="/creators"
          className="hover:text-amber-400/80 transition-colors"
        >
          Creators
        </Link>
        <span className="text-stone-700">/</span>
        <span className="text-stone-300">Submit</span>
      </nav>

      <h1 className="text-3xl font-extralight text-white mb-6">
        Submit your work
      </h1>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label className="block text-sm text-stone-300 mb-2">
            Name <span className="text-rose-400">*</span>
          </label>
          <input
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded border border-stone-800 bg-stone-950 px-3 py-2 text-white focus:border-amber-500/40 focus:outline-none"
            placeholder="WikiHouse Roof Panel v2"
          />
        </div>

        <div>
          <label className="block text-sm text-stone-300 mb-2">
            Type <span className="text-rose-400">*</span>
          </label>
          <div className="space-y-2">
            {ASSET_TYPES.map((t) => (
              <label
                key={t.value}
                className={`flex items-start gap-3 rounded border p-3 cursor-pointer transition-colors ${
                  assetType === t.value
                    ? "border-amber-500/40 bg-amber-500/5"
                    : "border-stone-800 bg-stone-950/40 hover:border-stone-700"
                }`}
              >
                <input
                  type="radio"
                  name="asset_type"
                  value={t.value}
                  checked={assetType === t.value}
                  onChange={(e) => setAssetType(e.target.value)}
                  className="mt-1"
                />
                <div>
                  <div className="text-white">{t.label}</div>
                  <div className="text-xs text-stone-500 mt-0.5">
                    {t.description}
                  </div>
                </div>
              </label>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm text-stone-300 mb-2">
            Description <span className="text-rose-400">*</span>
          </label>
          <textarea
            required
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={4}
            className="w-full rounded border border-stone-800 bg-stone-950 px-3 py-2 text-white focus:border-amber-500/40 focus:outline-none"
            placeholder="What does it do, what context does it live in, what's provenance?"
          />
        </div>

        <div>
          <label className="block text-sm text-stone-300 mb-2">
            Community tags{" "}
            <span className="text-xs text-stone-500">
              (comma-separated, optional, max 10)
            </span>
          </label>
          <input
            value={communityTags}
            onChange={(e) => setCommunityTags(e.target.value)}
            className="w-full rounded border border-stone-800 bg-stone-950 px-3 py-2 text-white focus:border-amber-500/40 focus:outline-none"
            placeholder="permaculture, natural-building, wikihouse"
          />
        </div>

        <div>
          <label className="block text-sm text-stone-300 mb-2">
            File URL or GitHub URL <span className="text-rose-400">*</span>
          </label>
          <input
            required
            type="url"
            value={fileUrl}
            onChange={(e) => setFileUrl(e.target.value)}
            className="w-full rounded border border-stone-800 bg-stone-950 px-3 py-2 text-white focus:border-amber-500/40 focus:outline-none"
            placeholder="https://github.com/example/repo or https://arweave.net/tx"
          />
        </div>

        {error && (
          <div className="rounded border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-200">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="inline-block rounded border border-amber-500/40 bg-amber-500/10 px-6 py-3 text-amber-200 hover:bg-amber-500/20 disabled:opacity-50 transition-colors"
        >
          {submitting ? "Submitting…" : "Submit"}
        </button>
      </form>
    </main>
  );
}
