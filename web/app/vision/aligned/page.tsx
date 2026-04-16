import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { getApiBase } from "@/lib/api";

export const metadata: Metadata = {
  title: "Aligned Communities — The Living Collective",
  description:
    "Communities, host spaces, and gatherings already carrying pieces of the field. Learn from them, visit them, and let the signal travel.",
};

export const dynamic = "force-dynamic";

type DBItem = { id: string; name: string; description?: string; [key: string]: unknown };

type CuratedCommunity = {
  name: string;
  slug: string;
  location: string;
  size: string;
  image: string;
  url: string;
  resonates: string;
  learn: string;
  concepts: string[];
  conceptLabels: string[];
};

type HostSpace = {
  title: string;
  image: string;
  context: string;
  energy: string;
  body: string;
  firstMove: string;
  note: string;
};

type Gathering = {
  title: string;
  image: string;
  body: string;
  energy: string;
};

type Practice = {
  name: string;
  image: string;
  url: string;
  what: string;
  concepts: string[];
};

async function fetchItems(type: string): Promise<DBItem[]> {
  const base = getApiBase();
  try {
    const res = await fetch(`${base}/api/concepts/${type}?limit=50`, { next: { revalidate: 60 } });
    if (!res.ok) return [];
    const data = await res.json();
    return data?.items || [];
  } catch {
    return [];
  }
}

const COMMUNITIES: CuratedCommunity[] = [
  {
    name: "Tamera",
    slug: "tamera",
    location: "Alentejo, Portugal",
    size: "~250 people",
    image: "/visuals/community-tamera.png",
    url: "https://www.tamera.org/",
    resonates:
      "Building a healing biotope through water retention, trust practices, and community-scale solar infrastructure.",
    learn:
      "Water retention landscapes, solar village systems, transparent communication, and relationship as field practice.",
    concepts: ["lc-sensing", "lc-v-harmonizing", "lc-energy", "lc-land"],
    conceptLabels: ["Sensing", "Harmonizing", "Energy", "Land"],
  },
  {
    name: "Auroville",
    slug: "auroville",
    location: "Tamil Nadu, India",
    size: "~3,000 people, 60+ nations",
    image: "/visuals/community-auroville.png",
    url: "https://auroville.org/",
    resonates:
      "A long experiment in human unity with reforestation, earth building, renewable energy, and forms of stewardship beyond private property.",
    learn:
      "Governance without rigid government, land regeneration, compressed earth building, and community at civilizational scale.",
    concepts: ["lc-pulse", "lc-circulation", "lc-v-freedom-expression", "lc-land"],
    conceptLabels: ["The Pulse", "Circulation", "Freedom", "Land"],
  },
  {
    name: "Findhorn Ecovillage",
    slug: "findhorn",
    location: "Moray, Scotland",
    size: "~350 people",
    image: "/visuals/community-findhorn.png",
    url: "https://www.ecovillagefindhorn.com/",
    resonates:
      "Listening to land, low ecological footprint, spiritual practice without doctrine, and community-built spaces for meditation and performance.",
    learn:
      "Immersion as education, living wastewater systems, community-built halls, and hosting thousands of visitors without losing atmosphere.",
    concepts: ["lc-land", "lc-v-living-spaces", "lc-v-harmonizing", "lc-attunement-joining"],
    conceptLabels: ["Land", "Living Spaces", "Harmonizing", "Joining"],
  },
  {
    name: "Damanhur",
    slug: "damanhur",
    location: "Piedmont, Italy",
    size: "~600 people in 30 communities",
    image: "/visuals/community-damanhur.png",
    url: "https://damanhur.org/",
    resonates:
      "A federation of communities where sacred architecture, local currency, and artistic expression shape daily life.",
    learn:
      "Federated structure, community currency, and art as a primary civic organ rather than decoration.",
    concepts: ["lc-network", "lc-v-ceremony", "lc-beauty", "lc-circulation"],
    conceptLabels: ["The Network", "Ceremony", "Beauty", "Circulation"],
  },
  {
    name: "Gaviotas",
    slug: "gaviotas",
    location: "Los Llanos, Colombia",
    size: "~200 people",
    image: "/visuals/community-gaviotas.png",
    url: "https://en.wikipedia.org/wiki/Gaviotas",
    resonates:
      "A community that regenerated what looked impossible through open invention, care for land, and practical beauty.",
    learn:
      "Land restoration on degraded soil, appropriate technology, and the civic force of persistent regenerative practice.",
    concepts: ["lc-land", "lc-vitality", "lc-instruments", "lc-v-shelter-organism"],
    conceptLabels: ["Land", "Vitality", "Instruments", "Shelter"],
  },
  {
    name: "Earthship Biotecture",
    slug: "earthship",
    location: "Taos, New Mexico, USA",
    size: "~130 residents",
    image: "/visuals/community-earthship.png",
    url: "https://earthship.com/",
    resonates:
      "Buildings that gather water, regulate climate, grow food, and generate energy as part of their own body.",
    learn:
      "Passive solar design, water harvesting, greywater systems, food-producing buildings, and practical off-grid education.",
    concepts: ["lc-v-shelter-organism", "lc-v-living-spaces", "lc-energy", "lc-nourishment"],
    conceptLabels: ["Shelter as Skin", "Living Spaces", "Energy", "Nourishment"],
  },
  {
    name: "New Earth MicroNation",
    slug: "new-earth",
    location: "Africa",
    size: "Founding phase",
    image: "/visuals/nature-architecture-blend.png",
    url: "https://newearthhorizon.com/",
    resonates:
      "A sovereignty-first experiment tying jurisdiction, technology, and fellowship to a different civilizational operating system.",
    learn:
      "Alternative exchange, sovereignty structures, free-energy imagination, and beauty as a design premise.",
    concepts: ["lc-v-freedom-expression", "lc-energy", "lc-circulation", "lc-beauty"],
    conceptLabels: ["Freedom", "Energy", "Circulation", "Beauty"],
  },
];

const HOST_SPACES: HostSpace[] = [
  {
    title: "City apartment band",
    image: "/visuals/transform-apartment.png",
    context: "city",
    energy: "light-touch",
    body:
      "A residential stack becomes a quiet band of cells with shared meals, child care, rooftop gardens, listening rooms, and a commons strong enough to change how the whole building feels.",
    firstMove:
      "Open one floor, corridor, or rooftop to shared nourishment, a guest room, and a stillness space before changing anything structural.",
    note: "The shell stays. The social metabolism changes first.",
  },
  {
    title: "Urban block host",
    image: "/visuals/transform-neighborhood.png",
    context: "urban",
    energy: "light-touch",
    body:
      "A storefront, foyer, hall, or studio shifts from throughput into repair, borrowing, nourishment, and visible welcome. One block starts to breathe differently.",
    firstMove:
      "Retune one underused front-facing room into a provision house, listening circle, or repair table that anyone nearby can understand at a glance.",
    note: "The fastest shifts often happen on the ground floor.",
  },
  {
    title: "Suburban commons lane",
    image: "/visuals/generated/lc-attuned-spaces-1.jpg",
    context: "suburban",
    energy: "light-touch",
    body:
      "A porch line, cul-de-sac, garage bay, or side-yard seam becomes a connected lane of meals, tools, child support, and slow social rhythm without waiting for a full redevelopment cycle.",
    firstMove:
      "Open one shared table, one visible pantry shelf, and one garage workshop so neighboring homes start reading as one field.",
    note: "Connection can arrive before new architecture does.",
  },
  {
    title: "Rural anchor house",
    image: "/visuals/community-earthship.png",
    context: "rural edge",
    energy: "medium-touch",
    body:
      "One existing home or stewarded structure becomes the place where tools, meals, bathing, greenhouse warmth, and visiting cells start to gather.",
    firstMove:
      "Let one house become the commons before new buildings appear: shared kitchen, shared bath, shared workshop, shared welcome.",
    note: "Connection grows faster than construction.",
  },
  {
    title: "Land-rooted cluster",
    image: "/visuals/community-findhorn.png",
    context: "rural",
    energy: "medium-touch",
    body:
      "Paths, gardens, small structures, and a shared hall start reading as one organism. The land no longer feels divided into isolated holdings but into living gradients.",
    firstMove:
      "Connect paths, shared food, bathing, and gathering first so the land feels one body before any big buildout begins.",
    note: "Permeable thresholds replace decorative separation.",
  },
];

const GATHERINGS: Gathering[] = [
  {
    title: "Listening supper",
    image: "/visuals/life-shared-meal.png",
    body:
      "A long table lets strangers arrive as bodies rather than profiles. Presence, nourishment, and direct conversation make a field legible faster than explanation.",
    energy: "Presence becomes belonging.",
  },
  {
    title: "Traveling workshop",
    image: "/visuals/life-creation-workshop.png",
    body:
      "Builders, musicians, healers, and facilitators move between nodes carrying know-how, rhythm, and fresh pattern memory into each new host.",
    energy: "Creative energy becomes transmissible.",
  },
  {
    title: "Seasonal convergence",
    image: "/visuals/network-midsummer-gathering.png",
    body:
      "Periodic gatherings let communities compare practices, share beauty, meet new cells, and tune the larger network without central control.",
    energy: "Wisdom becomes circulation.",
  },
];

const PRACTICES: Practice[] = [
  {
    name: "Vipassana Meditation",
    image: "/visuals/space-stillness-sanctuary.png",
    url: "https://www.dhamma.org/",
    what:
      "A volunteer-run, generosity-based container for stillness. Useful when a field needs strong attention without performance.",
    concepts: ["lc-stillness", "lc-v-harmonizing"],
  },
  {
    name: "Permaculture Design",
    image: "/visuals/life-garden-planting.png",
    url: "https://www.permaculturenews.org/",
    what:
      "A design language for food, water, land repair, and nested systems. Useful anywhere a place wants to feed more life than it currently does.",
    concepts: ["lc-land", "lc-v-food-practice", "lc-nourishment"],
  },
  {
    name: "Natural Building",
    image: "/visuals/space-creation-arc-overview.png",
    url: "https://www.cobcottage.com/",
    what:
      "Cob, rammed earth, straw bale, bamboo, and other methods that let shelter act more like body and climate partner than sealed product.",
    concepts: ["lc-v-shelter-organism", "lc-v-living-spaces", "lc-space"],
  },
  {
    name: "Sound Healing",
    image: "/visuals/practice-sound-healing.png",
    url: "https://www.taize.fr/",
    what:
      "Chant, bowls, overtone work, kirtan, and shared sound as a practical attunement tool for groups, rooms, and transitions.",
    concepts: ["lc-transmission", "lc-v-harmonizing", "lc-ceremony"],
  },
];

const NETWORKS = [
  {
    name: "New Earth Horizon",
    url: "https://newearthhorizon.com/",
    scope: "Global — territory, exchange, initiatives",
    resonates:
      "A sovereignty-oriented network linking jurisdiction, technology, and fellowship as mutually reinforcing conditions.",
  },
  {
    name: "Global Ecovillage Network",
    url: "https://ecovillage.org/",
    scope: "6,000+ communities in 114 countries",
    resonates:
      "An existing mycorrhizal layer for communities sharing methods, people, and regenerative education across continents.",
  },
  {
    name: "Transition Towns",
    url: "https://transitionnetwork.org/",
    scope: "1,000+ initiatives in 50+ countries",
    resonates:
      "A civic-scale network for local food, local energy, and local resilience where neighborhoods become practical living laboratories.",
  },
];

export default async function AlignedPage() {
  const [dbCommunities, dbNetworks, dbPractices] = await Promise.all([
    fetchItems("communities"),
    fetchItems("networks"),
    fetchItems("practices"),
  ]);

  const counts = {
    communities: dbCommunities.length || COMMUNITIES.length,
    networks: dbNetworks.length || NETWORKS.length,
    practices: dbPractices.length || PRACTICES.length,
  };

  return (
    <main className="max-w-6xl mx-auto px-6 py-16 space-y-24">
      <section className="relative overflow-hidden rounded-[2rem] border border-stone-800/30 bg-stone-950/60 px-6 py-16 md:px-12 md:py-20">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(45,212,191,0.14),_transparent_38%),radial-gradient(circle_at_bottom_left,_rgba(251,191,36,0.1),_transparent_32%),radial-gradient(circle_at_bottom_right,_rgba(196,181,253,0.12),_transparent_30%)]" />
        <div className="relative grid gap-10 lg:grid-cols-[1.2fr_0.8fr] lg:items-end">
          <div className="space-y-6">
            <p className="text-sm uppercase tracking-[0.3em] text-amber-400/70">Already living it</p>
            <h1 className="text-4xl font-extralight tracking-tight text-white md:text-6xl">
              The field already has{" "}
              <span className="bg-gradient-to-r from-amber-300 via-teal-300 to-violet-300 bg-clip-text text-transparent">
                real hosts
              </span>
            </h1>
            <p className="max-w-3xl text-lg font-light leading-relaxed text-stone-300">
              Some are full communities on land. Some are city apartments, neighborhood blocks,
              suburban lanes, or civic rooms waiting for a new social metabolism. Some are gatherings
              that move between places and let the signal travel. All of them show that new life
              does not need a blank slate to begin.
            </p>
            <div className="flex flex-wrap gap-3 pt-2 text-sm">
              <Link
                href="#communities"
                className="rounded-full border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-amber-200 transition-colors hover:border-amber-400/40 hover:text-amber-100"
              >
                Communities on the land
              </Link>
              <Link
                href="#hosts"
                className="rounded-full border border-teal-500/30 bg-teal-500/10 px-4 py-2 text-teal-200 transition-colors hover:border-teal-400/40 hover:text-teal-100"
              >
                Connected host spaces
              </Link>
              <Link
                href="#gatherings"
                className="rounded-full border border-violet-500/30 bg-violet-500/10 px-4 py-2 text-violet-200 transition-colors hover:border-violet-400/40 hover:text-violet-100"
              >
                Gatherings and experiences
              </Link>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-1">
            {[
              { label: "communities sensed", value: counts.communities, tone: "text-amber-300/90" },
              { label: "network lines", value: counts.networks, tone: "text-teal-300/90" },
              { label: "practice streams", value: counts.practices, tone: "text-violet-300/90" },
            ].map((stat) => (
              <div
                key={stat.label}
                className="rounded-2xl border border-stone-800/40 bg-stone-900/30 p-5 text-center"
              >
                <div className={`text-3xl font-extralight ${stat.tone}`}>{stat.value}</div>
                <div className="mt-1 text-xs uppercase tracking-[0.24em] text-stone-500">
                  {stat.label}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="grid gap-5 lg:grid-cols-3">
        {[
          {
            title: "Rooted communities",
            body:
              "Places that already live with shared land, shared rhythm, and enough continuity to hold meals, learning, conflict, building, and ceremony inside one organism.",
            tone:
              "from-amber-500/12 via-amber-500/5 to-stone-900/0 border-amber-500/20 text-amber-200",
          },
            {
              title: "Existing host spaces",
              body:
              "Apartments, studios, storefronts, rooftops, halls, and rural anchors that can be retuned now so cells can gather through presence, creativity, wisdom, and care.",
              tone:
                "from-teal-500/12 via-teal-500/5 to-stone-900/0 border-teal-500/20 text-teal-200",
            },
          {
            title: "Traveling experiences",
            body:
              "Meals, workshops, circles, residencies, and seasonal convergences that let the field travel lightly and find the places ready to host it next.",
            tone:
              "from-violet-500/12 via-violet-500/5 to-stone-900/0 border-violet-500/20 text-violet-200",
          },
        ].map((item) => (
          <div
            key={item.title}
            className={`rounded-[1.5rem] border bg-gradient-to-br p-6 ${item.tone}`}
          >
            <h2 className="text-xl font-light text-white">{item.title}</h2>
            <p className="mt-3 text-sm leading-relaxed text-stone-300">{item.body}</p>
          </div>
        ))}
      </section>

      <section className="space-y-8">
        <div className="space-y-3 text-center">
          <p className="text-sm uppercase tracking-[0.28em] text-stone-500">Three visible pathways</p>
          <h2 className="text-3xl font-extralight text-stone-200 md:text-4xl">
            The field lands through place, host, and movement
          </h2>
          <p className="mx-auto max-w-3xl text-stone-400">
            A community can anchor it. A city room can host it. A suburban lane can soften into
            commons. A rural cluster can deepen it. A gathering can transmit it. The same values
            move through all three forms.
          </p>
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          {[
            {
              title: "A place that already knows the rhythm",
              image: "/visuals/community-findhorn.png",
              body:
                "Land-based communities show what it looks like when meals, stewardship, building, and ceremony share one pulse long enough to become culture.",
              link: "/vision/aligned/findhorn",
              cta: "See a rooted example",
            },
            {
              title: "A city shell becoming a living host",
              image: "/visuals/transform-neighborhood.png",
              body:
                "An existing block or building can become a threshold where repair, nourishment, listening, and exchange feel more natural than consumption.",
              link: "/vision/realize",
              cta: "See host-space shifts",
            },
            {
              title: "A gathering that helps cells find each other",
              image: "/visuals/network-midsummer-gathering.png",
              body:
                "Circles, workshops, and seasonal convergences let the field gather before it has permanent walls, and keep it alive between nodes after it does.",
              link: "/vision/lived",
              cta: "Feel the experience",
            },
          ].map((item) => (
            <Link
              key={item.title}
              href={item.link}
              className="group overflow-hidden rounded-[1.5rem] border border-stone-800/30 bg-stone-900/20"
            >
              <div className="relative aspect-[5/4] overflow-hidden">
                <Image
                  src={item.image}
                  alt={item.title}
                  fill
                  className="object-cover transition-transform duration-700 group-hover:scale-105"
                  sizes="(max-width: 1024px) 100vw, 33vw"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-stone-950 via-stone-950/35 to-transparent" />
              </div>
              <div className="space-y-3 p-6">
                <h3 className="text-xl font-light text-white">{item.title}</h3>
                <p className="text-sm leading-relaxed text-stone-400">{item.body}</p>
                <div className="text-sm text-amber-300/80 transition-colors group-hover:text-amber-200">
                  {item.cta} →
                </div>
              </div>
            </Link>
          ))}
        </div>
      </section>

      <section id="communities" className="space-y-8 scroll-mt-24">
        <div className="space-y-3">
          <p className="text-sm uppercase tracking-[0.28em] text-amber-400/60">Communities already carrying the signal</p>
          <h2 className="text-3xl font-extralight text-stone-200">Rooted places we can learn from</h2>
          <p className="max-w-3xl text-stone-400">
            These are not templates to copy. They are living proofs that different parts of the
            field can already be held in durable form.
          </p>
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          {COMMUNITIES.map((community) => (
            <article
              key={community.name}
              className="overflow-hidden rounded-[1.5rem] border border-stone-800/30 bg-stone-900/20"
            >
              <div className="relative aspect-[16/9] overflow-hidden">
                <Image
                  src={community.image}
                  alt={community.name}
                  fill
                  className="object-cover"
                  sizes="(max-width: 1024px) 100vw, 50vw"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-stone-950 via-stone-950/15 to-transparent" />
              </div>
              <div className="space-y-4 p-6">
                <div className="flex flex-wrap items-baseline gap-3">
                  <Link
                    href={`/vision/aligned/${community.slug}`}
                    className="text-2xl font-light text-amber-300/90 transition-colors hover:text-amber-200"
                  >
                    {community.name} →
                  </Link>
                  <span className="text-sm text-stone-600">
                    {community.location} · {community.size}
                  </span>
                </div>
                <p className="leading-relaxed text-stone-300">{community.resonates}</p>
                <div className="space-y-1">
                  <span className="text-xs uppercase tracking-[0.22em] text-stone-500">
                    What it teaches
                  </span>
                  <p className="text-sm leading-relaxed text-stone-400">{community.learn}</p>
                </div>
                <div className="flex flex-wrap gap-2 pt-1">
                  {community.concepts.map((conceptId, index) => (
                    <Link
                      key={conceptId}
                      href={`/vision/${conceptId}`}
                      className="rounded-full border border-stone-700/40 px-3 py-1 text-xs text-stone-400 transition-colors hover:border-teal-500/30 hover:text-teal-300/90"
                    >
                      {community.conceptLabels[index]}
                    </Link>
                  ))}
                </div>
                <a
                  href={community.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex text-sm text-stone-500 transition-colors hover:text-stone-300"
                >
                  Visit source ↗
                </a>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section id="hosts" className="space-y-8 scroll-mt-24">
        <div className="space-y-3">
          <p className="text-sm uppercase tracking-[0.28em] text-teal-400/60">Existing spaces can host now</p>
          <h2 className="text-3xl font-extralight text-stone-200">Not every aligned node needs new land or hard borders</h2>
          <p className="max-w-3xl text-stone-400">
            A healthy organism uses the shells it already has. Existing buildings can attract cells
            through hospitality, craft, care, sound, wisdom, and shared rhythm before they ever
            become full communities. The fastest shifts usually come from shared kitchens, common
            rooms, and porous thresholds, not from expensive new construction.
          </p>
        </div>

        <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
          {HOST_SPACES.map((space) => (
            <article
              key={space.title}
              className="overflow-hidden rounded-[1.5rem] border border-stone-800/30 bg-stone-900/20"
            >
              <div className="relative aspect-[4/5] overflow-hidden">
                <Image
                  src={space.image}
                  alt={space.title}
                  fill
                  className="object-cover"
                  sizes="(max-width: 1280px) 50vw, 25vw"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-stone-950 via-stone-950/20 to-transparent" />
              </div>
              <div className="space-y-3 p-5">
                <div className="flex flex-wrap items-center gap-2 text-[11px] uppercase tracking-[0.22em] text-stone-500">
                  <span>{space.context}</span>
                  <span className="text-stone-700">•</span>
                  <span>{space.energy}</span>
                </div>
                <h3 className="text-lg font-light text-teal-200">{space.title}</h3>
                <p className="text-sm leading-relaxed text-stone-400">{space.body}</p>
                <div className="rounded-xl border border-stone-800/30 bg-stone-950/30 p-3">
                  <p className="text-[11px] uppercase tracking-[0.22em] text-stone-500">First move</p>
                  <p className="mt-1 text-xs leading-relaxed text-stone-400">{space.firstMove}</p>
                </div>
                <p className="text-xs uppercase tracking-[0.24em] text-stone-500">{space.note}</p>
              </div>
            </article>
          ))}
        </div>

        <div className="rounded-[1.5rem] border border-teal-500/20 bg-teal-500/5 p-6">
          <p className="text-stone-300 leading-relaxed">
            The question is no longer only <span className="text-teal-200">where can we build?</span>{" "}
            It is also <span className="text-teal-200">what spaces are already ready to become more alive?</span>
            {" "}That is how neighborhoods start to behave like fields instead of addresses.
          </p>
        </div>
      </section>

      <section id="gatherings" className="space-y-8 scroll-mt-24">
        <div className="space-y-3">
          <p className="text-sm uppercase tracking-[0.28em] text-violet-400/60">Gatherings and experiences</p>
          <h2 className="text-3xl font-extralight text-stone-200">How the field travels before it settles</h2>
          <p className="max-w-3xl text-stone-400">
            Some cells join through land. Others join through an evening, a workshop, a circle, or a
            season. Experience is often the first proof that a deeper form of community is possible.
          </p>
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          {GATHERINGS.map((gathering) => (
            <article
              key={gathering.title}
              className="overflow-hidden rounded-[1.5rem] border border-stone-800/30 bg-stone-900/20"
            >
              <div className="relative aspect-[5/4] overflow-hidden">
                <Image
                  src={gathering.image}
                  alt={gathering.title}
                  fill
                  className="object-cover"
                  sizes="(max-width: 1024px) 100vw, 33vw"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-stone-950 via-stone-950/20 to-transparent" />
              </div>
              <div className="space-y-3 p-6">
                <h3 className="text-xl font-light text-violet-200">{gathering.title}</h3>
                <p className="text-sm leading-relaxed text-stone-400">{gathering.body}</p>
                <p className="text-xs uppercase tracking-[0.24em] text-stone-500">{gathering.energy}</p>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="rounded-[1.5rem] border border-stone-800/30 bg-stone-900/20 p-6">
          <h2 className="text-2xl font-extralight text-stone-200">Networks already doing the linking</h2>
          <div className="mt-6 space-y-5">
            {NETWORKS.map((network) => (
              <a
                key={network.name}
                href={network.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block rounded-2xl border border-stone-800/30 bg-stone-950/30 p-5 transition-colors hover:border-stone-700/40"
              >
                <div className="text-lg font-light text-teal-300/90">{network.name} ↗</div>
                <p className="mt-1 text-xs uppercase tracking-[0.24em] text-stone-600">{network.scope}</p>
                <p className="mt-3 text-sm leading-relaxed text-stone-400">{network.resonates}</p>
              </a>
            ))}
          </div>
        </div>

        <div className="rounded-[1.5rem] border border-stone-800/30 bg-stone-900/20 p-6">
          <h2 className="text-2xl font-extralight text-stone-200">Practices that help a place tune itself</h2>
          <div className="mt-6 grid gap-4 md:grid-cols-2">
            {PRACTICES.map((practice) => (
              <div
                key={practice.name}
                className="overflow-hidden rounded-2xl border border-stone-800/30 bg-stone-950/30 transition-colors hover:border-stone-700/40"
              >
                <div className="relative aspect-[16/10] overflow-hidden">
                  <Image
                    src={practice.image}
                    alt={practice.name}
                    fill
                    className="object-cover"
                    sizes="(max-width: 1024px) 100vw, 50vw"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-stone-950 via-stone-950/15 to-transparent" />
                </div>
                <div className="space-y-3 p-5">
                  <a
                    href={practice.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex text-lg font-light text-violet-300/90 transition-colors hover:text-violet-200"
                  >
                    {practice.name} ↗
                  </a>
                  <p className="text-sm leading-relaxed text-stone-400">{practice.what}</p>
                  <div className="flex flex-wrap gap-2">
                    {practice.concepts.map((conceptId) => (
                      <Link
                        key={conceptId}
                        href={`/vision/${conceptId}`}
                        className="rounded-full border border-stone-700/40 px-2.5 py-1 text-[11px] text-stone-500 transition-colors hover:border-violet-500/30 hover:text-violet-300/90"
                      >
                        {conceptId.replace("lc-v-", "").replace("lc-", "").replace(/-/g, " ")}
                      </Link>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {(dbCommunities.length > 0 || dbNetworks.length > 0 || dbPractices.length > 0) && (
        <section className="rounded-[1.5rem] border border-stone-800/30 bg-stone-900/20 p-6 text-center">
          <p className="text-sm uppercase tracking-[0.26em] text-stone-500">Live graph signal</p>
          <p className="mx-auto mt-3 max-w-3xl leading-relaxed text-stone-400">
            The curated story is only one layer. The live graph is already collecting additional
            communities, networks, and practices so the field can keep widening without flattening
            into a directory.
          </p>
        </section>
      )}

      <section className="rounded-[2rem] border border-stone-800/30 bg-gradient-to-br from-stone-900/50 via-stone-950/70 to-stone-900/30 px-6 py-14 text-center md:px-12">
        <h2 className="text-3xl font-extralight text-white md:text-4xl">
          A community does not have to start from zero
        </h2>
        <p className="mx-auto mt-4 max-w-3xl text-lg font-light leading-relaxed text-stone-300">
          It can begin in a room, a meal, a practice, a block, a tower floor, a borrowed hall, a
          seasonal convergence, or a rooted piece of land. The work is to sense what each place can
          honestly hold, then let the next layer of life gather there.
        </p>
        <div className="mt-8 flex flex-col justify-center gap-4 sm:flex-row">
          <Link
            href="/vision/lived"
            className="rounded-xl border border-violet-500/20 bg-violet-500/10 px-8 py-3 font-medium text-violet-200 transition-colors hover:bg-violet-500/20"
          >
            Walk through the lived experience
          </Link>
          <Link
            href="/vision/community"
            className="rounded-xl border border-teal-500/20 bg-teal-500/10 px-8 py-3 font-medium text-teal-200 transition-colors hover:bg-teal-500/20"
          >
            See who is gathering
          </Link>
          <Link
            href="/vision/join"
            className="rounded-xl border border-amber-500/20 bg-amber-500/10 px-8 py-3 font-medium text-amber-200 transition-colors hover:bg-amber-500/20"
          >
            Join the field
          </Link>
        </div>
      </section>
    </main>
  );
}
