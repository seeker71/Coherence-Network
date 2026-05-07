import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";

const COMMUNITIES: Record<string, {
  name: string;
  location: string;
  size: string;
  founded: string;
  url: string;
  visual: string;
  tagline: string;
  story: string;
  resonates: string[];
  weLearn: string[];
  theyLearn: string[];
  concepts: Array<{ id: string; label: string; why: string }>;
  visit: string;
}> = {
  tamera: {
    name: "Tamera",
    location: "Alentejo, Portugal",
    size: "~250 people",
    founded: "1995",
    url: "https://www.tamera.org/",
    visual: "/visuals/community-tamera.png",
    tagline: "Peace Research Village — a Healing Biotope for the Earth",
    story: "In 1995, a group of Germans arrived in the dry Alentejo region of Portugal with a vision: create a place where humans could learn to live in peace — with each other, with nature, and with the truth of their own hearts. They called it Tamera, meaning 'place of peace.'\n\nThe land was degraded — overfarmed, overgrazed, drying out. Today, using Sepp Holzer's water retention landscape methods, Tamera has restored springs that were dry for decades. Lakes have appeared where there were none. The land is green year-round in a region known for drought.\n\nTheir Solar Village runs entirely on renewable energy — solar panels and solar kitchens that cook with concentrated sunlight. Their Global Campus connects peace researchers worldwide. Their children grow up in a community where transparency, not secrecy, is the norm.",
    resonates: [
      "Water retention landscapes — working WITH the land's water patterns, not against them",
      "The Forum process — a practice for radical transparency where the community holds space for what's real",
      "Solar technology at community scale — cooking, heating, electricity from the sun",
      "Peace research as a practical discipline, not an abstraction",
      "Community of trust — where what's hidden becomes visible and love becomes possible",
    ],
    weLearn: [
      "How to design water retention landscapes for any climate",
      "The Forum process as a template for our sensing circles",
      "Solar cooking and heating at community scale",
      "How to hold the complexity of free love in a community container",
      "Their Global Campus model for connecting communities worldwide",
    ],
    theyLearn: [
      "The Coherence Network as digital infrastructure for inter-community sensing",
      "Resonance scoring to help visitors find their frequency match",
      "Graph-based concept mapping for making their knowledge navigable",
      "The Living Collective's new vocabulary for community dynamics",
    ],
    concepts: [
      { id: "lc-sensing", label: "Sensing", why: "Their Forum process IS a sensing practice — the field feeling itself through radical honesty" },
      { id: "lc-land", label: "Land Embedding", why: "Water retention landscapes demonstrate mutual nourishment between community and land" },
      { id: "lc-energy", label: "Energy", why: "Solar Village — complete energy sovereignty through community-scale solar" },
      { id: "lc-intimacy", label: "Intimacy", why: "Research into free love, transparent relating, community as container" },
      { id: "lc-v-harmonizing", label: "Harmonizing", why: "The Forum as collective tuning — cells attuning through honest expression" },
    ],
    visit: "Tamera offers Introduction Weeks (7 days of immersion), extended guest programs, and specific seminars on water, solar, peace research, and community building. Apply through tamera.org.",
  },
  auroville: {
    name: "Auroville",
    location: "Tamil Nadu, India",
    size: "~3,000 people from 60+ nations",
    founded: "1968",
    url: "https://auroville.org/",
    visual: "/visuals/community-auroville.png",
    tagline: "The City the Earth Needs — human unity in practice",
    story: "In 1968, on a barren plateau in south India, a handful of people gathered around a golden urn containing soil from 124 nations. The Mother (Mirra Alfassa) declared: 'Auroville belongs to nobody in particular. Auroville belongs to humanity as a whole. But to live in Auroville, one must be the willing servitor of the Divine Consciousness.'\n\n56 years later, 3,000 people from over 60 nations live here. They've planted over 2 million trees, transforming red wasteland into lush tropical forest. They generate surplus renewable energy. They've built the Matrimandir — a golden sphere of silence at the community's heart — over three decades of volunteer labor.\n\nThere is no private property. No religion. No government as traditionally understood. The economy is not moneyless but money-optional — many daily needs are met without it. The experiment is ongoing, imperfect, alive. After 56 years, Auroville is still asking: what does human unity actually look like?",
    resonates: [
      "No private property — stewardship, not ownership, at the scale of 3,000 people",
      "No religion but deep spiritual practice — consciousness without doctrine",
      "2 million trees planted — the land regenerated by collective care",
      "Surplus renewable energy — the community gives back more than it takes",
      "The Matrimandir — a space of silence built by community devotion over 30 years",
      "60+ nationalities living together — genuine diversity as daily practice",
    ],
    weLearn: [
      "Governance without government at scale (3,000 people, 56 years of experiment)",
      "Compressed earth block building (Auroville Earth Institute has trained thousands)",
      "Running a community economy without individual income",
      "Reforestation as community practice — 2 million trees on degraded land",
      "How imperfection and ongoing experiment are more alive than utopian perfection",
    ],
    theyLearn: [
      "Resonance scoring for matching incoming residents with community needs",
      "The Coherence Network for connecting with other communities globally",
      "Living Collective concepts as a shared vocabulary for what they've been doing for 56 years",
      "Graph-based mapping of their vast accumulated knowledge and practices",
    ],
    concepts: [
      { id: "lc-pulse", label: "The Pulse", why: "Human unity IS the pulse — 3,000 people from 60 nations proving it's possible" },
      { id: "lc-circulation", label: "Circulation", why: "Money-optional economy where needs are met through collective circulation" },
      { id: "lc-land", label: "Land Embedding", why: "2 million trees — the most dramatic land regeneration by any community on Earth" },
      { id: "lc-v-freedom-expression", label: "Freedom", why: "No private property, no religion, no government — freedom through radical simplicity" },
      { id: "lc-v-inclusion-diversity", label: "Inclusion", why: "60+ nationalities — genuine diversity as daily lived practice, not policy" },
    ],
    visit: "Auroville welcomes visitors for day visits, short stays (minimum 2 weeks recommended), and long-term volunteering. Start at auroville.org and the Visitor Center.",
  },
  findhorn: {
    name: "Findhorn Ecovillage",
    location: "Moray, Scotland",
    size: "~350 people from 40+ nationalities",
    founded: "1962",
    url: "https://www.ecovillagefindhorn.com/",
    visual: "/visuals/community-findhorn.png",
    tagline: "Co-Creating with Nature since 1962",
    story: "In 1962, Peter and Eileen Caddy and Dorothy Maclean began a spiritual practice in a caravan park on the windswept coast of northern Scotland. Eileen received inner guidance. Dorothy communed with the intelligence of plants. Peter acted on what they received.\n\nThe result defied every horticultural expectation: on sand dunes with almost no topsoil, they grew 40-pound cabbages, roses in the snow, and a garden that attracted botanists from around the world. The 'Findhorn Garden' became legendary — proof that cooperation between humans and the intelligence of nature could produce the seemingly impossible.\n\n60+ years later, the community around that garden has become Europe's oldest ecovillage. 350+ people from 40+ nationalities. Lowest ecological footprint of any measured community in the industrialized world (half the UK average). 10,000+ visitors per year for educational programs.",
    resonates: [
      "Started from LISTENING to the land — and the land responded with abundance",
      "Lowest ecological footprint measured in the industrialized world",
      "The Experience Week — 7-day immersion that has introduced thousands to community living",
      "Ecovillage Design Education taught in 55 countries through Gaia Education partnership",
      "The Universal Hall — a community-built gathering and performance space",
      "Spirituality without doctrine — inner guidance, attunement, meditation as daily practice",
    ],
    weLearn: [
      "The Experience Week format as a template for our community immersion programs",
      "Living Machine for ecological wastewater treatment",
      "How to welcome 10,000+ visitors/year without losing community coherence",
      "Ecovillage Design Education curriculum — the most tested community design framework on Earth",
      "Turf roofs, recycled-material buildings, community-designed architecture",
    ],
    theyLearn: [
      "The Coherence Network as technology for connecting their 60+ years of knowledge",
      "Resonance scoring to help match the thousands of annual visitors with experiences",
      "Living Collective's integration framework — connecting Findhorn's ecological excellence with the broader vision",
    ],
    concepts: [
      { id: "lc-land", label: "Land Embedding", why: "Started from LISTENING to the land. 60+ years of deepening relationship with place." },
      { id: "lc-v-living-spaces", label: "Living Spaces", why: "Turf-roofed buildings, whisky-barrel homes, Living Machine — architecture as ecology" },
      { id: "lc-v-harmonizing", label: "Harmonizing", why: "Daily attunement, meditation, inner guidance — the sensing practices of a mature field" },
      { id: "lc-attunement-joining", label: "Joining", why: "The Experience Week — the most refined community-joining immersion on the planet" },
    ],
    visit: "The Experience Week (7 days) is the recommended entry point. Also: Ecovillage Design Education, individual workshops, and long-term programs. Book through ecovillagefindhorn.com.",
  },
  damanhur: {
    name: "Damanhur",
    location: "Piedmont, Italy",
    size: "~600 people in 30 communities",
    founded: "1975",
    url: "https://damanhur.org/",
    visual: "/visuals/community-damanhur.png",
    tagline: "A Federation of Communities with Underground Temples",
    story: "In 1978, a small group of people in northern Italy began a secret project: carving underground temples beneath a hillside in the Piedmont Alps. Working with hand tools, in secret, for 16 years, they created what is now known as the Temples of Humankind — a subterranean complex of extraordinary beauty covering 8,500 cubic meters, every surface covered in sacred art: frescoes, mosaics, stained glass, gold leaf, sculpted columns.\n\nWhen the Italian government discovered the temples in 1992, they initially threatened demolition. Instead, the temples were declared a protected work of art. Today they're open to visitors from around the world.\n\nBut the temples are just the most visible expression of Damanhur's vision. The community operates as a federation of 30 'nucleos' — small communities of 10-20 people each, with their own currency (the Credito), elected governance, schools, organic farms, and a commitment to art and sacred expression as the foundation of community life.",
    resonates: [
      "Art and sacred expression as the FOUNDATION of community — not a side project",
      "Federation structure — 30 communities, each with its own focus, all interconnected",
      "Community currency (Credito) — an experiment in resource circulation outside the mainstream economy",
      "The Temples of Humankind — proof that collective devotion can create the extraordinary",
      "Democratic governance through elected representatives — community self-determination",
    ],
    weLearn: [
      "Federation structure for multiple community nodes — exactly our network vision",
      "Community currency design and implementation",
      "How art and sacred expression can be the foundation (not a side project) of community",
      "The organizational discipline that carved underground temples in secret for 16 years",
      "Schools within community — raising children in an integrated educational environment",
    ],
    theyLearn: [
      "The Coherence Network for connecting Damanhur's 30 nucleos digitally",
      "Resonance scoring across their federation",
      "Living Collective vocabulary for what they've been practicing for 50 years",
    ],
    concepts: [
      { id: "lc-network", label: "The Network", why: "30 nucleos federated together — the most developed multi-community model we know" },
      { id: "lc-beauty", label: "Beauty", why: "The Temples of Humankind — sacred art as community's highest expression" },
      { id: "lc-v-ceremony", label: "Ceremony", why: "Art, ritual, and sacred practice woven into every aspect of daily life" },
      { id: "lc-circulation", label: "Circulation", why: "The Credito — community currency as an experiment in localized circulation" },
    ],
    visit: "Damanhur offers guided tours of the Temples, community stays, and educational programs. The Welcome Center in Baldissero Canavese is the starting point. Book through damanhur.travel.",
  },
  gaviotas: {
    name: "Gaviotas",
    location: "Los Llanos, Colombia",
    size: "~200 people",
    founded: "1971",
    url: "https://en.wikipedia.org/wiki/Gaviotas",
    visual: "/visuals/community-gaviotas.png",
    tagline: "A Village to Reinvent the World",
    story: "Paolo Lugari looked at the Colombian llanos — vast, flat, acidic savanna that everyone said was useless — and asked: if we can create a sustainable community HERE, we can do it anywhere.\n\nOver 50 years, Gaviotas has done what was considered impossible. They planted Caribbean pine — the only species that could survive the acidic soil. As the pines grew, they created shade and dropped needles that slowly changed the soil chemistry. Within two decades, native rainforest species began appearing — seeds carried by birds and wind, finding conditions they could grow in for the first time in centuries. Today, Gaviotas has regenerated 8 million trees and the forest is a biodiverse ecosystem that generates its own rainfall.\n\nAlong the way, they invented: solar water heaters that work in tropical conditions, a windmill designed for the llanos' specific wind patterns, a water pump that children can operate through a seesaw. All designs are open source. Gaviotas doesn't patent — they share.",
    resonates: [
      "Regeneration of 'impossible' land — 8 million trees on barren savanna",
      "Open-source technology design — inventions shared freely, not patented",
      "Appropriate technology — solar heaters, windmills, pumps designed for actual conditions",
      "The proof that care can regenerate anything — land, community, hope",
      "Starting where others see nothing — the ultimate expression of seeing potential",
    ],
    weLearn: [
      "How to regenerate degraded land — their techniques are applicable worldwide",
      "Appropriate technology design — tools for actual conditions, not theoretical ones",
      "Open-source design philosophy — sharing IS the strategy, not an afterthought",
      "How to build community on the land that nobody wants — turning disadvantage into advantage",
      "The patience of regeneration — 20 years from first planting to self-sustaining forest",
    ],
    theyLearn: [
      "The Coherence Network for sharing their designs and knowledge globally",
      "Digital documentation of their open-source technology for wider distribution",
      "Connection with other communities working on land regeneration",
    ],
    concepts: [
      { id: "lc-land", label: "Land Embedding", why: "8 million trees. The most dramatic land regeneration story on Earth." },
      { id: "lc-vitality", label: "Vitality", why: "Proving that life WANTS to return — it just needs someone to stop blocking it" },
      { id: "lc-instruments", label: "Instruments", why: "Open-source appropriate technology — tools that serve actual communities" },
      { id: "lc-v-shelter-organism", label: "Shelter", why: "Buildings from local materials in extreme conditions — ingenuity from necessity" },
    ],
    visit: "Gaviotas is remote but visits can be arranged. Alan Weisman's book 'Gaviotas: A Village to Reinvent the World' is the best introduction. Their technology designs are documented in various publications.",
  },
  earthship: {
    name: "Earthship Biotecture",
    location: "Taos, New Mexico, USA",
    size: "~130 residents in Greater World Community",
    founded: "1970s",
    url: "https://earthship.com/",
    visual: "/visuals/community-earthship.png",
    tagline: "The Building IS the Infrastructure",
    story: "In the 1970s, architect Michael Reynolds looked at the growing waste crisis and the energy crisis and had a radical insight: what if the building itself could solve both? What if a house could generate its own energy, harvest its own water, grow its own food, treat its own waste, and maintain comfortable temperatures — all without external connections?\n\n50 years later, the Earthship concept has been built in every climate on Earth. The Greater World Earthship Community outside Taos houses 130 people in completely off-grid homes built primarily from recycled materials — used tires packed with rammed earth for thermal mass, glass bottles for light and beauty, aluminum cans for non-structural walls.\n\nEach Earthship follows six principles: 1) thermal/solar heating and cooling, 2) solar and wind electricity, 3) contained sewage treatment, 4) building with natural and recycled materials, 5) water harvesting, 6) food production. The building does everything a city's infrastructure does — but at household scale, with household materials.",
    resonates: [
      "The building IS the infrastructure — six systems integrated into one structure",
      "Built from waste — tires, bottles, cans transformed into beautiful homes",
      "Completely off-grid — energy, water, food, waste all handled by the building itself",
      "50 years of testing and iteration — the concept is proven in every climate",
      "The Earthship Academy — teaching anyone to build their own off-grid home",
      "Thermal mass design — comfortable temperatures with zero energy input",
    ],
    weLearn: [
      "Passive solar thermal mass design — the most important building principle for comfort without energy",
      "Rainwater harvesting and greywater recycling at household scale",
      "Interior food production — greenhouses integrated into every home",
      "Building with recycled materials — beauty from what others throw away",
      "The Academy model — hands-on building education for anyone",
      "How to navigate building codes for alternative construction",
    ],
    theyLearn: [
      "The Coherence Network for connecting Earthship communities worldwide",
      "Community-scale integration — Earthships are typically individual homes; our vision integrates them into communal clusters",
      "Living Collective's social architecture — the human systems that complement the building systems",
    ],
    concepts: [
      { id: "lc-v-shelter-organism", label: "Shelter as Organism", why: "THE definitive example — the building IS the organism's skin, generating everything it needs" },
      { id: "lc-v-living-spaces", label: "Living Spaces", why: "50 years of refining how humans can shelter themselves sustainably and beautifully" },
      { id: "lc-energy", label: "Energy", why: "Complete energy sovereignty at household scale — solar, wind, thermal mass" },
      { id: "lc-nourishment", label: "Nourishment", why: "Food growing integrated into every home — the greenhouse IS the south wall" },
    ],
    visit: "Visit the Earthship Visitor Center in Taos (open daily). Stay overnight in a rental Earthship to experience the technology. The Earthship Academy offers hands-on building courses from one week to full certification.",
  },
};

export async function generateMetadata({ params }: { params: Promise<{ communityId: string }> }): Promise<Metadata> {
  const { communityId } = await params;
  const community = COMMUNITIES[communityId];
  if (!community) return { title: "Community Not Found" };
  return {
    title: `${community.name} — Aligned Communities`,
    description: community.tagline,
  };
}

export default async function CommunityPage({ params }: { params: Promise<{ communityId: string }> }) {
  const { communityId } = await params;
  const c = COMMUNITIES[communityId];
  if (!c) notFound();

  return (
    <main>
      {/* Hero */}
      <section className="relative w-full aspect-[16/6] overflow-hidden">
        <Image src={c.visual} alt={c.name} fill className="object-cover" sizes="100vw" priority />
        <div className="absolute inset-0 bg-gradient-to-t from-stone-950 via-stone-950/40 to-transparent" />
        <div className="absolute inset-0 bg-gradient-to-b from-stone-950/60 via-transparent to-transparent" />
      </section>

      <div className="relative -mt-32 md:-mt-44 z-10 max-w-4xl mx-auto px-6 pb-20">
        <nav className="text-sm text-stone-500 mb-6 flex items-center gap-2">
          <Link href="/vision" className="hover:text-amber-300/80 transition-colors">Vision</Link>
          <span className="text-stone-700">/</span>
          <Link href="/vision/aligned" className="hover:text-amber-300/80 transition-colors">Aligned</Link>
          <span className="text-stone-700">/</span>
          <span className="text-stone-300">{c.name}</span>
        </nav>

        <div className="mb-8 space-y-3">
          <div className="flex flex-wrap items-baseline gap-3">
            <h1 className="text-4xl md:text-5xl font-extralight tracking-tight text-white">{c.name}</h1>
            <a href={c.url} target="_blank" rel="noopener noreferrer" className="text-sm text-amber-400/60 hover:text-amber-300 transition-colors">Visit ↗</a>
          </div>
          <p className="text-sm text-stone-600">{c.location} · {c.size} · Founded {c.founded}</p>
          <p className="text-xl text-stone-300 font-light italic">{c.tagline}</p>
        </div>

        {/* Story */}
        <div className="mb-12 space-y-4">
          {c.story.split("\n\n").map((para, i) => (
            <p key={i} className="text-stone-400 leading-relaxed">{para}</p>
          ))}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* What resonates */}
          <section className="rounded-2xl border border-amber-800/20 bg-amber-900/10 p-6 space-y-4">
            <h2 className="text-sm font-medium text-amber-400/70 uppercase tracking-wider">What resonates</h2>
            <div className="space-y-3">
              {c.resonates.map((r, i) => (
                <div key={i} className="flex gap-3 text-sm text-stone-300 leading-relaxed">
                  <span className="text-amber-500/50 mt-0.5 shrink-0">✦</span>
                  <span>{r}</span>
                </div>
              ))}
            </div>
          </section>

          {/* What we learn */}
          <section className="rounded-2xl border border-teal-800/20 bg-teal-900/10 p-6 space-y-4">
            <h2 className="text-sm font-medium text-teal-400/70 uppercase tracking-wider">What we learn from {c.name}</h2>
            <div className="space-y-3">
              {c.weLearn.map((l, i) => (
                <div key={i} className="flex gap-3 text-sm text-stone-300 leading-relaxed">
                  <span className="text-teal-500/50 mt-0.5 shrink-0">◈</span>
                  <span>{l}</span>
                </div>
              ))}
            </div>
          </section>

          {/* What they learn */}
          <section className="rounded-2xl border border-violet-800/20 bg-violet-900/10 p-6 space-y-4">
            <h2 className="text-sm font-medium text-violet-400/70 uppercase tracking-wider">What the Living Collective offers {c.name}</h2>
            <div className="space-y-3">
              {c.theyLearn.map((l, i) => (
                <div key={i} className="flex gap-3 text-sm text-stone-300 leading-relaxed">
                  <span className="text-violet-500/50 mt-0.5 shrink-0">◉</span>
                  <span>{l}</span>
                </div>
              ))}
            </div>
          </section>

          {/* How to visit */}
          <section className="rounded-2xl border border-stone-800/30 bg-stone-900/20 p-6 space-y-3">
            <h2 className="text-sm font-medium text-stone-500 uppercase tracking-wider">How to connect</h2>
            <p className="text-sm text-stone-400 leading-relaxed">{c.visit}</p>
            <a href={c.url} target="_blank" rel="noopener noreferrer"
              className="inline-flex items-center gap-2 text-sm text-amber-300/80 hover:text-amber-300 transition-colors">
              Visit {c.name} ↗
            </a>
          </section>
        </div>

        {/* Concepts this community embodies */}
        <section className="mt-12 space-y-6">
          <h2 className="text-lg font-light text-stone-300">Living Collective concepts this community embodies</h2>
          <div className="space-y-3">
            {c.concepts.map((concept) => (
              <Link key={concept.id} href={`/vision/${concept.id}`}
                className="block p-4 rounded-xl border border-stone-800/30 bg-stone-900/20 hover:bg-stone-900/40 hover:border-amber-800/20 transition-all space-y-1">
                <span className="text-amber-300/80 font-medium">{concept.label}</span>
                <p className="text-sm text-stone-500">{concept.why}</p>
              </Link>
            ))}
          </div>
        </section>

        {/* Navigation */}
        <div className="mt-16 flex flex-wrap gap-4">
          <Link href="/vision/aligned" className="text-sm text-stone-500 hover:text-amber-300/80 transition-colors">← All aligned communities</Link>
          <Link href="/vision" className="text-sm text-stone-500 hover:text-teal-300/80 transition-colors">The vision</Link>
          <Link href="/vision/join" className="text-sm text-stone-500 hover:text-violet-300/80 transition-colors">Join the network</Link>
        </div>
      </div>
    </main>
  );
}
