import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Join the Vision — The Living Collective",
  description: "Explore, contribute, resonate. The Living Collective is an open invitation to co-create a new way of living together.",
};

export default function JoinPage() {
  return (
    <main className="max-w-4xl mx-auto px-6 py-20 space-y-24">
      {/* Hero */}
      <section className="text-center space-y-8">
        <h1 className="text-4xl md:text-6xl font-extralight tracking-tight text-white">
          The field is{" "}
          <span className="bg-gradient-to-r from-amber-300 via-teal-300 to-violet-300 bg-clip-text text-transparent">
            forming
          </span>
        </h1>
        <p className="text-xl text-stone-400 font-light leading-relaxed max-w-2xl mx-auto">
          The Living Collective is not a finished design. It's a frequency pattern — a seed
          that grows differently in every soil. What you're reading is an open invitation
          to co-create what wants to emerge.
        </p>
      </section>

      {/* Three paths */}
      <section className="grid md:grid-cols-3 gap-8">
        <Link
          href="/vision"
          className="group p-8 rounded-2xl border border-stone-800/40 bg-stone-900/20 hover:bg-stone-900/40 hover:border-amber-800/30 transition-all duration-500 space-y-4 text-center"
        >
          <div className="text-4xl">✦</div>
          <h2 className="text-xl font-light text-amber-300/80 group-hover:text-amber-300 transition-colors">
            Explore
          </h2>
          <p className="text-sm text-stone-500 leading-relaxed">
            Walk through the 51 concepts. Read the descriptions, the living examples,
            the aligned places. Feel which ones resonate with you. Let the vision form
            in your own sensing.
          </p>
        </Link>

        <Link
          href="/contribute?tags=living-collective"
          className="group p-8 rounded-2xl border border-stone-800/40 bg-stone-900/20 hover:bg-stone-900/40 hover:border-teal-800/30 transition-all duration-500 space-y-4 text-center"
        >
          <div className="text-4xl">◈</div>
          <h2 className="text-xl font-light text-teal-300/80 group-hover:text-teal-300 transition-colors">
            Contribute
          </h2>
          <p className="text-sm text-stone-500 leading-relaxed">
            Share an idea for how any concept expresses in practice. A design for a living space.
            A ceremony form. A food practice. A harmonizing technique.
            Every contribution enriches the field.
          </p>
        </Link>

        <Link
          href="/resonance"
          className="group p-8 rounded-2xl border border-stone-800/40 bg-stone-900/20 hover:bg-stone-900/40 hover:border-violet-800/30 transition-all duration-500 space-y-4 text-center"
        >
          <div className="text-4xl">◉</div>
          <h2 className="text-xl font-light text-violet-300/80 group-hover:text-violet-300 transition-colors">
            Resonate
          </h2>
          <p className="text-sm text-stone-500 leading-relaxed">
            Discover which concepts you naturally resonate with. The field's resonance scoring
            maps your frequency against the vision's — not to judge, but to illuminate
            where your unique expression fits.
          </p>
        </Link>
      </section>

      {/* What this is */}
      <section className="space-y-6 text-center">
        <h2 className="text-2xl font-light text-stone-300">What is the Living Collective?</h2>
        <div className="text-stone-400 leading-relaxed max-w-2xl mx-auto space-y-4 text-left">
          <p>
            A community of people is an organism. The cells of this organism are vibrant,
            connected, and aligned. What amplifies aliveness is resonant. What diminishes it is not.
            This changes. The field senses continuously.
          </p>
          <p>
            The vision draws from quantum understanding (coherence, entanglement, the observer effect),
            from nature's intelligence (mycelium, dolphins, murmuration, coral reefs), from
            tantric non-duality (shakti, spanda, presence without judgment), from Taoism (wu wei,
            effortless alignment), and from communities that already embody pieces of this —
            Auroville, Findhorn, Tamera, Gaviotas, indigenous practices worldwide.
          </p>
          <p>
            51 concepts organized fractally — from The Pulse (the root) through three systems,
            five flows, living expressions in every domain of shared life, and nine emerging visions
            ready for concrete realization. All stored as living nodes in the Coherence Network,
            cross-linked, resonance-scored, and waiting for your contribution.
          </p>
        </div>
      </section>

      {/* What we need */}
      <section className="space-y-8">
        <h2 className="text-2xl font-light text-stone-300 text-center">What the field is calling for</h2>
        <div className="grid md:grid-cols-2 gap-6">
          {[
            { role: "Living-structure weavers", desc: "People who sense how the field wants to shelter itself. Architects, builders, earthship enthusiasts, cob practitioners, bamboo growers." },
            { role: "Nourishment alchemists", desc: "People attuned to how land wants to feed the field. Permaculturists, fermentation practitioners, food foresters, communal cooks." },
            { role: "Frequency holders", desc: "People whose sound attunes the field. Musicians, sound healers, voice practitioners, silence holders." },
            { role: "Vitality keepers", desc: "People whose presence amplifies the glow. Bodyworkers, movement facilitators, nature immersion guides, breathwork practitioners." },
            { role: "Transmission sources", desc: "People whose mastery radiates. Experienced community builders, facilitators, elders of any tradition that resonates." },
            { role: "Form-growers", desc: "People who work with earth, timber, stone, water as living materials. Hands that know how to shape space that breathes." },
          ].map((need) => (
            <div key={need.role} className="p-5 rounded-2xl border border-stone-800/30 bg-stone-900/20 space-y-2">
              <h3 className="text-amber-300/70 font-medium text-sm">{need.role}</h3>
              <p className="text-stone-500 text-sm leading-relaxed">{need.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="text-center space-y-6 py-12">
        <p className="text-stone-500 text-lg italic">
          The field doesn't ask for credentials. It senses resonance.
        </p>
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Link
            href="/vision"
            className="px-8 py-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300/90 hover:bg-amber-500/20 hover:border-amber-500/30 transition-all font-medium"
          >
            Explore the vision
          </Link>
          <Link
            href="/contribute?tags=living-collective"
            className="px-8 py-3 rounded-xl bg-teal-500/10 border border-teal-500/20 text-teal-300/90 hover:bg-teal-500/20 hover:border-teal-500/30 transition-all font-medium"
          >
            Contribute an idea
          </Link>
        </div>
      </section>

      {/* Footer */}
      <section className="text-center text-xs text-stone-700 space-y-2 pt-8 border-t border-stone-800/20">
        <p>The Coherence Network is the crystalline nervous system for the emerging network of living fields.</p>
        <p>It is alive. It changes. It grows. It radiates.</p>
      </section>
    </main>
  );
}
