import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { PrintButton } from "@/components/vision/PrintButton";
import { pollinationsUrl } from "@/lib/vision-utils";

export const metadata: Metadata = {
  title: "Community Posters — The Living Collective",
  description: "Photorealistic visualizations of what The Living Collective looks and feels like — sacred spaces, shared kitchens, gardens, workshops, gathering circles across different landscapes.",
};

/**
 * Each poster is a photorealistic visualization of one aspect of community life.
 * Images generated via Pollinations.ai FLUX model — free, no auth, URL-based.
 *
 * The posters cover:
 * - Sacred spaces (gathering, ceremony, meditation)
 * - Shared kitchens / hearths
 * - Living gardens / food forests
 * - Open workshops / maker spaces
 * - Children's spaces
 * - Sound / music circles
 * - Natural dwellings
 * - The full community from above
 *
 * Multiple locations: Colorado mountains, coastal Pacific, Mediterranean, tropical
 */

type Poster = {
  id: string;
  title: string;
  subtitle: string;
  description: string;
  prompt: string;
  location: string;
  scale: string;
};

const POSTERS: Poster[] = [
  // ── Colorado Mountain Community ──
  {
    id: "co-aerial",
    title: "The Living Field",
    subtitle: "Colorado Rockies — 100 people",
    description: "Aerial view of a 100-person community nestled in the Colorado mountains. Organic roundhouses and earthen structures arranged in a spiral pattern. Central gathering circle with a fire pit. Terraced permaculture gardens flowing down the hillside. Solar panels integrated naturally. Mountain peaks in the background.",
    prompt: "photorealistic aerial view of an intentional community of 30 organic roundhouses and earthen structures arranged in spiral pattern in Colorado Rocky Mountains, central fire pit gathering circle, terraced permaculture gardens on hillside, solar panels, aspen trees, mountain peaks background, golden hour lighting, drone photography style, ultra detailed, 8k",
    location: "Colorado, USA",
    scale: "100 people",
  },
  {
    id: "co-hearth",
    title: "The Hearth",
    subtitle: "Shared kitchen — open fire, communal table",
    description: "A large open-air kitchen with massive wooden communal tables. Clay oven, herb garden right outside, morning light streaming through. People of all ages cooking and eating together. Warm, alive, abundant.",
    prompt: "photorealistic large open-air communal kitchen in mountain setting, massive rustic wooden tables seating 30 people, clay wood-fired oven, fresh herbs and vegetables, morning golden light streaming in, people cooking together, warm atmosphere, abundant food, mountain community, professional architecture photography, 8k",
    location: "Colorado, USA",
    scale: "100 people",
  },
  {
    id: "co-garden",
    title: "The Living Garden",
    subtitle: "Permaculture food forest, terraced beds",
    description: "Terraced permaculture gardens with fruit trees, herbs, vegetables in polyculture. Winding paths, water features, people working the soil together. Mountains in the background. Abundant, diverse, alive.",
    prompt: "photorealistic terraced permaculture food forest garden in Colorado mountains, diverse polyculture with fruit trees vegetables herbs, winding stone paths, small pond, people gardening together, aspen and pine trees, mountain backdrop, abundant harvest, golden hour, professional landscape photography, 8k",
    location: "Colorado, USA",
    scale: "100 people",
  },
  {
    id: "co-sound",
    title: "The Sound Circle",
    subtitle: "Where the field attunes itself",
    description: "An outdoor amphitheater-like circle of natural stone seating. Musicians with drums, singing bowls, flutes gathered in the center. Evening light, lanterns, stars beginning to emerge. The sound visible as energy in the air.",
    prompt: "photorealistic outdoor natural stone amphitheater circle in mountain meadow, musicians with drums singing bowls and flutes in center, warm lantern light, twilight sky with first stars, 30 people sitting in circle, mystical atmosphere, Colorado mountains background, professional event photography, 8k",
    location: "Colorado, USA",
    scale: "100 people",
  },
  {
    id: "co-workshop",
    title: "The Open Workshop",
    subtitle: "Maker space where hands create",
    description: "A spacious timber-frame workshop with natural light. Woodworking, metalwork, pottery areas. Tools organized beautifully. People collaborating on building projects. Sawdust in the air, creative energy palpable.",
    prompt: "photorealistic large timber-frame open workshop maker space, natural light through large windows, woodworking area with hand tools, pottery wheels, metalwork station, people collaborating on projects, sawdust in sunbeams, organized tool walls, creative atmosphere, mountain community, professional interior photography, 8k",
    location: "Colorado, USA",
    scale: "100 people",
  },
  {
    id: "co-dwelling",
    title: "The Nest",
    subtitle: "Where the organism sleeps and dreams",
    description: "An earthen roundhouse dwelling with living roof. Natural materials — cob, timber, stone. Large windows framing mountain views. Cozy interior with handmade furniture. Warm light, plants, books.",
    prompt: "photorealistic earthen roundhouse dwelling with living green roof in Colorado mountains, cob and timber construction, large windows with mountain view, cozy interior visible, handmade wooden furniture, warm evening light, plants hanging, natural stone pathway, professional architecture photography, 8k",
    location: "Colorado, USA",
    scale: "Individual dwelling",
  },

  // ── Coastal Pacific Community ──
  {
    id: "pac-aerial",
    title: "Ocean Field",
    subtitle: "Pacific Coast — 200 people",
    description: "A larger community on a coastal bluff overlooking the Pacific. Interconnected structures with living roofs. Vegetable terraces stepping down toward the sea. Wind turbines and solar integrated. Tide pools visible below.",
    prompt: "photorealistic aerial view of 50-structure intentional community on Pacific coast bluff, interconnected organic buildings with living green roofs, terraced gardens stepping toward ocean, small wind turbines and solar panels, tide pools below cliff, Pacific ocean panorama, sunset light, drone photography, ultra detailed, 8k",
    location: "Pacific Coast, USA",
    scale: "200 people",
  },
  {
    id: "pac-gathering",
    title: "The Gathering Circle",
    subtitle: "Where the organism speaks with itself",
    description: "A large circular gathering space, open to the sky, with the ocean visible beyond. Concentric rings of natural seating. A central fire. 100+ people sitting in council. Wind in their hair. Deep presence.",
    prompt: "photorealistic large outdoor circular gathering space on coastal bluff, concentric rings of natural stone and wood seating, central fire pit with small flame, 100 people sitting in circle formation, Pacific ocean visible beyond, golden sunset light, wind in hair, deep contemplative atmosphere, professional photography, 8k",
    location: "Pacific Coast, USA",
    scale: "200 people",
  },

  // ── Mediterranean Community ──
  {
    id: "med-aerial",
    title: "Sun Field",
    subtitle: "Mediterranean hillside — 75 people",
    description: "White-washed structures with terracotta roofs cascading down a sun-drenched hillside. Olive groves and grape arbors. Central courtyard with fountain. Azure sky, warmth radiating.",
    prompt: "photorealistic aerial view of intentional community of 20 white-washed structures with terracotta roofs on Mediterranean hillside, olive groves and grape arbors, central courtyard with stone fountain, winding stone paths, herb gardens, azure sky, warm golden light, professional drone photography, 8k",
    location: "Mediterranean",
    scale: "75 people",
  },
  {
    id: "med-courtyard",
    title: "The Heart Space",
    subtitle: "Where all paths meet",
    description: "A sun-drenched central courtyard with a stone fountain. Tables with shared meals. Children playing. Elders in shade. Vines overhead casting dappled shadows. The pulse of the organism.",
    prompt: "photorealistic Mediterranean courtyard with ancient stone fountain center, long wooden tables with shared colorful meal, children playing, elders sitting in shade of vine-covered pergola, dappled sunlight, bougainvillea and jasmine, warm convivial atmosphere, professional lifestyle photography, 8k",
    location: "Mediterranean",
    scale: "75 people",
  },

  // ── Tropical Community ──
  {
    id: "trop-aerial",
    title: "Jungle Field",
    subtitle: "Tropical forest — 50 people",
    description: "Elevated bamboo structures connected by walkways through the canopy. River below. Cacao and banana gardens at ground level. Open-air gathering platforms. Birds, butterflies, life everywhere.",
    prompt: "photorealistic aerial view of small intentional community of 15 elevated bamboo structures connected by walkways through tropical forest canopy, river below, cacao and banana gardens at ground level, open-air gathering platform, lush vegetation, birds in flight, golden morning mist, professional drone photography, 8k",
    location: "Tropical",
    scale: "50 people",
  },
  {
    id: "trop-children",
    title: "The Weaving Ground",
    subtitle: "Where children are teachers and the world is the classroom",
    description: "An open-air children's space under the canopy. Natural play structures made from bamboo and rope. Children of all ages exploring, climbing, creating. Mud kitchen, tree houses, art materials. Adults present but not directing.",
    prompt: "photorealistic open-air children nature play space in tropical forest, natural bamboo and rope climbing structures, tree houses, mud kitchen area, children ages 3-12 exploring and playing freely, art materials and natural objects, adults sitting nearby watching lovingly, dappled forest light, professional documentary photography, 8k",
    location: "Tropical",
    scale: "50 people",
  },
];

// pollinationsUrl imported from @/lib/vision-utils

export default function PostersPage() {
  return (
    <>
      {/* Print styles */}
      <style>{`
        @media print {
          body { background: white !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
          .no-print { display: none !important; }
          .poster-card { page-break-inside: avoid; break-inside: avoid; }
          @page { margin: 0.25in; size: letter landscape; }
        }
      `}</style>

      <main className="max-w-7xl mx-auto px-6 py-12 space-y-16">
        {/* Header */}
        <div className="text-center space-y-6 no-print">
          <Link href="/vision/flyer" className="text-sm text-stone-600 hover:text-stone-400 transition-colors">
            &larr; Back to flyers
          </Link>
          <h1 className="text-4xl md:text-5xl font-extralight tracking-tight text-white">
            Community{" "}
            <span className="bg-gradient-to-r from-amber-300 via-teal-300 to-violet-300 bg-clip-text text-transparent">
              Visualizations
            </span>
          </h1>
          <p className="text-stone-400 text-lg max-w-2xl mx-auto">
            Photorealistic visions of what The Living Collective looks and feels like
            across different landscapes, scales, and climates. Print these to surround
            your workspace with the vision.
          </p>
          <PrintButton label="Print all posters" />
        </div>

        {/* Colorado Section */}
        <section className="space-y-8">
          <div className="space-y-2">
            <h2 className="text-2xl font-light text-amber-300/80">Colorado Rockies</h2>
            <p className="text-stone-500">Mountain community — 100 people among aspen and pine</p>
          </div>
          <div className="grid md:grid-cols-2 gap-6">
            {POSTERS.filter(p => p.location === "Colorado, USA").map((poster) => (
              <PosterCard key={poster.id} poster={poster} />
            ))}
          </div>
        </section>

        {/* Pacific Section */}
        <section className="space-y-8">
          <div className="space-y-2">
            <h2 className="text-2xl font-light text-teal-300/80">Pacific Coast</h2>
            <p className="text-stone-500">Ocean community — 200 people on the coastal bluff</p>
          </div>
          <div className="grid md:grid-cols-2 gap-6">
            {POSTERS.filter(p => p.location === "Pacific Coast, USA").map((poster) => (
              <PosterCard key={poster.id} poster={poster} />
            ))}
          </div>
        </section>

        {/* Mediterranean Section */}
        <section className="space-y-8">
          <div className="space-y-2">
            <h2 className="text-2xl font-light text-orange-300/80">Mediterranean</h2>
            <p className="text-stone-500">Sun-drenched hillside — 75 people among olive groves</p>
          </div>
          <div className="grid md:grid-cols-2 gap-6">
            {POSTERS.filter(p => p.location === "Mediterranean").map((poster) => (
              <PosterCard key={poster.id} poster={poster} />
            ))}
          </div>
        </section>

        {/* Tropical Section */}
        <section className="space-y-8">
          <div className="space-y-2">
            <h2 className="text-2xl font-light text-emerald-300/80">Tropical Forest</h2>
            <p className="text-stone-500">Canopy community — 50 people among bamboo and river</p>
          </div>
          <div className="grid md:grid-cols-2 gap-6">
            {POSTERS.filter(p => p.location === "Tropical").map((poster) => (
              <PosterCard key={poster.id} poster={poster} />
            ))}
          </div>
        </section>

        {/* Cost & Timeline Estimates */}
        <section className="space-y-8 py-12 border-t border-stone-800/20">
          <h2 className="text-2xl font-light text-stone-300 text-center">
            Rough Estimates — Making It Real
          </h2>
          <p className="text-stone-500 text-center max-w-2xl mx-auto">
            These are very rough order-of-magnitude estimates. Real numbers depend deeply on
            location, materials, labor, land costs, and how much the community builds with its own hands.
          </p>

          <div className="grid md:grid-cols-3 gap-6">
            {/* 50 people */}
            <div className="p-6 rounded-2xl border border-stone-800/30 bg-stone-900/20 space-y-4">
              <div className="text-center space-y-1">
                <div className="text-3xl font-light text-emerald-300/80">50</div>
                <div className="text-xs text-stone-600 uppercase tracking-wider">people — seed community</div>
              </div>
              <div className="space-y-3 text-sm">
                <div className="flex justify-between text-stone-400">
                  <span>Land (10-30 acres)</span>
                  <span className="text-stone-300">$200K-$2M</span>
                </div>
                <div className="flex justify-between text-stone-400">
                  <span>Dwellings (15-20 units)</span>
                  <span className="text-stone-300">$750K-$2M</span>
                </div>
                <div className="flex justify-between text-stone-400">
                  <span>Common spaces</span>
                  <span className="text-stone-300">$200K-$500K</span>
                </div>
                <div className="flex justify-between text-stone-400">
                  <span>Infrastructure</span>
                  <span className="text-stone-300">$150K-$400K</span>
                </div>
                <div className="flex justify-between text-stone-400">
                  <span>Gardens &amp; food systems</span>
                  <span className="text-stone-300">$50K-$150K</span>
                </div>
                <hr className="border-stone-800/30" />
                <div className="flex justify-between font-medium text-stone-200">
                  <span>Total range</span>
                  <span className="text-emerald-300/80">$1.3M-$5M</span>
                </div>
                <div className="flex justify-between text-stone-500 text-xs">
                  <span>Per person</span>
                  <span>$26K-$100K</span>
                </div>
                <div className="flex justify-between text-stone-500 text-xs">
                  <span>Timeline to livable</span>
                  <span>12-24 months</span>
                </div>
              </div>
            </div>

            {/* 100 people */}
            <div className="p-6 rounded-2xl border border-amber-800/20 bg-amber-900/5 space-y-4">
              <div className="text-center space-y-1">
                <div className="text-3xl font-light text-amber-300/80">100</div>
                <div className="text-xs text-stone-600 uppercase tracking-wider">people — full community</div>
              </div>
              <div className="space-y-3 text-sm">
                <div className="flex justify-between text-stone-400">
                  <span>Land (30-80 acres)</span>
                  <span className="text-stone-300">$500K-$5M</span>
                </div>
                <div className="flex justify-between text-stone-400">
                  <span>Dwellings (30-40 units)</span>
                  <span className="text-stone-300">$1.5M-$4M</span>
                </div>
                <div className="flex justify-between text-stone-400">
                  <span>Common spaces</span>
                  <span className="text-stone-300">$400K-$1M</span>
                </div>
                <div className="flex justify-between text-stone-400">
                  <span>Infrastructure</span>
                  <span className="text-stone-300">$300K-$800K</span>
                </div>
                <div className="flex justify-between text-stone-400">
                  <span>Gardens &amp; food systems</span>
                  <span className="text-stone-300">$100K-$300K</span>
                </div>
                <hr className="border-stone-800/30" />
                <div className="flex justify-between font-medium text-stone-200">
                  <span>Total range</span>
                  <span className="text-amber-300/80">$2.8M-$11M</span>
                </div>
                <div className="flex justify-between text-stone-500 text-xs">
                  <span>Per person</span>
                  <span>$28K-$110K</span>
                </div>
                <div className="flex justify-between text-stone-500 text-xs">
                  <span>Timeline to livable</span>
                  <span>18-36 months</span>
                </div>
              </div>
            </div>

            {/* 200 people */}
            <div className="p-6 rounded-2xl border border-stone-800/30 bg-stone-900/20 space-y-4">
              <div className="text-center space-y-1">
                <div className="text-3xl font-light text-violet-300/80">200</div>
                <div className="text-xs text-stone-600 uppercase tracking-wider">people — network node</div>
              </div>
              <div className="space-y-3 text-sm">
                <div className="flex justify-between text-stone-400">
                  <span>Land (80-200 acres)</span>
                  <span className="text-stone-300">$1M-$10M</span>
                </div>
                <div className="flex justify-between text-stone-400">
                  <span>Dwellings (60-80 units)</span>
                  <span className="text-stone-300">$3M-$8M</span>
                </div>
                <div className="flex justify-between text-stone-400">
                  <span>Common spaces</span>
                  <span className="text-stone-300">$800K-$2M</span>
                </div>
                <div className="flex justify-between text-stone-400">
                  <span>Infrastructure</span>
                  <span className="text-stone-300">$500K-$1.5M</span>
                </div>
                <div className="flex justify-between text-stone-400">
                  <span>Gardens &amp; food systems</span>
                  <span className="text-stone-300">$200K-$500K</span>
                </div>
                <hr className="border-stone-800/30" />
                <div className="flex justify-between font-medium text-stone-200">
                  <span>Total range</span>
                  <span className="text-violet-300/80">$5.5M-$22M</span>
                </div>
                <div className="flex justify-between text-stone-500 text-xs">
                  <span>Per person</span>
                  <span>$28K-$110K</span>
                </div>
                <div className="flex justify-between text-stone-500 text-xs">
                  <span>Timeline to livable</span>
                  <span>24-48 months</span>
                </div>
              </div>
            </div>
          </div>

          {/* Cost reduction strategies */}
          <div className="max-w-2xl mx-auto p-6 rounded-2xl border border-stone-800/20 bg-stone-900/10 space-y-4">
            <h3 className="text-lg font-light text-stone-300 text-center">
              How the field reduces cost
            </h3>
            <div className="grid md:grid-cols-2 gap-4 text-sm text-stone-500">
              <div className="space-y-1">
                <p className="text-stone-400 font-medium">Natural building</p>
                <p>Cob, rammed earth, bamboo, timber frame — materials from the land, 40-60% cheaper than conventional</p>
              </div>
              <div className="space-y-1">
                <p className="text-stone-400 font-medium">Collective labor</p>
                <p>Community builds together — barn-raising energy, skill sharing, learning by doing</p>
              </div>
              <div className="space-y-1">
                <p className="text-stone-400 font-medium">Shared infrastructure</p>
                <p>One large kitchen serves 50 people better than 20 small ones. Shared tools, vehicles, energy systems</p>
              </div>
              <div className="space-y-1">
                <p className="text-stone-400 font-medium">Land trust models</p>
                <p>Community land trusts, cooperative ownership, reducing per-person land cost by 50-80%</p>
              </div>
            </div>
          </div>

          {/* Timeline */}
          <div className="max-w-2xl mx-auto space-y-4">
            <h3 className="text-lg font-light text-stone-300 text-center">
              Timeline to reality
            </h3>
            <div className="space-y-3">
              {[
                { phase: "Now", time: "Month 0", desc: "Gather resonant people. Build the field online. Share the vision." },
                { phase: "Seed", time: "Months 1-6", desc: "Core group of 10-20 forms. Legal structure. Land search begins. Fundraising." },
                { phase: "Root", time: "Months 6-12", desc: "Land secured. First structures. Garden beds planted. Infrastructure started." },
                { phase: "Sprout", time: "Months 12-18", desc: "First residents move in. Common spaces usable. Food production begins." },
                { phase: "Bloom", time: "Months 18-36", desc: "Community reaches 50+ people. All systems operational. Visitors welcomed." },
                { phase: "Fruit", time: "Year 3+", desc: "Community thriving. Network connections to other communities. Replication begins." },
              ].map((step) => (
                <div key={step.phase} className="flex gap-4 items-start">
                  <div className="flex-shrink-0 w-20 text-right">
                    <span className="text-sm font-medium text-amber-300/60">{step.phase}</span>
                  </div>
                  <div className="flex-shrink-0 w-px h-full bg-stone-800/30 relative">
                    <div className="w-2 h-2 rounded-full bg-amber-500/40 absolute -left-[3px] top-1.5" />
                  </div>
                  <div className="flex-1 pb-4">
                    <p className="text-sm text-stone-400 font-medium">{step.time}</p>
                    <p className="text-sm text-stone-500">{step.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="text-center space-y-6 py-8 border-t border-stone-800/20 no-print">
          <p className="text-stone-500">
            Can you feel it forming?
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/vision/join#register"
              className="px-8 py-3 rounded-xl bg-gradient-to-r from-amber-500/10 via-teal-500/10 to-violet-500/10 border border-amber-500/20 text-amber-300/90 hover:from-amber-500/20 hover:via-teal-500/20 hover:to-violet-500/20 transition-all font-medium"
            >
              Join the field
            </Link>
            <Link
              href="/vision"
              className="px-8 py-3 rounded-xl bg-stone-900/40 border border-stone-800/40 text-stone-400 hover:text-stone-300 hover:border-stone-700/40 transition-all font-medium"
            >
              Explore the vision
            </Link>
          </div>
        </section>
      </main>
    </>
  );
}

function PosterCard({ poster }: { poster: Poster }) {
  const imageUrl = pollinationsUrl(poster.prompt, 42, 1024, 768);

  return (
    <div className="poster-card rounded-2xl overflow-hidden border border-stone-800/30 bg-stone-900/20 group">
      <div className="relative aspect-[4/3] overflow-hidden">
        <Image
          src={imageUrl}
          alt={poster.title}
          fill
          className="object-cover group-hover:scale-105 transition-transform duration-700"
          sizes="(max-width: 768px) 100vw, 50vw"
          unoptimized
        />
        <div className="absolute inset-0 bg-gradient-to-t from-stone-950/80 via-transparent to-transparent" />
        <div className="absolute bottom-0 left-0 right-0 p-6 space-y-1">
          <h3 className="text-xl font-light text-white">{poster.title}</h3>
          <p className="text-sm text-stone-300/80">{poster.subtitle}</p>
        </div>
        <div className="absolute top-3 right-3 flex gap-2">
          <span className="text-xs px-2 py-0.5 rounded-full bg-stone-950/60 text-stone-300 border border-stone-700/30">
            {poster.scale}
          </span>
          <span className="text-xs px-2 py-0.5 rounded-full bg-stone-950/60 text-stone-300 border border-stone-700/30">
            {poster.location}
          </span>
        </div>
      </div>
      <div className="p-5">
        <p className="text-sm text-stone-500 leading-relaxed">{poster.description}</p>
      </div>
    </div>
  );
}
