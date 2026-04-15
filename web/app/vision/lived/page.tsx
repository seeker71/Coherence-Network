import type { Metadata } from "next";
import Link from "next/link";
import { getApiBase } from "@/lib/api";
import { ConceptSectionCard, StoryCard } from "@/components/vision";

export const metadata: Metadata = {
  title: "The Lived Experience — The Living Collective",
  description: "Walk through it. Smell the bread. Hear the music. Feel the field. Stories and scenes from daily life in a community of 50-200 cells.",
};

export const dynamic = "force-dynamic";

type Scene = { id: string; name: string; description: string; visual_path?: string };
type Story = { id: string; name: string; description?: string; body?: string; note?: string };

export default async function LivedPage() {
  const base = getApiBase();

  const [scenesRes, storiesRes] = await Promise.all([
    fetch(`${base}/api/concepts/scenes?limit=50`, { next: { revalidate: 60 } }).then(r => r.json()).catch(() => ({ items: [] })),
    fetch(`${base}/api/concepts/stories?limit=50`, { next: { revalidate: 60 } }).then(r => r.json()).catch(() => ({ items: [] })),
  ]);

  const scenes: Scene[] = scenesRes.items || [];
  const stories: Story[] = storiesRes.items || [];

  return (
    <main>
      {/* Hero */}
      <section className="relative flex flex-col items-center justify-center min-h-[70vh] px-6 text-center">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_rgba(234,179,8,0.06)_0%,_transparent_60%)]" />
        <div className="relative z-10 max-w-3xl space-y-6">
          <p className="text-amber-400/60 text-sm sensing-[0.3em] uppercase">Walk through it</p>
          <h1 className="text-5xl md:text-7xl font-extralight tracking-tight leading-[1.1]">
            The Lived{" "}
            <span className="bg-gradient-to-r from-amber-300 via-teal-300 to-violet-300 bg-clip-text text-transparent">
              Experience
            </span>
          </h1>
          <p className="text-xl text-stone-400 font-light max-w-2xl mx-auto">
            50 to 200 cells. Travelers flowing through. A network of communities
            sharing resources, music, stories, vitality. This is what it feels like.
          </p>
        </div>
      </section>

      {/* Scenes — from graph DB */}
      {scenes.map((scene, i) => (
        scene.visual_path ? (
          <ConceptSectionCard
            key={scene.id}
            title={scene.name}
            body={scene.description}
            imageSrc={scene.visual_path}
            priority={i < 3}
          />
        ) : null
      ))}

      {/* Stories — from graph DB */}
      <section className="max-w-4xl mx-auto px-6 py-24 space-y-16">
        <div className="text-center space-y-4">
          <h2 className="text-3xl md:text-4xl font-extralight text-stone-300">Stories of Living</h2>
          <p className="text-stone-500 text-lg max-w-2xl mx-auto">
            Specific people. Specific days. Where do YOU fit?
          </p>
        </div>

        <div className="space-y-8">
          {stories.map((story) => (
            <StoryCard
              key={story.id}
              title={story.name}
              body={story.body || story.description || ""}
              note={story.note}
            />
          ))}
        </div>
      </section>

      {/* The field you can feel */}
      <section className="max-w-3xl mx-auto px-6 py-24 text-center space-y-8">
        <h2 className="text-2xl font-extralight text-stone-400">The field you can feel</h2>
        <p className="text-stone-400 leading-relaxed">
          When 50-200 people live in genuine resonance — sharing meals, sharing space,
          sharing silence, sharing breath, sharing creative expression, sharing physical
          touch, sharing fire — the collective field becomes palpable. You can feel it
          when you enter. Visitors describe it as warmth, as coming home, as the air
          being thicker, as being held.
        </p>
        <p className="text-stone-500 leading-relaxed italic">
          When the field is strong, fear dissolves — not through courage but through
          irrelevance. What is there to fear when you're held?
        </p>
      </section>

      {/* CTA */}
      <section className="border-t border-stone-800/20">
        <div className="max-w-3xl mx-auto px-6 py-20 text-center space-y-8">
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link href="/vision" className="px-8 py-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300/90 hover:bg-amber-500/20 transition-all font-medium">
              The concepts
            </Link>
            <Link href="/vision/realize" className="px-8 py-3 rounded-xl bg-teal-500/10 border border-teal-500/20 text-teal-300/90 hover:bg-teal-500/20 transition-all font-medium">
              How it becomes real
            </Link>
            <Link href="/vision/join" className="px-8 py-3 rounded-xl bg-violet-500/10 border border-violet-500/20 text-violet-300/90 hover:bg-violet-500/20 transition-all font-medium">
              Join the vision
            </Link>
          </div>
          <p className="text-stone-700 text-xs italic">
            Every story is a cell in the field sensing itself.
            If you can feel it, you're already part of it.
          </p>
        </div>
      </section>
    </main>
  );
}
