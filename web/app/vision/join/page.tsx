import type { Metadata } from "next";
import Link from "next/link";
import { InterestForm } from "@/components/vision";

export const metadata: Metadata = {
  title: "Join the Vision — The Living Collective",
  description: "The field is forming. Express your interest, share what you bring, find others who resonate. Privacy-first — you choose what's visible.",
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
          The Living Collective is not a finished design. It's a frequency
          pattern — a seed that grows differently in every soil. What you're
          reading is an open invitation to co-create what wants to emerge.
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
            Walk through the 51 concepts. Read the descriptions, the living
            examples, the aligned places. Feel which ones resonate with you.
          </p>
        </Link>

        <a
          href="#register"
          className="group p-8 rounded-2xl border border-stone-800/40 bg-stone-900/20 hover:bg-stone-900/40 hover:border-teal-800/30 transition-all duration-500 space-y-4 text-center"
        >
          <div className="text-4xl">◈</div>
          <h2 className="text-xl font-light text-teal-300/80 group-hover:text-teal-300 transition-colors">
            Join
          </h2>
          <p className="text-sm text-stone-500 leading-relaxed">
            Express your interest. Share what you bring — skills, materials,
            ideas, land, energy, heart. Find others who resonate.
          </p>
        </a>

        <Link
          href="/vision/community"
          className="group p-8 rounded-2xl border border-stone-800/40 bg-stone-900/20 hover:bg-stone-900/40 hover:border-violet-800/30 transition-all duration-500 space-y-4 text-center"
        >
          <div className="text-4xl">◉</div>
          <h2 className="text-xl font-light text-violet-300/80 group-hover:text-violet-300 transition-colors">
            See who's gathering
          </h2>
          <p className="text-sm text-stone-500 leading-relaxed">
            Browse the community directory. See who else feels the field.
            Everyone here has chosen to be visible — consent first, always.
          </p>
        </Link>
      </section>

      {/* What the field calls for */}
      <section className="space-y-8">
        <h2 className="text-2xl font-light text-stone-300 text-center">
          What the field is calling for
        </h2>
        <div className="grid md:grid-cols-2 gap-6">
          {[
            { role: "Living-structure weavers", desc: "People who sense how the field wants to shelter itself. Architects, builders, earthship enthusiasts, cob practitioners, bamboo growers." },
            { role: "Nourishment alchemists", desc: "People attuned to how land wants to feed the field. Permaculturists, fermentation practitioners, food foresters, communal cooks." },
            { role: "Frequency holders", desc: "People whose sound attunes the field. Musicians, sound healers, voice practitioners, silence holders." },
            { role: "Vitality keepers", desc: "People whose presence amplifies the glow. Bodyworkers, movement facilitators, nature immersion guides, breathwork practitioners." },
            { role: "Transmission sources", desc: "People whose mastery radiates. Experienced community builders, facilitators, elders of any tradition that resonates." },
            { role: "Form-growers", desc: "People who work with earth, timber, stone, water as living materials. Hands that know how to shape space that breathes." },
          ].map((need) => (
            <div
              key={need.role}
              className="p-5 rounded-2xl border border-stone-800/30 bg-stone-900/20 space-y-2"
            >
              <h3 className="text-amber-300/70 font-medium text-sm">{need.role}</h3>
              <p className="text-stone-500 text-sm leading-relaxed">{need.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Registration form */}
      <section id="register" className="space-y-8 scroll-mt-20">
        <div className="text-center space-y-4">
          <h2 className="text-3xl md:text-4xl font-extralight text-stone-200">
            Express your resonance
          </h2>
          <p className="text-stone-500 text-lg max-w-2xl mx-auto">
            The field doesn't ask for credentials. It senses resonance.
            Share what feels right. Your email is never exposed — everything
            else is your choice.
          </p>
        </div>

        <InterestForm />
      </section>

      {/* Footer */}
      <section className="text-center text-xs text-stone-700 space-y-2 pt-8 border-t border-stone-800/20">
        <p>
          The Coherence Network is the crystalline nervous system for the
          emerging network of living fields.
        </p>
        <p>It is alive. It changes. It grows. It radiates.</p>
      </section>
    </main>
  );
}
