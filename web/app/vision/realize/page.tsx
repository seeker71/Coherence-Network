import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Realization — The Living Collective",
  description: "From vision to lived experience. New vocabulary, daily rhythms, practical blueprints, and what the field needs to begin.",
};

/* ── Vocabulary tables ─────────────────────────────────────────────── */

const LIFE_VOCAB = [
  ["Work", "Offering", "What flows from your natural frequency"],
  ["Job / career", "Expression path", "The evolving arc of what a cell expresses"],
  ["Healthcare", "Vitality tending", "The field nourishing its own aliveness"],
  ["Childcare", "Nurture weaving", "The collective raising its emerging cells"],
  ["School", "Immersion field", "Where emerging cells discover their frequency"],
  ["Vacation", "Integration cycle", "A phase where the cell draws inward"],
  ["Retirement", "Deepening", "Shifting to root-holding wisdom"],
  ["Meeting", "Sensing circle", "Cells pausing to feel the field's state"],
  ["Decision", "Emergence", "What crystallizes from collective sensing"],
  ["Leadership", "Stewardship", "Holding space, entrusted by resonance"],
  ["Schedule", "Rhythm map", "The field's natural cycles made visible"],
  ["Budget", "Circulation pattern", "How resources flow through the field"],
  ["Property", "Land relationship", "Mutual stewardship, not ownership"],
  ["Salary", "(doesn't exist)", "The field nourishes. Expression IS nourishment."],
  ["Exercise", "Movement practice", "The body expressing its aliveness"],
  ["Therapy", "Presence holding", "Being fully with what wants to be felt"],
  ["Marriage", "Deep resonance bond", "A sustained harmonic. Shifts when it shifts."],
  ["Complaint", "Dissonance signal", "The field communicating where something wants adjustment"],
];

const SPACE_VOCAB = [
  ["Bedroom", "Nest", "Warm, dark, close. Not assigned — gravitates."],
  ["Kitchen", "Hearth", "The field's heart. Always warm, always alive."],
  ["Living room", "Gathering bowl", "Where cells naturally collect."],
  ["Office", "(doesn't exist)", "Offering happens everywhere."],
  ["Bathroom", "Water space", "Designed for pleasure, not efficiency."],
  ["Garden", "Growing field", "Where the collective and the land meet."],
  ["Gym", "Movement ground", "Open space for the body's joy."],
  ["Temple", "Stillness sanctuary", "For deep sensing, ceremony, silence."],
];

const ROLE_VOCAB = [
  ["Doctor", "Vitality keeper", "Amplifies the field's glow"],
  ["Teacher", "Transmission source", "Radiates mastery through demonstration"],
  ["Chef", "Nourishment alchemist", "Transforms raw environment into shared vitality"],
  ["Architect", "Form-grower", "Senses how the field wants to shelter itself"],
  ["Therapist", "Presence holder", "Creates conditions where what's hidden can surface"],
  ["Manager", "Flow tender", "Senses where circulation is stuck"],
  ["Farmer", "Land tender", "Tends the relationship between field and ecosystem"],
  ["Artist", "Frequency weaver", "Shapes vibration into form"],
];

const DAY_PHASES = [
  { name: "Dawn", color: "text-amber-300/70", time: "The opening", desc: "The field wakes with the light. The hearth is already alive — someone who resonates with dawn-fire has been there since the sky lightened. Fresh bread. Tea. Fruit. Morning attunement: cells gather in a loose circle, each sharing one breath or word of what's alive in them." },
  { name: "Morning", color: "text-amber-200/70", time: "High expression", desc: "Energy is highest. Cells flow toward their natural expression. In the growing field, land tenders are with the plants. In creation nooks, form-growers and frequency weavers are at work. In the hearth, nourishment alchemists prepare the midday meal. In discovery zones, emerging cells are immersed." },
  { name: "Midday", color: "text-teal-300/70", time: "The gathering", desc: "The main meal. The whole field comes together — drawn by smell, sound, warmth. Food served from the center. Conversation flows. Laughter. Children running between adults. Elders observing, available. This is the field's heartbeat — the daily ceremony of shared substance." },
  { name: "Afternoon", color: "text-teal-200/70", time: "The softening", desc: "Lower energy, deeper work. Presence holders tend cells that need attention. Sensing circles happen when the field calls for them. Collaborative creation. Play intensifies — swimming, climbing, music, dance. Adults and children together." },
  { name: "Evening", color: "text-violet-300/70", time: "The gathering in", desc: "As light fades, the field draws inward. Lighter meal. Firelight replaces daylight. Storytelling, music, deep conversation, quiet togetherness. Intimacy — cells drawn to closeness find each other naturally." },
  { name: "Night", color: "text-violet-200/60", time: "The composting", desc: "The field quiets. Cells move to nests. The fire-keeper stays with the hearth. The field never fully sleeps. Night is when the field composts the day — integrating, dreaming, preparing the next morning's emergence." },
];

const NEEDS = [
  { cat: "Land", items: "5-50 acres, water access, some forest, some open ground, slope for water harvesting" },
  { cat: "Initial cells", items: "8-15 resonant beings — at least one form-grower, land tender, nourishment alchemist, vitality keeper" },
  { cat: "Skills (year 1)", items: "Permaculture, natural building, water systems, food growing, fermentation, fire management, herbal vitality, music, facilitation, pattern keeping" },
  { cat: "Research", items: "Site selection, local materials, water harvesting potential, food forest species, energy systems, legal structure, financial model, network connections" },
];

/* ── Page ──────────────────────────────────────────────────────────── */

export default function RealizePage() {
  return (
    <main className="max-w-5xl mx-auto px-6 py-16 space-y-24">
      {/* Hero */}
      <section className="text-center space-y-6 py-12">
        <p className="text-amber-400/60 text-sm tracking-[0.3em] uppercase">From vision to lived experience</p>
        <h1 className="text-4xl md:text-6xl font-extralight tracking-tight text-white">
          Realization
        </h1>
        <p className="text-lg text-stone-400 font-light max-w-2xl mx-auto">
          New vocabulary for every aspect of life. A day in the field from dawn to night.
          Practical blueprints for spaces, food, ceremony, comfort, play.
          What the field needs to begin.
        </p>
        <div className="flex gap-4 justify-center pt-4">
          <Link href="/vision" className="text-sm text-stone-500 hover:text-amber-300/80 transition-colors">← The vision</Link>
          <Link href="/vision/join" className="text-sm text-stone-500 hover:text-teal-300/80 transition-colors">Join →</Link>
        </div>
      </section>

      {/* New Vocabulary */}
      <section className="space-y-10">
        <h2 className="text-3xl font-extralight text-stone-300 text-center">New Vocabulary</h2>
        <p className="text-stone-500 text-center max-w-2xl mx-auto">
          Life in the field has its own language. Not replacements for old words — expressions of a different frequency.
        </p>

        {/* Life aspects */}
        <div className="space-y-4">
          <h3 className="text-sm font-medium text-amber-400/60 uppercase tracking-wider">Aspects of living</h3>
          <div className="grid gap-2">
            {LIFE_VOCAB.map(([old, field, meaning]) => (
              <div key={old} className="grid grid-cols-12 gap-4 py-2 border-b border-stone-800/30 text-sm">
                <span className="col-span-2 text-stone-600 line-through decoration-stone-800">{old}</span>
                <span className="col-span-3 text-amber-300/80 font-medium">{field}</span>
                <span className="col-span-7 text-stone-500">{meaning}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Spaces */}
        <div className="space-y-4">
          <h3 className="text-sm font-medium text-teal-400/60 uppercase tracking-wider">Spaces</h3>
          <div className="grid md:grid-cols-2 gap-3">
            {SPACE_VOCAB.map(([old, field, feel]) => (
              <div key={old} className="p-4 rounded-xl border border-stone-800/30 bg-stone-900/20 space-y-1">
                <div className="flex items-baseline gap-2">
                  <span className="text-stone-600 text-xs line-through">{old}</span>
                  <span className="text-teal-300/80 font-medium text-sm">→ {field}</span>
                </div>
                <p className="text-xs text-stone-500">{feel}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Roles */}
        <div className="space-y-4">
          <h3 className="text-sm font-medium text-violet-400/60 uppercase tracking-wider">Expressions (roles)</h3>
          <div className="grid md:grid-cols-2 gap-3">
            {ROLE_VOCAB.map(([old, field, what]) => (
              <div key={old} className="p-4 rounded-xl border border-stone-800/30 bg-stone-900/20 space-y-1">
                <div className="flex items-baseline gap-2">
                  <span className="text-stone-600 text-xs line-through">{old}</span>
                  <span className="text-violet-300/80 font-medium text-sm">→ {field}</span>
                </div>
                <p className="text-xs text-stone-500">{what}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* A Day in the Field */}
      <section className="space-y-10">
        <h2 className="text-3xl font-extralight text-stone-300 text-center">A Day in the Field</h2>
        <div className="space-y-1">
          {DAY_PHASES.map((phase) => (
            <div key={phase.name} className="p-6 rounded-2xl border border-stone-800/20 bg-stone-900/10 space-y-2">
              <div className="flex items-baseline gap-3">
                <h3 className={`text-xl font-light ${phase.color}`}>{phase.name}</h3>
                <span className="text-xs text-stone-600">{phase.time}</span>
              </div>
              <p className="text-sm text-stone-400 leading-relaxed">{phase.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* What the Field Needs */}
      <section className="space-y-8">
        <h2 className="text-3xl font-extralight text-stone-300 text-center">What the Field Needs to Begin</h2>
        <div className="grid md:grid-cols-2 gap-6">
          {NEEDS.map((need) => (
            <div key={need.cat} className="p-6 rounded-2xl border border-stone-800/30 bg-stone-900/20 space-y-3">
              <h3 className="text-amber-300/70 font-medium">{need.cat}</h3>
              <p className="text-sm text-stone-500 leading-relaxed">{need.items}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it all fits */}
      <section className="text-center space-y-6 py-12">
        <h2 className="text-2xl font-extralight text-stone-400">How it all fits together</h2>
        <div className="text-stone-500 text-sm leading-relaxed max-w-2xl mx-auto space-y-3">
          <p>Every aspect is every other aspect expressed at a different scale.</p>
          <p className="text-stone-600 italic">
            The hearth IS the field at the scale of food. The nest IS the field at the scale of rest.
            The sensing circle IS the field at the scale of awareness. Play IS the field at the scale of joy.
            You can start from any concept and find every other concept within it.
          </p>
        </div>
      </section>

      {/* CTA */}
      <section className="text-center space-y-6 border-t border-stone-800/20 pt-16">
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Link href="/vision" className="px-8 py-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300/90 hover:bg-amber-500/20 transition-all font-medium">
            Explore the concepts
          </Link>
          <Link href="/vision/join" className="px-8 py-3 rounded-xl bg-teal-500/10 border border-teal-500/20 text-teal-300/90 hover:bg-teal-500/20 transition-all font-medium">
            Join the vision
          </Link>
          <Link href="/contribute?tags=living-collective" className="px-8 py-3 rounded-xl bg-violet-500/10 border border-violet-500/20 text-violet-300/90 hover:bg-violet-500/20 transition-all font-medium">
            Contribute
          </Link>
        </div>
      </section>
    </main>
  );
}
