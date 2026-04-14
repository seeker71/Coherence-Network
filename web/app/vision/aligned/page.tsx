import type { Metadata } from "next";
import Link from "next/link";
import { getApiBase } from "@/lib/api";

export const metadata: Metadata = {
  title: "Aligned Communities — The Living Collective",
  description: "Communities and practices already living pieces of this vision. We celebrate them, learn from them, and invite connection.",
};

export const dynamic = "force-dynamic";

type DBItem = { id: string; name: string; description?: string; [key: string]: unknown };

async function fetchItems(type: string): Promise<DBItem[]> {
  const base = getApiBase();
  try {
    const res = await fetch(`${base}/api/concepts/${type}?limit=50`, { next: { revalidate: 60 } });
    if (!res.ok) return [];
    const data = await res.json();
    return data?.items || [];
  } catch { return []; }
}

const COMMUNITIES = [
  {
    name: "Tamera", slug: "tamera",
    location: "Alentejo, Portugal",
    size: "~250 people",
    url: "https://www.tamera.org/",
    resonates: "Building a Healing Biotope. Solar village, water retention landscapes, transparent communication through the Forum process. Trust as the foundation.",
    learn: "Water retention landscape design, solar technology at community scale, the Forum process for sensing circles",
    concepts: ["lc-sensing", "lc-v-harmonizing", "lc-energy", "lc-land"],
    conceptLabels: ["Sensing", "Harmonizing", "Energy", "Land"],
  },
  {
    name: "Auroville", slug: "auroville",
    location: "Tamil Nadu, India",
    size: "~3,000 people, 60+ nations",
    url: "https://auroville.org/",
    resonates: "No private property. No religion. Self-governance. 50+ years of consciousness-based living. 2 million trees planted. Surplus renewable energy. Human unity as practice.",
    learn: "Governance without government at scale, reforestation, compressed earth building, moneyless economics",
    concepts: ["lc-pulse", "lc-circulation", "lc-v-freedom-expression", "lc-land"],
    conceptLabels: ["The Pulse", "Circulation", "Freedom", "Land"],
  },
  {
    name: "Findhorn Ecovillage", slug: "findhorn",
    location: "Moray, Scotland",
    size: "~350 people, 40+ nationalities",
    url: "https://www.ecovillagefindhorn.com/",
    resonates: "Started from listening to the land. Lowest ecological footprint measured in the industrialized world. Spirituality without doctrine. Universal Hall — community-built for meditation and performance.",
    learn: "Experience Week immersion, Living Machine wastewater, turf-roofed buildings, welcoming 10,000+ visitors/year",
    concepts: ["lc-land", "lc-v-living-spaces", "lc-v-harmonizing", "lc-attunement-joining"],
    conceptLabels: ["Land", "Living Spaces", "Harmonizing", "Joining"],
  },
  {
    name: "Damanhur", slug: "damanhur",
    location: "Piedmont, Italy",
    size: "~600 people in 30 communities",
    url: "https://damanhur.org/",
    resonates: "Federation of 30 nucleos, each with a focus. Their own currency. Underground Temples of Humankind — carved by hand over decades. Art and sacred expression as the foundation of community.",
    learn: "Federation structure for multiple nodes, community currency, integrating art/spirituality as foundation",
    concepts: ["lc-network", "lc-v-ceremony", "lc-beauty", "lc-circulation"],
    conceptLabels: ["The Network", "Ceremony", "Beauty", "Circulation"],
  },
  {
    name: "Gaviotas", slug: "gaviotas",
    location: "Los Llanos, Colombia",
    size: "~200 people",
    url: "https://en.wikipedia.org/wiki/Gaviotas",
    resonates: "Built a community on 'impossible' land. Regenerated 8 million trees on barren savanna. Invented solar and wind technology for tropical conditions. Proof that care can regenerate anything.",
    learn: "Land regeneration on degraded soil, appropriate technology invention, open-source design",
    concepts: ["lc-land", "lc-vitality", "lc-instruments", "lc-v-shelter-organism"],
    conceptLabels: ["Land", "Vitality", "Instruments", "Shelter"],
  },
  {
    name: "Earthship Biotecture", slug: "earthship",
    location: "Taos, New Mexico, USA",
    size: "~130 residents",
    url: "https://earthship.com/",
    resonates: "Buildings that ARE the infrastructure — generating energy, harvesting water, growing food, treating waste, maintaining temperature. 50 years of perfecting off-grid living from recycled materials.",
    learn: "Passive solar design, rainwater harvesting, greywater recycling, food-producing buildings, academy model",
    concepts: ["lc-v-shelter-organism", "lc-v-living-spaces", "lc-energy", "lc-nourishment"],
    conceptLabels: ["Shelter as Skin", "Living Spaces", "Energy", "Nourishment"],
  },
];

const NETWORKS = [
  {
    name: "Global Ecovillage Network (GEN)",
    url: "https://ecovillage.org/",
    scope: "6,000+ communities in 114 countries",
    resonates: "The existing mycorrhizal network. Ecovillage Design Education in 55 countries. New digital platform launching 2026.",
  },
  {
    name: "Transition Towns",
    url: "https://transitionnetwork.org/",
    scope: "1,000+ initiatives in 50+ countries",
    resonates: "Community-led responses to climate and economy. Local food, local energy, local resilience. The civic-scale complement to intentional communities.",
  },
];

const PRACTICES = [
  { name: "Vipassana Meditation", url: "https://www.dhamma.org/", what: "10-day silent retreats. Volunteer-run, free. 350+ centers. The model for sustained-by-generosity service.", concepts: ["lc-stillness", "lc-v-harmonizing"] },
  { name: "Permaculture Design", url: "https://www.permaculturenews.org/", what: "The design science for food forests, water systems, and regenerative land stewardship. Three ethics: earth care, people care, fair share.", concepts: ["lc-land", "lc-v-food-practice", "lc-nourishment"] },
  { name: "Natural Building", url: "https://www.cobcottage.com/", what: "Cob, rammed earth, straw bale, bamboo, SuperAdobe. Beautiful, adapted, local. The building methods for living structures.", concepts: ["lc-v-shelter-organism", "lc-v-living-spaces", "lc-space"] },
  { name: "Sound Healing", url: "https://www.taize.fr/", what: "Singing bowls, kirtan, overtone singing, Taizé chanting. Sound as the primary attunement technology.", concepts: ["lc-transmission", "lc-v-harmonizing", "lc-ceremony"] },
];

export default async function AlignedPage() {
  // Fetch from DB — fall back to hardcoded data if empty
  const [dbCommunities, dbNetworks, dbPractices] = await Promise.all([
    fetchItems("communities"),
    fetchItems("networks"),
    fetchItems("practices"),
  ]);

  // Use DB data if available, otherwise hardcoded
  const useCommunities = dbCommunities.length > 0 ? dbCommunities : null;
  const useNetworks = dbNetworks.length > 0 ? dbNetworks : null;
  const usePractices = dbPractices.length > 0 ? dbPractices : null;
  return (
    <main className="max-w-5xl mx-auto px-6 py-16 space-y-24">
      {/* Hero */}
      <section className="text-center space-y-6 py-12">
        <p className="text-amber-400/60 text-sm tracking-[0.3em] uppercase">Already living it</p>
        <h1 className="text-4xl md:text-6xl font-extralight tracking-tight text-white">
          Aligned Communities
        </h1>
        <p className="text-lg text-stone-400 font-light max-w-2xl mx-auto">
          Across the planet, communities are already living pieces of this vision.
          We celebrate them, learn from them, and invite connection.
          The field extends beyond any single community.
        </p>
      </section>

      {/* Communities */}
      <section className="space-y-8">
        {COMMUNITIES.map((c) => (
          <div key={c.name} className="rounded-2xl border border-stone-800/30 bg-stone-900/20 overflow-hidden">
            <div className="p-8 space-y-4">
              <div className="flex flex-wrap items-baseline gap-3">
                <Link href={`/vision/aligned/${c.slug}`}
                  className="text-2xl font-light text-amber-300/80 hover:text-amber-300 transition-colors">
                  {c.name} →
                </Link>
                <span className="text-sm text-stone-600">{c.location} · {c.size}</span>
              </div>
              <p className="text-stone-300 leading-relaxed">{c.resonates}</p>
              <div className="pt-2">
                <span className="text-xs text-stone-500 uppercase tracking-wider">What we can learn:</span>
                <p className="text-sm text-stone-400 mt-1">{c.learn}</p>
              </div>
              <div className="flex flex-wrap gap-2 pt-2">
                {c.concepts.map((conceptId, i) => (
                  <Link key={conceptId} href={`/vision/${conceptId}`}
                    className="text-xs px-3 py-1 rounded-full border border-stone-700/40 text-stone-400 hover:text-teal-300/80 hover:border-teal-500/30 transition-colors">
                    {c.conceptLabels[i]}
                  </Link>
                ))}
              </div>
            </div>
          </div>
        ))}
      </section>

      {/* Networks */}
      <section className="space-y-8">
        <h2 className="text-2xl font-extralight text-stone-300">Networks</h2>
        <div className="grid md:grid-cols-2 gap-6">
          {NETWORKS.map((n) => (
            <div key={n.name} className="p-6 rounded-2xl border border-stone-800/30 bg-stone-900/20 space-y-3">
              <a href={n.url} target="_blank" rel="noopener noreferrer"
                className="text-lg font-light text-teal-300/80 hover:text-teal-300 transition-colors">
                {n.name} ↗
              </a>
              <p className="text-xs text-stone-600">{n.scope}</p>
              <p className="text-sm text-stone-400 leading-relaxed">{n.resonates}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Practices */}
      <section className="space-y-8">
        <h2 className="text-2xl font-extralight text-stone-300">Practices & Traditions</h2>
        <div className="grid md:grid-cols-2 gap-6">
          {PRACTICES.map((p) => (
            <div key={p.name} className="p-6 rounded-2xl border border-stone-800/30 bg-stone-900/20 space-y-3">
              <a href={p.url} target="_blank" rel="noopener noreferrer"
                className="text-lg font-light text-violet-300/80 hover:text-violet-300 transition-colors">
                {p.name} ↗
              </a>
              <p className="text-sm text-stone-400 leading-relaxed">{p.what}</p>
              <div className="flex flex-wrap gap-2">
                {p.concepts.map((cid) => (
                  <Link key={cid} href={`/vision/${cid}`}
                    className="text-xs px-2.5 py-0.5 rounded-full border border-stone-700/40 text-stone-500 hover:text-violet-300/80 hover:border-violet-500/30 transition-colors">
                    {cid.replace("lc-", "").replace("lc-v-", "").replace(/-/g, " ")}
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* How we collaborate */}
      <section className="text-center space-y-6 py-12">
        <h2 className="text-2xl font-extralight text-stone-400">How We Collaborate</h2>
        <p className="text-stone-500 max-w-2xl mx-auto leading-relaxed">
          The Living Collective is one more node in the same network.
          Any community that resonates can connect — no application, no membership fee.
          Just resonance. The Coherence Network maps the connections and facilitates
          the flow of cells, seeds, knowledge, and celebration between nodes.
        </p>
        <div className="flex flex-col sm:flex-row gap-4 justify-center pt-6">
          <Link href="/vision" className="px-8 py-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300/90 hover:bg-amber-500/20 transition-all font-medium">
            Explore the vision
          </Link>
          <Link href="/vision/join" className="px-8 py-3 rounded-xl bg-teal-500/10 border border-teal-500/20 text-teal-300/90 hover:bg-teal-500/20 transition-all font-medium">
            Join the network
          </Link>
        </div>
      </section>
    </main>
  );
}
