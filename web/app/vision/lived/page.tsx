import type { Metadata } from "next";
import Link from "next/link";
import { getApiBase } from "@/lib/api";
import { ConceptSectionCard, GalleryGrid, StoryCard } from "@/components/vision";

export const metadata: Metadata = {
  title: "The Lived Experience — The Living Collective",
  description:
    "Walk through it. See how arrivals, meals, making, and gatherings let a field become tangible in the body.",
};

export const dynamic = "force-dynamic";

type Scene = { id: string; name: string; description: string; visual_path?: string };
type Story = { id: string; name: string; description?: string; body?: string; note?: string };

const STORY_BEATS = [
  {
    title: "Arrival",
    body:
      "A person enters with all the speed of the outside world still in their body. A host makes tea, a meal is already somewhere in the building, music is coming from another room, and the first shift happens before any explanation does.",
    note:
      "A field often becomes legible through atmosphere before it becomes legible through language.",
    imageSrc: "/visuals/life-nomad-arrival.png",
  },
  {
    title: "The Table",
    body:
      "A shared meal does more than feed people. It synchronizes pace, widens trust, reveals tone, lets stories move, and gives bodies enough safety to become more honest about what they carry.",
    note:
      "Nourishment is one of the fastest ways a future community becomes physically believable.",
    imageSrc: "/visuals/life-shared-meal.png",
  },
  {
    title: "Overflow",
    body:
      "Once a field is warm enough, creativity stops feeling like performance and starts behaving like weather. Music appears, tools come out, ideas move into sketches, and people find themselves joining in before deciding they should.",
    note:
      "Vitality spreads through participation, not spectatorship.",
    imageSrc: "/visuals/joy-collective-build.png",
  },
];

const EXPERIENCE_GALLERY = [
  { imageSrc: "/visuals/life-morning-circle.png", label: "Morning circle", href: "/vision/community" },
  { imageSrc: "/visuals/practice-storytelling-elder.png", label: "Elder storytelling", href: "/vision/aligned" },
  { imageSrc: "/visuals/life-contact-improv.png", label: "Movement and trust", href: "/vision/lc-play" },
  { imageSrc: "/visuals/practice-fermentation.png", label: "Kitchen alchemy", href: "/vision/lc-v-food-practice" },
  { imageSrc: "/visuals/joy-harvest-feast.png", label: "Harvest feast", href: "/vision/lc-nourishment" },
  { imageSrc: "/visuals/network-traveling-musicians.png", label: "Traveling musicians", href: "/vision/lc-network" },
];

const FALLBACK_STORIES: Story[] = [
  {
    id: "story-presence-before-role",
    name: "Presence before role",
    body:
      "Someone arrives who is used to introducing themselves through title, output, or urgency. In a slower field they are met through eye contact, food, temperature, and attention first. Their role appears later, but it no longer has to carry their entire identity.",
    note: "The body often relaxes before the mind can explain why.",
  },
  {
    id: "story-skill-becomes-visible",
    name: "Skill becomes visible in the room",
    body:
      "A person who does not think of themselves as a leader starts setting a table, softening a tense exchange, and drawing shy people into conversation. The field recognizes a form of leadership that would stay invisible on a resume.",
    note: "Real contribution becomes easier to sense in shared activity than in self-description.",
  },
  {
    id: "story-host-space-comes-alive",
    name: "A host space comes alive",
    body:
      "A borrowed hall that felt generic all week becomes unmistakably itself once candles, sound, food, bodies, and direct conversation enter together. For a few hours, a container proves what it could hold more often.",
    note: "Experience often opens the door that planning alone cannot.",
  },
];

export default async function LivedPage() {
  const base = getApiBase();

  const [scenesRes, storiesRes] = await Promise.all([
    fetch(`${base}/api/concepts/scenes?limit=50`, { next: { revalidate: 60 } })
      .then((r) => r.json())
      .catch(() => ({ items: [] })),
    fetch(`${base}/api/concepts/stories?limit=50`, { next: { revalidate: 60 } })
      .then((r) => r.json())
      .catch(() => ({ items: [] })),
  ]);

  const scenes: Scene[] = scenesRes.items || [];
  const stories: Story[] = storiesRes.items || [];
  const activeStories = stories.length > 0 ? stories : FALLBACK_STORIES;

  return (
    <main>
      <section className="relative flex min-h-[70vh] flex-col items-center justify-center px-6 text-center">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_rgba(45,212,191,0.08)_0%,_transparent_60%),radial-gradient(circle_at_bottom_left,_rgba(251,191,36,0.08),_transparent_28%)]" />
        <div className="relative z-10 max-w-4xl space-y-6">
          <p className="text-sm uppercase tracking-[0.3em] text-amber-400/60">Walk through it</p>
          <h1 className="text-5xl font-extralight tracking-tight leading-[1.1] text-white md:text-7xl">
            The Lived{" "}
            <span className="bg-gradient-to-r from-amber-300 via-teal-300 to-violet-300 bg-clip-text text-transparent">
              Experience
            </span>
          </h1>
          <p className="mx-auto max-w-3xl text-xl font-light text-stone-300">
            This is what it feels like when a gathering becomes a field: arrival softens, meals
            synchronize, creativity wakes up, and an ordinary space starts behaving like a host.
          </p>
          <div className="flex flex-wrap justify-center gap-3 pt-2 text-sm">
            <Link
              href="/vision/aligned"
              className="rounded-full border border-stone-700/40 bg-stone-900/30 px-4 py-2 text-stone-300 transition-colors hover:border-amber-500/30 hover:text-amber-200"
            >
              Aligned hosts
            </Link>
            <Link
              href="/vision/community"
              className="rounded-full border border-stone-700/40 bg-stone-900/30 px-4 py-2 text-stone-300 transition-colors hover:border-teal-500/30 hover:text-teal-200"
            >
              The gathering
            </Link>
            <Link
              href="/vision/realize"
              className="rounded-full border border-stone-700/40 bg-stone-900/30 px-4 py-2 text-stone-300 transition-colors hover:border-violet-500/30 hover:text-violet-200"
            >
              Existing spaces, new meanings
            </Link>
          </div>
        </div>
      </section>

      {STORY_BEATS.map((beat, index) => (
        <ConceptSectionCard
          key={beat.title}
          title={beat.title}
          body={beat.body}
          note={beat.note}
          imageSrc={beat.imageSrc}
          priority={index === 0}
        />
      ))}

      {scenes.length > 0 && (
        <section className="max-w-5xl mx-auto px-6 py-24 space-y-10">
          <div className="space-y-3 text-center">
            <p className="text-sm uppercase tracking-[0.28em] text-stone-500">More sensed scenes</p>
            <h2 className="text-3xl font-extralight text-stone-200">Additional moments already in the graph</h2>
          </div>
          <div className="space-y-12">
            {scenes.map((scene, index) =>
              scene.visual_path ? (
                <ConceptSectionCard
                  key={scene.id}
                  title={scene.name}
                  body={scene.description}
                  imageSrc={scene.visual_path}
                  priority={index === 0}
                />
              ) : null,
            )}
          </div>
        </section>
      )}

      <section className="max-w-5xl mx-auto px-6 py-24 space-y-8">
        <div className="space-y-3 text-center">
          <p className="text-sm uppercase tracking-[0.28em] text-stone-500">Experiences that make it tangible</p>
          <h2 className="text-3xl font-extralight text-stone-200">You can feel the pattern in real moments</h2>
          <p className="mx-auto max-w-3xl text-stone-400">
            A story becomes more credible when you can smell the kitchen, hear the music, notice the
            pace change in your own body, and watch people start contributing without being assigned.
          </p>
        </div>
        <GalleryGrid items={EXPERIENCE_GALLERY} columns={3} aspectRatio="5/4" />
      </section>

      <section className="max-w-4xl mx-auto px-6 py-24 space-y-16">
        <div className="space-y-4 text-center">
          <h2 className="text-3xl font-extralight text-stone-300 md:text-4xl">Stories of living</h2>
          <p className="mx-auto max-w-2xl text-lg text-stone-500">
            Specific people. Specific rooms. Specific shifts in the field.
          </p>
        </div>

        <div className="space-y-8">
          {activeStories.map((story) => (
            <StoryCard
              key={story.id}
              title={story.name}
              body={story.body || story.description || ""}
              note={story.note}
            />
          ))}
        </div>
      </section>

      <section className="max-w-3xl mx-auto px-6 py-24 text-center space-y-8">
        <h2 className="text-2xl font-extralight text-stone-400">The field you can feel</h2>
        <p className="leading-relaxed text-stone-400">
          When people share meals, shared attention, sound, craft, movement, and direct conversation
          for long enough, the atmosphere becomes part of the experience. Visitors often describe it
          first as warmth, depth, slowness, relief, or a strange sense of being recognized.
        </p>
        <p className="italic leading-relaxed text-stone-500">
          That sensation is not decoration. It is evidence that a different social metabolism is
          becoming physically real.
        </p>
      </section>

      <section className="border-t border-stone-800/20">
        <div className="max-w-4xl mx-auto px-6 py-20 text-center space-y-8">
          <div className="flex flex-col justify-center gap-4 sm:flex-row">
            <Link
              href="/vision/aligned"
              className="rounded-xl border border-amber-500/20 bg-amber-500/10 px-8 py-3 font-medium text-amber-200 transition-colors hover:bg-amber-500/20"
            >
              Explore aligned hosts
            </Link>
            <Link
              href="/vision/community"
              className="rounded-xl border border-teal-500/20 bg-teal-500/10 px-8 py-3 font-medium text-teal-200 transition-colors hover:bg-teal-500/20"
            >
              See who is gathering
            </Link>
            <Link
              href="/vision/join"
              className="rounded-xl border border-violet-500/20 bg-violet-500/10 px-8 py-3 font-medium text-violet-200 transition-colors hover:bg-violet-500/20"
            >
              Join the field
            </Link>
          </div>
          <p className="text-xs italic text-stone-700">
            Every felt experience is one more proof that the story can land in bodies, not only in words.
          </p>
        </div>
      </section>
    </main>
  );
}
