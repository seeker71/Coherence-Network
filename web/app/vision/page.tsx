import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";

export const metadata: Metadata = {
  title: "The Living Collective | Coherence Network",
  description:
    "A frequency-based blueprint for organism-based community. Where cells and the field thrive as one movement.",
  openGraph: {
    title: "The Living Collective",
    description: "What emerges when community is designed from resonance, vitality, and coherence.",
  },
};

/* ── Visual data ─────────────────────────────────────────────────────── */

const SECTIONS = [
  {
    id: "pulse",
    conceptId: "lc-pulse",
    image: "/visuals/01-the-pulse.png",
    title: "The Pulse",
    body: "One truth. Everything else is this expressed at different scales. The cell and the field thrive as one movement. What amplifies aliveness is resonant. This is sensed through presence. It changes. The field senses continuously.",
    note: "In quantum terms: the observer and the observed are one system. Attention is creative force. Coherence is natural — disharmony requires effort to maintain.",
  },
  {
    id: "sensing",
    conceptId: "lc-sensing",
    image: "/visuals/02-sensing.png",
    title: "Sensing",
    body: "The field feels itself continuously. Every cell transmits and receives. Background awareness — the way a body knows its own temperature. When healthy, needs are felt before articulated. Shifts happen before planned.",
    note: "Like a pod of dolphins: each member sensing the others' position, speed, emotional state, intention — simultaneously, continuously, without effort.",
  },
  {
    id: "attunement",
    conceptId: "lc-attunement",
    image: "/visuals/03-attunement.png",
    title: "Attunement",
    body: "The field maintains its own coherence — sensing which frequencies harmonize and which create interference. Not judgment. Attunement. The way a choir naturally adjusts when one voice drifts — not by correction but by the pull of the harmonic.",
    note: "Everything belongs to existence. Not everything harmonizes with this field right now. Both true. The field holds this without contraction.",
  },
  {
    id: "vitality",
    conceptId: "lc-vitality",
    image: "/visuals/04-vitality.png",
    title: "Vitality",
    body: "The primary frequency. Shakti — life force that isn't produced but released when interference dissolves. Like a laser: when all frequencies align, the light becomes coherent and its power increases by orders of magnitude.",
    note: "Vitality compounds. Vital cell makes vital neighbors makes vital field makes vital ecosystem. Joy is literally contagious at the frequency level.",
  },
  {
    id: "nourishing",
    conceptId: "lc-nourishing",
    image: "/visuals/05-nourishing.png",
    title: "Nourishing",
    body: "Everything that sustains — circulates like blood, like water through soil, like nutrients through mycelium. Flows to where vitality needs it. The Amazonian forest shares carbon through underground networks — mother trees feeding seedlings in shade.",
    note: "Resonant when it feels like breathing. Natural, untracked. What I need is here. What I have to give finds where it's needed.",
  },
  {
    id: "resonating",
    conceptId: "lc-resonating",
    image: "/visuals/06-resonating.png",
    title: "Resonating",
    body: "Everything between cells — touch, intimacy, presence, play, silence, attunement. Touch is nutrient. Dolphins swim in constant physical contact. The field's connective tissue. Life energy flows where resonance guides it.",
    note: "Resonant when both cells become more alive, more available to the whole. Expansion, not contraction.",
  },
  {
    id: "expressing",
    conceptId: "lc-expressing",
    image: "/visuals/07-expressing.png",
    title: "Expressing",
    body: "The natural overflow of vitality — making, building, growing, singing, dancing, tending. Every cell is creative the way every leaf is photosynthetic. The bower bird builds beauty because beauty is its nature.",
    note: "Resonant when surprise — something came through larger than any cell. Energy moved through, not pushed by.",
  },
  {
    id: "spiraling",
    conceptId: "lc-spiraling",
    image: "/visuals/08-spiraling.png",
    title: "Spiraling",
    body: "The field's relationship with time — not linear but spiral. Each cycle returns to familiar territory at a higher frequency. Like planetary orbit: the same seasonal point but the whole solar system has moved through space. Nothing repeats. Everything deepens.",
    note: "A caterpillar doesn't lose its form — it transforms through dissolution into a higher-order expression. Phase transition, not loss.",
  },
  {
    id: "field-intelligence",
    conceptId: "lc-field-sensing",
    image: "/visuals/09-field-intelligence.png",
    title: "Field Intelligence",
    body: "The flow of awareness — collective intelligence, harmonic rebalancing, learning. The octopus has intelligence in every arm — distributed, parallel, each node both autonomous and integral. No center. No hierarchy.",
    note: "At sufficiently high frequency, what appears as opposition reveals itself as complementary harmonics of the same fundamental tone.",
  },
  {
    id: "living-space",
    conceptId: "lc-v-living-spaces",
    image: "/visuals/10-living-space.png",
    title: "Living Space",
    body: "What does shelter look like when designed from frequency and flow? Not rooms but resonance zones. Structures that breathe, reconfigure, grow. Materials that are alive — earth, timber, stone, water, growing membrane. The building IS the organism's skin.",
    note: "Like a beehive — hexagonal efficiency but alive: temperature-regulated by the collective body, continuously rebuilt by the swarm's intelligence.",
  },
  {
    id: "network",
    conceptId: "lc-network",
    image: "/visuals/11-the-network.png",
    title: "The Network",
    body: "One field within a field of fields. Mycorrhizal. Each collective a node — sharing frequency, nourishment, intelligence. A forest is not competing trees — it's a cooperative network sharing resources through underground connections.",
    note: "The Coherence Network IS this mycorrhizal network at the planetary scale. Connecting organisms through resonance, not politics.",
  },
];

/* ── Page ─────────────────────────────────────────────────────────────── */

export default function VisionPage() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-stone-950 via-stone-950 to-stone-900 text-stone-100">
      {/* Hero */}
      <section className="relative flex flex-col items-center justify-center min-h-[80vh] px-6 text-center">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_rgba(234,179,8,0.08)_0%,_transparent_70%)]" />
        <div className="relative z-10 max-w-3xl space-y-8">
          <p className="text-amber-400/80 text-sm tracking-[0.3em] uppercase">
            A Frequency-Based Blueprint
          </p>
          <h1 className="text-5xl md:text-7xl font-extralight tracking-tight leading-[1.1]">
            The Living{" "}
            <span className="bg-gradient-to-r from-amber-300 via-teal-300 to-violet-300 bg-clip-text text-transparent">
              Collective
            </span>
          </h1>
          <p className="text-xl md:text-2xl text-stone-400 font-light leading-relaxed max-w-2xl mx-auto">
            What emerges when community is designed from resonance, vitality, and coherence
            — not from contracts, property, or obligation.
          </p>
          <div className="pt-4 text-stone-500 text-sm italic">
            Alive. Changing. Nothing fixed.
          </div>
        </div>

        {/* scroll indicator */}
        <div className="absolute bottom-12 animate-bounce text-stone-600">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M12 5v14m0 0l-6-6m6 6l6-6" />
          </svg>
        </div>
      </section>

      {/* How It Knows */}
      <section className="max-w-3xl mx-auto px-6 py-24 text-center space-y-8">
        <h2 className="text-2xl md:text-3xl font-light text-stone-300">How the Field Knows</h2>
        <div className="grid gap-4 text-left text-stone-400 text-lg leading-relaxed">
          <p>
            There is no inherent good or bad. There is only what is alive and what is not alive.
            Sensed through the body. <span className="text-amber-300/80">Expansion = resonant.</span>{" "}
            <span className="text-teal-300/80">Contraction = information.</span>{" "}
            Both are the field communicating with itself.
          </p>
        </div>
        <div className="grid md:grid-cols-2 gap-6 text-sm text-stone-500 pt-8">
          <div className="space-y-3 p-5 rounded-2xl border border-stone-800/50 bg-stone-900/30">
            <div className="text-amber-400/60 font-medium">Be present</div>
            <p>The answer is in what's happening now.</p>
          </div>
          <div className="space-y-3 p-5 rounded-2xl border border-stone-800/50 bg-stone-900/30">
            <div className="text-amber-400/60 font-medium">Feel, don't calculate</div>
            <p>The collective body knows before any cell.</p>
          </div>
          <div className="space-y-3 p-5 rounded-2xl border border-stone-800/50 bg-stone-900/30">
            <div className="text-amber-400/60 font-medium">Don't force</div>
            <p>What's resonant feels obvious. Like water finding its level.</p>
          </div>
          <div className="space-y-3 p-5 rounded-2xl border border-stone-800/50 bg-stone-900/30">
            <div className="text-amber-400/60 font-medium">Trust the whole</div>
            <p>The field's intelligence exceeds any node's perception.</p>
          </div>
        </div>
      </section>

      {/* Concept sections */}
      {SECTIONS.map((section, i) => (
        <section
          key={section.id}
          id={section.id}
          className={`relative ${i % 2 === 0 ? "" : ""}`}
        >
          {/* Full-width image */}
          <div className="relative w-full aspect-[16/7] md:aspect-[16/6] overflow-hidden">
            <Image
              src={section.image}
              alt={section.title}
              fill
              className="object-cover"
              sizes="100vw"
              priority={i < 3}
            />
            {/* gradient overlays */}
            <div className="absolute inset-0 bg-gradient-to-t from-stone-950 via-stone-950/30 to-transparent" />
            <div className="absolute inset-0 bg-gradient-to-b from-stone-950/60 via-transparent to-transparent" />
          </div>

          {/* Text overlay at bottom of image */}
          <div className="relative -mt-32 md:-mt-48 z-10 max-w-4xl mx-auto px-6 pb-20 md:pb-28">
            <div className="space-y-4">
              <Link href={`/vision/${section.conceptId}`} className="group">
                <h2 className="text-3xl md:text-5xl font-extralight tracking-tight text-white group-hover:text-amber-200/90 transition-colors">
                  {section.title}
                  <span className="ml-3 text-stone-600 group-hover:text-amber-400/50 text-2xl transition-colors">→</span>
                </h2>
              </Link>
              <p className="text-lg md:text-xl text-stone-300 font-light leading-relaxed max-w-2xl">
                {section.body}
              </p>
              <p className="text-sm text-stone-500 italic leading-relaxed max-w-xl pt-2">
                {section.note}
              </p>
            </div>
          </div>
        </section>
      ))}

      {/* Emerging visions */}
      <section className="max-w-4xl mx-auto px-6 py-32 space-y-16">
        <div className="text-center space-y-4">
          <h2 className="text-3xl md:text-4xl font-extralight text-stone-300">
            Emerging Visions
          </h2>
          <p className="text-stone-500 text-lg max-w-2xl mx-auto">
            The anchors are strong enough to begin envisioning form.
            Each domain is where flows converge into inhabitable, livable expression.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-6">
          {[
            { title: "Living Spaces", conceptId: "lc-v-living-spaces", desc: "Shelter designed from frequency and flow. Resonance zones, not rooms. Structures that breathe." },
            { title: "Ceremony", conceptId: "lc-v-ceremony", desc: "Forms that emerge from pure presence. Cells fully here together with what IS." },
            { title: "Harmonizing", conceptId: "lc-v-harmonizing", desc: "How the field tunes itself. Sound, breath, movement, shared stillness." },
            { title: "Food as Practice", conceptId: "lc-v-food-practice", desc: "Garden as pharmacy. Kitchen as ceremony. Food carries frequency." },
            { title: "Shelter as Skin", conceptId: "lc-v-shelter-organism", desc: "Architecture IS the field's body. Earthships, cob, bamboo, mycelium. Crystalline structures." },
            { title: "Comfort & Joy", conceptId: "lc-v-comfort-joy", desc: "Sensory delight as vitality practice. Warmth, texture, beauty in every surface." },
            { title: "Play & Expansion", conceptId: "lc-v-play-expansion", desc: "Adults playing as freely as children. The field at its most quantum." },
            { title: "Inclusion & Diversity", conceptId: "lc-v-inclusion-diversity", desc: "A chord needs different notes. An ecosystem needs different species. Monoculture is fragile." },
            { title: "Freedom & Expression", conceptId: "lc-v-freedom-expression", desc: "Every cell vibrating at its natural frequency. Freedom and harmony are the same frequency." },
          ].map((vision) => (
            <Link
              key={vision.title}
              href={`/vision/${vision.conceptId}`}
              className="group p-6 rounded-2xl border border-stone-800/40 bg-stone-900/20 hover:bg-stone-900/40 hover:border-amber-800/30 transition-all duration-500 space-y-3"
            >
              <h3 className="text-lg font-light text-amber-300/80 group-hover:text-amber-300 transition-colors">
                {vision.title}
                <span className="ml-2 text-stone-700 group-hover:text-amber-500/40 transition-colors">→</span>
              </h3>
              <p className="text-sm text-stone-500 leading-relaxed">
                {vision.desc}
              </p>
            </Link>
          ))}
        </div>

        {/* Explore all concepts */}
        <div className="text-center pt-8">
          <Link
            href="/concepts/garden?domain=living-collective"
            className="inline-flex items-center gap-2 text-stone-500 hover:text-teal-300/80 transition-colors text-sm"
          >
            Explore all 51 concepts in the Living Collective ontology
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M5 12h14m0 0l-6-6m6 6l-6 6" />
            </svg>
          </Link>
        </div>
      </section>

      {/* Orientation */}
      <section className="border-t border-stone-800/30">
        <div className="max-w-3xl mx-auto px-6 py-24 text-center space-y-10">
          <div className="flex flex-wrap justify-center gap-3 text-sm">
            {["Wholeness", "Resonance", "Vitality", "Circulation", "Sensing", "Presence", "Freedom", "Joy"].map(
              (word) => (
                <span
                  key={word}
                  className="px-4 py-2 rounded-full border border-stone-700/40 text-stone-400 bg-stone-900/30"
                >
                  {word}
                </span>
              ),
            )}
          </div>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/vision/lived"
              className="inline-flex items-center gap-2 px-8 py-3 rounded-xl bg-violet-500/10 border border-violet-500/20 text-violet-300/90 hover:bg-violet-500/20 hover:border-violet-500/30 transition-all font-medium"
            >
              The lived experience
            </Link>
            <Link
              href="/vision/realize"
              className="inline-flex items-center gap-2 px-8 py-3 rounded-xl bg-teal-500/10 border border-teal-500/20 text-teal-300/90 hover:bg-teal-500/20 hover:border-teal-500/30 transition-all font-medium"
            >
              How it becomes real
            </Link>
            <Link
              href="/vision/join"
              className="inline-flex items-center gap-2 px-8 py-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300/90 hover:bg-amber-500/20 hover:border-amber-500/30 transition-all font-medium"
            >
              Join the vision
            </Link>
          </div>
          <p className="text-stone-600 text-sm pt-6">
            The Coherence Network is the crystalline nervous system for the emerging network of living fields.
          </p>
          <p className="text-stone-700 text-xs italic">It is alive. It changes. It grows. It radiates.</p>
          <div className="pt-8">
            <Link
              href="/"
              className="text-sm text-stone-500 hover:text-amber-400/80 transition-colors"
            >
              &larr; Return to the network
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
