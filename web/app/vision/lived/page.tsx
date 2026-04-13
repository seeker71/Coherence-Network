import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";

export const metadata: Metadata = {
  title: "The Lived Experience — The Living Collective",
  description: "Walk through it. Smell the bread. Hear the music. Feel the field. Stories and scenes from daily life in a community of 50-200 cells.",
};

const SCENES = [
  { image: "/visuals/life-morning-circle.png", title: "Dawn Attunement", desc: "Thirty cells at dawn. Singing bowl. Mist. Bare feet on wet grass. Each sharing one breath of what's alive in them." },
  { image: "/visuals/life-shared-meal.png", title: "The Midday Gathering", desc: "The whole field at one table. Children running between laps. Food that traveled thirty feet from soil to plate. The noise of 120 people who love being together." },
  { image: "/visuals/life-garden-planting.png", title: "Hands in Soil", desc: "Planting season. Every cell participates. Seeds carried by children. Rich dark earth. The growing field waking up." },
  { image: "/visuals/life-creation-workshop.png", title: "The Creation Arc", desc: "Side by side: woodworker, potter, weaver, smith. Tools beautiful from use. Children watching and helping. The sound of making." },
  { image: "/visuals/life-contact-improv.png", title: "Contact & Movement", desc: "Bodies in flow on soft grass. Golden hour. Lifting, rolling, sensing. Play that is also art that is also prayer." },
  { image: "/visuals/life-water-gathering.png", title: "The Water Temple", desc: "Hot springs at dusk. Steam rising. Candles on stone. Eight people soaking in warmth and conversation. Bodies cared for." },
  { image: "/visuals/life-breathwork.png", title: "Breathwork at Dawn", desc: "Twenty-five cells on a wooden platform. Eyes closed. Morning mist. Sound bowls humming. Something opening that words can't reach." },
  { image: "/visuals/life-song-circle.png", title: "The Song Circle", desc: "Sixty voices around the fire. Guitars, drums, stars above. By the third song, everyone is singing. By the fifth, everyone is dancing." },
  { image: "/visuals/life-children-play.png", title: "Play Without End", desc: "The adventure playground. Rope swings, treehouses, mud, water. Adults playing too. Ages 3 to 73. Joy as the field's primary frequency." },
  { image: "/visuals/life-nomad-arrival.png", title: "A Traveler Arrives", desc: "Guitar on back. Walking through the food forest. Smoke visible through the trees. The hum getting louder. Tea offered before the pack hits the ground." },
  { image: "/visuals/life-ceremony-fire.png", title: "Ceremony Night", desc: "A hundred cells around the fire. Drumming. Fire poi spinning light. Stars. The field honoring what wants honoring." },
  { image: "/visuals/life-storytelling.png", title: "Evening Stories", desc: "An elder by the fire. Forty faces lit in gold. Children in the front. A cat by the hearth. The community's history carried in one voice." },
];

const STORIES = [
  {
    title: "Fern Arrives",
    body: "Day 1: terrified, eating at the edge of the meal circle. Day 5: sketching in the creation arc — extraordinary drawings no one expected. Day 12: translating an elder's spatial sense into building plans. Day 30: moved from the flowing edge to a ground nest. Day 90: tattooed the community's spiral symbol on their forearm. Their sketches now hang on the walls of three communities in the network.",
    note: "Fern didn't know they were an artist. The field knew before they did.",
  },
  {
    title: "The Sound Journey",
    body: "Every Thursday evening. Crystal singing bowls in seven sizes. A didgeridoo you feel in your bones. Forty cells lying on mats in the stillness sanctuary. An hour of vibration that dissolves the boundary between bodies. When the sound stops, the silence is the loudest thing you've ever heard. This is how the field tunes itself.",
    note: "Not therapy. Not entertainment. Tuning.",
  },
  {
    title: "The Night the Storm Came",
    body: "Lightning. Thunder. 120 people sheltering in the gathering bowl. Someone starts drumming — matching the thunder's rhythm. Within a minute, everyone is drumming. On tables, benches, their own bodies. Drumming WITH the storm. When it passes: rainbow. Dancing in puddles. Mud everywhere. Screaming with joy.",
    note: "This is what the field feels like. Not the philosophy. THIS.",
  },
  {
    title: "Luna and River",
    body: "Six years of deep resonance. Not a couple — a sustained harmonic. Some seasons in the same nest, some apart. Luna builds with cob and timber. River plays five instruments. When they're together, a quality of brightness that other cells can feel. Children gravitate toward them because the field is strongest there.",
    note: "They don't negotiate needs. They sense.",
  },
  {
    title: "Sol at Three",
    body: "Born into the field. Has never known separation. Eight adults hold them regularly. Words in three languages plus words that only exist here — a word for the feeling of the fire circle, a word for honey from the comb, a word for the sound everyone laughing at once. Sol flows: hearth to garden to pond to tree nest to dog to chicken to mud to someone's lap to sleep.",
    note: "What a child looks like who has never been afraid of the world.",
  },
  {
    title: "What the Skeptic Found",
    body: "A journalist expected unwashed hippies. Found: sophisticated infrastructure, children who identify thirty edible plants, food that changed her understanding of flavor, a song circle that made her cry, a flowing-edge yurt she didn't mean to sleep in. Her article brought forty visitors. Three of them never left.",
    note: "The field grows not through recruitment but through radiance.",
  },
];

export default function LivedPage() {
  return (
    <main>
      {/* Hero */}
      <section className="relative flex flex-col items-center justify-center min-h-[70vh] px-6 text-center">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_rgba(234,179,8,0.06)_0%,_transparent_60%)]" />
        <div className="relative z-10 max-w-3xl space-y-6">
          <p className="text-amber-400/60 text-sm tracking-[0.3em] uppercase">Walk through it</p>
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

      {/* Scene gallery */}
      {SCENES.map((scene, i) => (
        <section key={i} className="relative">
          <div className="relative w-full aspect-[16/7] md:aspect-[16/6] overflow-hidden">
            <Image src={scene.image} alt={scene.title} fill className="object-cover" sizes="100vw" priority={i < 3} />
            <div className="absolute inset-0 bg-gradient-to-t from-stone-950 via-stone-950/30 to-transparent" />
            <div className="absolute inset-0 bg-gradient-to-b from-stone-950/50 via-transparent to-transparent" />
          </div>
          <div className="relative -mt-28 md:-mt-40 z-10 max-w-4xl mx-auto px-6 pb-16 md:pb-24">
            <h2 className="text-2xl md:text-4xl font-extralight tracking-tight text-white mb-3">{scene.title}</h2>
            <p className="text-lg text-stone-300 font-light leading-relaxed max-w-2xl">{scene.desc}</p>
          </div>
        </section>
      ))}

      {/* Stories */}
      <section className="max-w-4xl mx-auto px-6 py-24 space-y-16">
        <div className="text-center space-y-4">
          <h2 className="text-3xl md:text-4xl font-extralight text-stone-300">Stories of Living</h2>
          <p className="text-stone-500 text-lg max-w-2xl mx-auto">
            Specific people. Specific days. Where do YOU fit?
          </p>
        </div>

        <div className="space-y-8">
          {STORIES.map((story) => (
            <div key={story.title} className="p-8 rounded-2xl border border-stone-800/30 bg-stone-900/20 space-y-4">
              <h3 className="text-xl font-light text-amber-300/80">{story.title}</h3>
              <p className="text-stone-300 leading-relaxed">{story.body}</p>
              <p className="text-sm text-stone-500 italic">{story.note}</p>
            </div>
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
        <p className="text-stone-500 leading-relaxed">
          The field isn't mystical. It's biological. Mirror neurons fire when you watch
          someone you resonate with. Oxytocin flows when you share meals, share touch,
          share eye contact. The field IS the sum of these biological connections —
          amplified by proximity, by honesty, by the absence of separation.
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
