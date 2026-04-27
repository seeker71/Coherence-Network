import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { cookies } from "next/headers";
import { createTranslator } from "@/lib/i18n";
import { DEFAULT_LOCALE, isSupportedLocale, type LocaleCode } from "@/lib/locales";
import { getApiBase } from "@/lib/api";
import { LocaleSwitcher } from "@/components/LocaleSwitcher";

type HubSection = {
  id: string;
  concept_id: string;
  image: string;
  title: string;
  body: string;
  note: string;
};

type HubGalleryItem = {
  id?: string;
  image: string;
  label: string;
  href: string;
};

type HubCard = {
  id?: string;
  title: string;
  concept_id: string;
  href: string;
  desc: string;
  tag: string;
};

type VisionHubContent = {
  source: "graph";
  domain: string;
  sections: HubSection[];
  galleries: {
    spaces: HubGalleryItem[];
    practices: HubGalleryItem[];
    people: HubGalleryItem[];
    network: HubGalleryItem[];
  };
  blueprints: HubCard[];
  emerging: HubCard[];
  orientation_words: string[];
  counts: {
    sections: number;
    gallery_items: number;
    blueprints: number;
    emerging: number;
    orientation_words: number;
  };
};

const EMPTY_HUB: VisionHubContent = {
  source: "graph",
  domain: "living-collective",
  sections: [],
  galleries: {
    spaces: [],
    practices: [],
    people: [],
    network: [],
  },
  blueprints: [],
  emerging: [],
  orientation_words: [],
  counts: {
    sections: 0,
    gallery_items: 0,
    blueprints: 0,
    emerging: 0,
    orientation_words: 0,
  },
};

const FALLBACK_HUB: VisionHubContent = {
  source: "graph",
  domain: "living-collective",
  sections: [
    {
      id: "pulse",
      concept_id: "lc-pulse",
      image: "/visuals/01-the-pulse.png",
      title: "The Pulse",
      body: "One truth. Everything else is this expressed at different scales. The cell and the field thrive as one movement. What amplifies aliveness is resonant. This is sensed through presence. It changes. The field senses continuously.",
      note: "In quantum terms: the observer and the observed are one system. Attention is creative force. Coherence is natural. Disharmony requires effort to maintain.",
    },
    {
      id: "sensing",
      concept_id: "lc-sensing",
      image: "/visuals/02-sensing.png",
      title: "Sensing",
      body: "The field feels itself continuously. Every cell transmits and receives. Background awareness, the way a body knows its own temperature. When healthy, needs are felt before articulated. Shifts happen before planned.",
      note: "Like a pod moving as one body: each member sensing position, speed, emotional state, and intention continuously, without effort.",
    },
    {
      id: "attunement",
      concept_id: "lc-attunement",
      image: "/visuals/03-attunement.png",
      title: "Attunement",
      body: "The field maintains its own coherence, sensing which frequencies harmonize and which create interference. Not judgment. Attunement. The way a choir naturally adjusts when one voice drifts.",
      note: "Everything belongs to existence. Not everything harmonizes with this field right now. Both true.",
    },
    {
      id: "vitality",
      concept_id: "lc-vitality",
      image: "/visuals/04-vitality.png",
      title: "Vitality",
      body: "The primary frequency. Life force is not produced but released when interference dissolves. When frequencies align, light becomes coherent and its power increases by orders of magnitude.",
      note: "Vitality compounds. Vital cell makes vital neighbors makes vital field makes vital ecosystem.",
    },
    {
      id: "nourishing",
      concept_id: "lc-nourishing",
      image: "/visuals/05-nourishing.png",
      title: "Nourishing",
      body: "Everything that sustains circulates like blood, like water through soil, like nutrients through underground networks. It flows to where vitality needs it.",
      note: "Resonant when it feels like breathing. Natural, untracked. What is needed is here.",
    },
    {
      id: "resonating",
      concept_id: "lc-resonating",
      image: "/visuals/06-resonating.png",
      title: "Resonating",
      body: "Everything between cells: touch, intimacy, presence, play, silence, attunement. The field's connective tissue. Life energy flows where resonance guides it.",
      note: "Resonant when both cells become more alive and more available to the whole.",
    },
    {
      id: "expressing",
      concept_id: "lc-expressing",
      image: "/visuals/07-expressing.png",
      title: "Expressing",
      body: "The natural overflow of vitality: making, building, growing, singing, dancing, tending. Every cell is creative the way every leaf is photosynthetic.",
      note: "Resonant when surprise appears, when something comes through larger than any one cell.",
    },
    {
      id: "spiraling",
      concept_id: "lc-spiraling",
      image: "/visuals/08-spiraling.png",
      title: "Spiraling",
      body: "The field's relationship with time is not linear but spiral. Each cycle returns to familiar territory at a higher frequency. Nothing repeats. Everything deepens.",
      note: "Phase transition, not loss.",
    },
    {
      id: "field-intelligence",
      concept_id: "lc-field-sensing",
      image: "/visuals/09-field-intelligence.png",
      title: "Field Intelligence",
      body: "The flow of awareness: collective intelligence, harmonic rebalancing, learning. Distributed, parallel, each node both autonomous and integral.",
      note: "At sufficiently high frequency, opposition reveals complementary harmonics of the same fundamental tone.",
    },
    {
      id: "living-space",
      concept_id: "lc-v-living-spaces",
      image: "/visuals/10-living-space.png",
      title: "Living Space",
      body: "What does shelter look like when designed from frequency and flow? Not rooms but resonance zones. Structures that breathe, reconfigure, and grow.",
      note: "The building is the organism's skin.",
    },
    {
      id: "network",
      concept_id: "lc-network",
      image: "/visuals/11-the-network.png",
      title: "The Network",
      body: "One field within a field of fields. Each collective is a node, sharing frequency, nourishment, and intelligence through resonance.",
      note: "The Coherence Network is this planetary-scale living network.",
    },
  ],
  galleries: {
    spaces: [
      { image: "/visuals/space-hearth-interior.png", label: "The Hearth", href: "/vision/lc-nourishment" },
      { image: "/visuals/space-nest-ground.png", label: "Ground Nest", href: "/vision/lc-rest" },
      { image: "/visuals/space-water-temple-interior.png", label: "Water Temple", href: "/vision/lc-v-comfort-joy" },
      { image: "/visuals/space-stillness-sanctuary.png", label: "Stillness Sanctuary", href: "/vision/lc-stillness" },
      { image: "/visuals/space-gathering-bowl.png", label: "Gathering Bowl", href: "/vision/lc-v-living-spaces" },
      { image: "/visuals/space-creation-arc-overview.png", label: "Creation Arc", href: "/vision/lc-offering" },
      { image: "/visuals/space-nest-tree.png", label: "Tree Nest", href: "/vision/lc-rest" },
      { image: "/visuals/space-movement-ground.png", label: "Movement Ground", href: "/vision/lc-play" },
    ],
    practices: [
      { image: "/visuals/life-morning-circle.png", label: "Dawn Attunement", href: "/vision/lc-sensing" },
      { image: "/visuals/practice-yoga-dawn.png", label: "Movement Practice", href: "/vision/lc-v-harmonizing" },
      { image: "/visuals/practice-tantra-circle.png", label: "Presence Circle", href: "/vision/lc-intimacy" },
      { image: "/visuals/practice-sound-healing.png", label: "Sound Journey", href: "/vision/lc-transmission" },
      { image: "/visuals/practice-drum-circle.png", label: "Drum Circle", href: "/vision/lc-v-ceremony" },
      { image: "/visuals/life-breathwork.png", label: "Breathwork", href: "/vision/lc-health" },
      { image: "/visuals/life-ceremony-fire.png", label: "Fire Ceremony", href: "/vision/lc-ceremony" },
      { image: "/visuals/practice-fermentation.png", label: "Fermentation Alchemy", href: "/vision/lc-v-food-practice" },
    ],
    people: [
      { image: "/visuals/life-shared-meal.png", label: "Shared Meal", href: "/vision/lc-nourishment" },
      { image: "/visuals/nature-food-forest-walk.png", label: "Food Forest Walk", href: "/vision/lc-land" },
      { image: "/visuals/nature-animals-integrated.png", label: "Animals in the Field", href: "/vision/lc-land" },
      { image: "/visuals/life-children-play.png", label: "Play Without End", href: "/vision/lc-play" },
      { image: "/visuals/nature-herb-spiral.png", label: "Herb Spiral", href: "/vision/lc-v-food-practice" },
      { image: "/visuals/life-garden-planting.png", label: "Hands in Soil", href: "/vision/lc-land" },
      { image: "/visuals/life-contact-improv.png", label: "Contact & Movement", href: "/vision/lc-play" },
      { image: "/visuals/nature-living-roof-close.png", label: "Living Roof", href: "/vision/lc-v-shelter-organism" },
    ],
    network: [
      { image: "/visuals/network-traveling-musicians.png", label: "Traveling Musicians", href: "/vision/lc-network" },
      { image: "/visuals/network-midsummer-gathering.png", label: "Midsummer Gathering", href: "/vision/lc-network" },
      { image: "/visuals/life-nomad-arrival.png", label: "A Traveler Arrives", href: "/vision/lc-attunement-joining" },
    ],
  },
  blueprints: [
    { title: "Economy", concept_id: "lc-economy", href: "/vision/economy", desc: "Energy in social form. Visible circulation, contribution, vitality buffers, and repurposed-now transformations.", tag: "0" },
    { title: "Space", concept_id: "lc-space", href: "/vision/lc-space", desc: "Common houses, private nests, workshops. Cob, timber, rammed earth.", tag: "7" },
    { title: "Nourishment", concept_id: "lc-nourishment", href: "/vision/lc-nourishment", desc: "Food forests, community kitchens, fermentation. Permaculture plans.", tag: "8" },
    { title: "Land", concept_id: "lc-land", href: "/vision/lc-land", desc: "Keyline design, regeneration, and water harvesting systems.", tag: "8" },
    { title: "Energy", concept_id: "lc-energy", href: "/vision/lc-energy", desc: "Solar arrays, biogas, micro-hydro, and open-source charge controllers.", tag: "8" },
    { title: "Health", concept_id: "lc-health", href: "/vision/lc-health", desc: "Herb gardens, apothecary, sauna, and community health worker training.", tag: "6" },
    { title: "Instruments", concept_id: "lc-instruments", href: "/vision/lc-instruments", desc: "Sensor networks, maker spaces, fab labs, and IoT for gardens and energy.", tag: "7" },
    { title: "Shelter", concept_id: "lc-v-shelter-organism", href: "/vision/lc-v-shelter-organism", desc: "Cob, CEB, SuperAdobe, bamboo, mycelium, and open-source building plans.", tag: "11" },
  ],
  emerging: [
    { title: "Living Spaces", concept_id: "lc-v-living-spaces", href: "/vision/lc-v-living-spaces", desc: "Shelter designed from frequency and flow. Resonance zones, not rooms. Structures that breathe.", tag: "" },
    { title: "Ceremony", concept_id: "lc-v-ceremony", href: "/vision/lc-v-ceremony", desc: "Forms that emerge from pure presence. Cells fully here together with what is.", tag: "" },
    { title: "Harmonizing", concept_id: "lc-v-harmonizing", href: "/vision/lc-v-harmonizing", desc: "How the field tunes itself. Sound, breath, movement, shared stillness.", tag: "" },
    { title: "Food as Practice", concept_id: "lc-v-food-practice", href: "/vision/lc-v-food-practice", desc: "Garden as pharmacy. Kitchen as ceremony. Food carries frequency.", tag: "" },
    { title: "Shelter as Skin", concept_id: "lc-v-shelter-organism", href: "/vision/lc-v-shelter-organism", desc: "Architecture as the field's body. Earthships, cob, bamboo, mycelium. Crystalline structures.", tag: "" },
    { title: "Comfort & Joy", concept_id: "lc-v-comfort-joy", href: "/vision/lc-v-comfort-joy", desc: "Sensory delight as vitality practice. Warmth, texture, beauty in every surface.", tag: "" },
    { title: "Play & Expansion", concept_id: "lc-v-play-expansion", href: "/vision/lc-v-play-expansion", desc: "Adults playing as freely as children. The field at its most quantum.", tag: "" },
    { title: "Inclusion & Diversity", concept_id: "lc-v-inclusion-diversity", href: "/vision/lc-v-inclusion-diversity", desc: "A chord needs different notes. An ecosystem needs different species. Monoculture is fragile.", tag: "" },
    { title: "Freedom & Expression", concept_id: "lc-v-freedom-expression", href: "/vision/lc-v-freedom-expression", desc: "Every cell vibrating at its natural frequency. Freedom and harmony are the same frequency.", tag: "" },
  ],
  orientation_words: ["Wholeness", "Resonance", "Vitality", "Circulation", "Sensing", "Presence", "Freedom", "Joy"],
  counts: {
    sections: 11,
    gallery_items: 27,
    blueprints: 8,
    emerging: 9,
    orientation_words: 8,
  },
};

function buildCounts(hub: VisionHubContent): VisionHubContent["counts"] {
  return {
    sections: hub.sections.length,
    gallery_items: Object.values(hub.galleries).reduce((total, items) => total + items.length, 0),
    blueprints: hub.blueprints.length,
    emerging: hub.emerging.length,
    orientation_words: hub.orientation_words.length,
  };
}

function normalizeHub(data: Partial<VisionHubContent> | null | undefined): VisionHubContent {
  const hub = {
    ...EMPTY_HUB,
    ...(data || {}),
    galleries: {
      ...EMPTY_HUB.galleries,
      ...(data?.galleries || {}),
    },
    counts: {
      ...EMPTY_HUB.counts,
      ...(data?.counts || {}),
    },
  };
  const withFallbacks: VisionHubContent = {
    ...hub,
    sections: hub.sections.length > 0 ? hub.sections : FALLBACK_HUB.sections,
    galleries: {
      spaces: hub.galleries.spaces.length > 0 ? hub.galleries.spaces : FALLBACK_HUB.galleries.spaces,
      practices: hub.galleries.practices.length > 0 ? hub.galleries.practices : FALLBACK_HUB.galleries.practices,
      people: hub.galleries.people.length > 0 ? hub.galleries.people : FALLBACK_HUB.galleries.people,
      network: hub.galleries.network.length > 0 ? hub.galleries.network : FALLBACK_HUB.galleries.network,
    },
    blueprints: hub.blueprints.length > 0 ? hub.blueprints : FALLBACK_HUB.blueprints,
    emerging: hub.emerging.length > 0 ? hub.emerging : FALLBACK_HUB.emerging,
    orientation_words: hub.orientation_words.length > 0 ? hub.orientation_words : FALLBACK_HUB.orientation_words,
  };
  return { ...withFallbacks, counts: buildCounts(withFallbacks) };
}

function localizedHref(href: string, lang: LocaleCode): string {
  if (lang === DEFAULT_LOCALE || href.startsWith("http") || href.startsWith("#")) return href;
  const joiner = href.includes("?") ? "&" : "?";
  return `${href}${joiner}lang=${lang}`;
}

function localizeFallbackHub(hub: VisionHubContent, lang: LocaleCode): VisionHubContent {
  if (lang !== "de") return hub;
  const sections: Record<string, Partial<HubSection>> = {
    "lc-pulse": {
      title: "Der Puls",
      body: "Eine Wahrheit. Alles andere ist diese Wahrheit in verschiedenen Maßstäben. Die Zelle und das Feld gedeihen als eine Bewegung. Was Lebendigkeit verstärkt, ist resonant.",
      note: "Aufmerksamkeit ist schöpferische Kraft. Stimmigkeit ist natürlich; Disharmonie braucht Anstrengung.",
    },
    "lc-sensing": {
      title: "Spüren",
      body: "Das Feld fühlt sich fortwährend selbst. Jede Zelle sendet und empfängt. Bedürfnisse werden gespürt, bevor sie formuliert werden.",
      note: "Wie ein Körper seine Temperatur kennt: still, kontinuierlich, ohne Beschluss.",
    },
    "lc-attunement": {
      title: "Einstimmung",
      body: "Das Feld hält seine eigene Stimmigkeit und spürt, welche Frequenzen harmonieren und welche Reibung erzeugen. Nicht Urteil. Einstimmung.",
      note: "Alles gehört zur Existenz. Nicht alles harmoniert jetzt mit diesem Feld. Beides ist wahr.",
    },
    "lc-vitality": {
      title: "Lebendigkeit",
      body: "Die Grundfrequenz. Lebenskraft wird nicht produziert; sie wird frei, wenn Störung sich löst.",
      note: "Lebendigkeit verstärkt sich: vitale Zelle, vitale Nachbarn, vitales Feld.",
    },
    "lc-nourishing": {
      title: "Nährend",
      body: "Alles, was erhält, zirkuliert wie Blut, Wasser im Boden und Nährstoffe in unterirdischen Netzen. Es fließt dorthin, wo Lebendigkeit es braucht.",
      note: "Resonant, wenn es sich wie Atmen anfühlt.",
    },
    "lc-resonating": {
      title: "Resonieren",
      body: "Alles zwischen den Zellen: Berührung, Nähe, Gegenwart, Spiel, Stille, Einstimmung. Das verbindende Gewebe des Feldes.",
      note: "Resonant, wenn beide Zellen lebendiger und für das Ganze verfügbarer werden.",
    },
    "lc-expressing": {
      title: "Ausdruck",
      body: "Der natürliche Überfluss von Lebendigkeit: machen, bauen, wachsen, singen, tanzen, hüten.",
      note: "Resonant, wenn etwas Größeres als eine einzelne Zelle durchkommt.",
    },
    "lc-spiraling": {
      title: "Spiralen",
      body: "Die Beziehung des Feldes zur Zeit ist nicht linear, sondern spiralig. Jeder Zyklus kehrt an vertrautes Gelände in höherer Frequenz zurück.",
      note: "Phasenübergang, nicht Verlust.",
    },
    "lc-field-sensing": {
      title: "Feldintelligenz",
      body: "Der Fluss von Gewahrsein: kollektive Intelligenz, harmonisches Ausbalancieren, Lernen. Verteilt und zugleich ganz.",
      note: "Gegensatz kann sich als ergänzende Harmonie desselben Grundtons zeigen.",
    },
    "lc-v-living-spaces": {
      title: "Lebendiger Raum",
      body: "Wie sieht Schutz aus, wenn er aus Frequenz und Fluss gestaltet wird? Nicht Zimmer, sondern Resonanzzonen. Strukturen, die atmen und wachsen.",
      note: "Das Gebäude ist die Haut des Organismus.",
    },
    "lc-network": {
      title: "Das Netz",
      body: "Ein Feld in einem Feld aus Feldern. Jede Gemeinschaft ist ein Knoten, der Frequenz, Nahrung und Intelligenz durch Resonanz teilt.",
      note: "Das Coherence Network ist dieses lebendige Netz im planetaren Maßstab.",
    },
  };
  const labels: Record<string, string> = {
    "The Hearth": "Der Herd",
    "Ground Nest": "Erdnest",
    "Water Temple": "Wassertempel",
    "Stillness Sanctuary": "Stille-Zuflucht",
    "Gathering Bowl": "Versammlungsschale",
    "Creation Arc": "Schöpfungsbogen",
    "Tree Nest": "Baumnest",
    "Movement Ground": "Bewegungsgrund",
    "Dawn Attunement": "Morgen-Einstimmung",
    "Movement Practice": "Bewegungspraxis",
    "Presence Circle": "Gegenwartskreis",
    "Sound Journey": "Klangreise",
    "Drum Circle": "Trommelkreis",
    "Breathwork": "Atemarbeit",
    "Fire Ceremony": "Feuerzeremonie",
    "Fermentation Alchemy": "Fermentations-Alchemie",
    "Shared Meal": "Geteilte Mahlzeit",
    "Food Forest Walk": "Gang durch den Nahrungswald",
    "Animals in the Field": "Tiere im Feld",
    "Play Without End": "Spiel ohne Ende",
    "Herb Spiral": "Kräuterspirale",
    "Hands in Soil": "Hände in der Erde",
    "Contact & Movement": "Kontakt & Bewegung",
    "Living Roof": "Lebendiges Dach",
    "Traveling Musicians": "Reisende Musiker",
    "Midsummer Gathering": "Mittsommer-Versammlung",
    "A Traveler Arrives": "Ein Reisender kommt an",
  };
  const cardText: Record<string, Partial<HubCard>> = {
    "/vision/economy": { title: "Ökonomie", desc: "Energie in sozialer Form. Sichtbare Zirkulation, Beitrag, Lebendigkeits-Puffer und Verwandlung dessen, was jetzt da ist." },
    "/vision/lc-space": { title: "Raum", desc: "Gemeinschaftshäuser, private Nester, Werkstätten. Lehm, Holz, Stampflehm." },
    "/vision/lc-nourishment": { title: "Nahrung", desc: "Nahrungswälder, Gemeinschaftsküchen, Fermentation und Permakulturpläne." },
    "/vision/lc-land": { title: "Land", desc: "Keyline-Design, Regeneration und Systeme zur Wasserernte." },
    "/vision/lc-energy": { title: "Energie", desc: "Solarfelder, Biogas, Mikro-Wasser und offene Laderegler." },
    "/vision/lc-health": { title: "Gesundheit", desc: "Kräutergärten, Apotheke, Sauna und gemeinschaftliche Gesundheitsbildung." },
    "/vision/lc-instruments": { title: "Instrumente", desc: "Sensornetze, Werkstätten, Fab Labs und IoT für Gärten und Energie." },
    "/vision/lc-v-shelter-organism": { title: "Schutz", desc: "Lehm, CEB, SuperAdobe, Bambus, Myzel und offene Baupläne." },
    "/vision/lc-v-living-spaces": { title: "Lebendige Räume", desc: "Schutz aus Frequenz und Fluss. Resonanzzonen statt Zimmer. Strukturen, die atmen." },
    "/vision/lc-v-ceremony": { title: "Zeremonie", desc: "Formen, die aus reiner Gegenwart entstehen. Zellen ganz hier mit dem, was ist." },
    "/vision/lc-v-harmonizing": { title: "Harmonisieren", desc: "Wie das Feld sich stimmt. Klang, Atem, Bewegung, geteilte Stille." },
    "/vision/lc-v-food-practice": { title: "Nahrung als Praxis", desc: "Garten als Apotheke. Küche als Zeremonie. Nahrung trägt Frequenz." },
    "/vision/lc-v-comfort-joy": { title: "Komfort & Freude", desc: "Sinnliche Freude als Lebendigkeitspraxis. Wärme, Textur, Schönheit in jeder Oberfläche." },
    "/vision/lc-v-play-expansion": { title: "Spiel & Weitung", desc: "Erwachsene spielen so frei wie Kinder. Das Feld in seiner quantischsten Form." },
    "/vision/lc-v-inclusion-diversity": { title: "Inklusion & Vielfalt", desc: "Ein Akkord braucht verschiedene Töne. Ein Ökosystem braucht verschiedene Arten." },
    "/vision/lc-v-freedom-expression": { title: "Freiheit & Ausdruck", desc: "Jede Zelle schwingt in ihrer natürlichen Frequenz. Freiheit und Harmonie sind dieselbe Frequenz." },
  };
  return {
    ...hub,
    sections: hub.sections.map((section) => ({ ...section, ...(sections[section.concept_id] || {}) })),
    galleries: Object.fromEntries(
      Object.entries(hub.galleries).map(([key, items]) => [
        key,
        items.map((item) => ({ ...item, label: labels[item.label] || item.label })),
      ]),
    ) as VisionHubContent["galleries"],
    blueprints: hub.blueprints.map((card) => ({ ...card, ...(cardText[card.href] || {}) })),
    emerging: hub.emerging.map((card) => ({ ...card, ...(cardText[card.href] || {}) })),
    orientation_words: ["Ganzheit", "Resonanz", "Lebendigkeit", "Zirkulation", "Spüren", "Gegenwart", "Freiheit", "Freude"],
  };
}

async function fetchVisionHub(lang: LocaleCode): Promise<VisionHubContent> {
  try {
    const res = await fetch(`${getApiBase()}/api/vision/living-collective/hub`, { cache: "no-store" });
    if (!res.ok) return localizeFallbackHub(FALLBACK_HUB, lang);
    const data = await res.json();
    return localizeFallbackHub(normalizeHub(data), lang);
  } catch {
    return localizeFallbackHub(FALLBACK_HUB, lang);
  }
}

export const metadata: Metadata = {
  title: "The Living Collective | Coherence Network",
  description:
    "A frequency-based blueprint for organism-based community. Where cells and the field thrive as one movement.",
  openGraph: {
    title: "The Living Collective",
    description: "What emerges when community is designed from resonance, vitality, and coherence.",
  },
};

function EmptyHubGroup({ label }: { label: string }) {
  return (
    <div className="rounded-xl border border-dashed border-stone-800/60 bg-stone-900/10 p-5 text-sm text-stone-600">
      No {label} records are published in the graph yet.
    </div>
  );
}

function GalleryGrid({
  items,
  lang,
  wide = false,
}: {
  items: HubGalleryItem[];
  lang: LocaleCode;
  wide?: boolean;
}) {
  if (items.length === 0) return <EmptyHubGroup label="gallery" />;
  return (
    <div className={wide ? "grid grid-cols-1 md:grid-cols-3 gap-3" : "grid grid-cols-2 md:grid-cols-4 gap-3"}>
      {items.map((item) => (
        <Link
          key={item.id || `${item.href}-${item.label}`}
          href={localizedHref(item.href, lang)}
          className={`group relative ${wide ? "aspect-[16/9]" : "aspect-[4/3]"} rounded-xl overflow-hidden`}
        >
          {item.image ? (
            <Image
              src={item.image}
              alt={item.label}
              fill
              className="object-cover group-hover:scale-105 transition-transform duration-500"
              sizes={wide ? "33vw" : "25vw"}
            />
          ) : (
            <div className="absolute inset-0 bg-stone-900" />
          )}
          <div className="absolute inset-0 bg-gradient-to-t from-stone-950/80 via-transparent to-transparent" />
          <span className={`absolute ${wide ? "bottom-3 left-4 text-sm" : "bottom-2 left-3 text-xs"} text-stone-200 font-medium`}>
            {item.label}
          </span>
        </Link>
      ))}
    </div>
  );
}

/* ── Page ─────────────────────────────────────────────────────────────── */

export default async function VisionPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const cookieStore = await cookies();
  const rawLang = typeof sp.lang === "string" ? sp.lang : undefined;
  const cookieLang = cookieStore.get("NEXT_LOCALE")?.value;
  const lang: LocaleCode = isSupportedLocale(rawLang)
    ? rawLang
    : isSupportedLocale(cookieLang)
      ? cookieLang
      : DEFAULT_LOCALE;
  const t = createTranslator(lang);
  const hub = await fetchVisionHub(lang);

  return (
    <main className="min-h-screen bg-gradient-to-b from-stone-950 via-stone-950 to-stone-900 text-stone-100">
      {/* Hero */}
      <section className="relative flex flex-col items-center justify-center min-h-[80vh] px-6 text-center">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_rgba(234,179,8,0.08)_0%,_transparent_70%)]" />
        <div className="relative z-10 max-w-3xl space-y-8">
          <p className="text-amber-400/80 text-sm sensing-[0.3em] uppercase">
            {t("visionIndex.heroEyebrow")}
          </p>
          <h1 className="text-5xl md:text-7xl font-extralight tracking-tight leading-[1.1]">
            {t("visionIndex.heroTitle1")}{" "}
            <span className="bg-gradient-to-r from-amber-300 via-teal-300 to-violet-300 bg-clip-text text-transparent">
              {t("visionIndex.heroTitle2")}
            </span>
          </h1>
          <p className="text-xl md:text-2xl text-stone-400 font-light leading-relaxed max-w-2xl mx-auto">
            {t("visionIndex.heroLede")}
          </p>
          <div className="pt-4 text-stone-500 text-sm italic">
            {t("visionIndex.heroTag")}
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
        <div className="flex justify-center">
          <LocaleSwitcher currentLang={lang} />
        </div>
        <h2 className="text-2xl md:text-3xl font-light text-stone-300">{t("visionIndex.knowsHeading")}</h2>
        <div className="grid gap-4 text-left text-stone-400 text-lg leading-relaxed">
          <p>
            {t("visionIndex.knowsBody")}{" "}
            <span className="text-amber-300/80">{t("visionIndex.knowsExpansion")}</span>{" "}
            <span className="text-teal-300/80">{t("visionIndex.knowsContraction")}</span>{" "}
            {t("visionIndex.knowsTail")}
          </p>
        </div>
        <div className="grid md:grid-cols-2 gap-6 text-sm text-stone-500 pt-8">
          <div className="space-y-3 p-5 rounded-2xl border border-stone-800/50 bg-stone-900/30">
            <div className="text-amber-400/60 font-medium">{t("visionIndex.knowsCard1Title")}</div>
            <p>{t("visionIndex.knowsCard1Body")}</p>
          </div>
          <div className="space-y-3 p-5 rounded-2xl border border-stone-800/50 bg-stone-900/30">
            <div className="text-amber-400/60 font-medium">{t("visionIndex.knowsCard2Title")}</div>
            <p>{t("visionIndex.knowsCard2Body")}</p>
          </div>
          <div className="space-y-3 p-5 rounded-2xl border border-stone-800/50 bg-stone-900/30">
            <div className="text-amber-400/60 font-medium">{t("visionIndex.knowsCard3Title")}</div>
            <p>{t("visionIndex.knowsCard3Body")}</p>
          </div>
          <div className="space-y-3 p-5 rounded-2xl border border-stone-800/50 bg-stone-900/30">
            <div className="text-amber-400/60 font-medium">{t("visionIndex.knowsCard4Title")}</div>
            <p>{t("visionIndex.knowsCard4Body")}</p>
          </div>
        </div>
      </section>

      {/* Concept sections */}
      {hub.sections.length === 0 && (
        <section className="max-w-4xl mx-auto px-6 py-20">
          <EmptyHubGroup label="vision section" />
        </section>
      )}
      {hub.sections.map((section, i) => (
        <section
          key={section.id}
          id={section.id}
          className={`relative ${i % 2 === 0 ? "" : ""}`}
        >
          {/* Full-width image */}
          <div className="relative w-full aspect-[16/7] md:aspect-[16/6] overflow-hidden">
            {section.image ? (
              <Image
                src={section.image}
                alt={section.title}
                fill
                className="object-cover"
                sizes="100vw"
                priority={i < 3}
              />
            ) : (
              <div className="absolute inset-0 bg-stone-900" />
            )}
            {/* gradient overlays */}
            <div className="absolute inset-0 bg-gradient-to-t from-stone-950 via-stone-950/30 to-transparent" />
            <div className="absolute inset-0 bg-gradient-to-b from-stone-950/60 via-transparent to-transparent" />
          </div>

          {/* Text overlay at bottom of image */}
          <div className="relative -mt-32 md:-mt-48 z-10 max-w-4xl mx-auto px-6 pb-20 md:pb-28">
            <div className="space-y-4">
              <Link href={localizedHref(`/vision/${section.concept_id}`, lang)} className="group">
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

      {/* Life in the field — visual galleries */}
      <section className="max-w-5xl mx-auto px-6 py-24 space-y-20">
        {/* Sacred Spaces */}
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-extralight text-stone-300">{t("visionIndex.galleryHeadingSpaces")}</h2>
            <Link href={localizedHref("/vision/lived", lang)} className="text-sm text-stone-500 hover:text-amber-300/80 transition-colors">{t("common.seeAll")}</Link>
          </div>
          <GalleryGrid items={hub.galleries.spaces} lang={lang} />
        </div>

        {/* Practices & Ceremonies */}
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-extralight text-stone-300">{t("visionIndex.galleryHeadingPractices")}</h2>
            <Link href={localizedHref("/vision/lived", lang)} className="text-sm text-stone-500 hover:text-amber-300/80 transition-colors">{t("common.seeAll")}</Link>
          </div>
          <GalleryGrid items={hub.galleries.practices} lang={lang} />
        </div>

        {/* People, Nature, Animals */}
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-extralight text-stone-300">{t("visionIndex.galleryHeadingPeople")}</h2>
            <Link href={localizedHref("/vision/lived", lang)} className="text-sm text-stone-500 hover:text-amber-300/80 transition-colors">{t("common.seeAll")}</Link>
          </div>
          <GalleryGrid items={hub.galleries.people} lang={lang} />
        </div>

        {/* The Network */}
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-extralight text-stone-300">{t("visionIndex.galleryHeadingNetwork")}</h2>
            <Link href={localizedHref("/vision/lc-network", lang)} className="text-sm text-stone-500 hover:text-amber-300/80 transition-colors">{t("common.explore")}</Link>
          </div>
          <GalleryGrid items={hub.galleries.network} lang={lang} wide />
        </div>

        {/* Stories CTA */}
        <div className="text-center">
          <Link
            href={localizedHref("/vision/lived", lang)}
            className="inline-flex items-center gap-2 px-8 py-3 rounded-xl bg-violet-500/10 border border-violet-500/20 text-violet-300/90 hover:bg-violet-500/20 hover:border-violet-500/30 transition-all font-medium"
          >
            {t("visionIndex.storiesCta")}
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M5 12h14m0 0l-6-6m6 6l-6 6" />
            </svg>
          </Link>
        </div>
      </section>

      {/* Blueprints & Resources — enriched concepts with real building data */}
      <section className="border-t border-stone-800/30">
        <div className="max-w-5xl mx-auto px-6 py-24 space-y-10">
          <div className="text-center space-y-4">
            <h2 className="text-3xl md:text-4xl font-extralight text-stone-300">
              {t("visionIndex.blueprintsHeading")}
            </h2>
            <p className="text-stone-500 text-lg max-w-2xl mx-auto">
              {t("visionIndex.blueprintsLede")}
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
            {hub.blueprints.map((bp) => (
              <Link
                key={bp.id || bp.href}
                href={localizedHref(bp.href, lang)}
                className="group p-5 rounded-2xl border border-teal-800/30 bg-teal-900/10 hover:bg-teal-900/20 hover:border-teal-700/40 transition-all duration-300 space-y-2"
              >
                <div className="flex items-center justify-between">
                  <h3 className="text-base font-medium text-teal-300/90 group-hover:text-teal-200 transition-colors">
                    {bp.title}
                  </h3>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-teal-500/10 text-teal-400/70 border border-teal-500/20">
                    {t("visionIndex.blueprintsResourcesTag", { n: parseInt(bp.tag, 10) || 0 })}
                  </span>
                </div>
                <p className="text-xs text-stone-500 leading-relaxed">
                  {bp.desc}
                </p>
              </Link>
            ))}
            {hub.blueprints.length === 0 && <EmptyHubGroup label="blueprint" />}
          </div>

          <div className="text-center pt-4">
            <Link
              href={localizedHref("/concepts/garden?domain=living-collective", lang)}
              className="inline-flex items-center gap-2 px-6 py-2.5 rounded-xl bg-teal-500/10 border border-teal-500/20 text-teal-300/80 hover:bg-teal-500/20 transition-all text-sm font-medium"
            >
              {t("visionIndex.blueprintsBrowseAll")}
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M5 12h14m0 0l-6-6m6 6l-6 6" />
              </svg>
            </Link>
          </div>
        </div>
      </section>

      {/* Emerging visions */}
      <section className="max-w-4xl mx-auto px-6 py-32 space-y-16">
        <div className="text-center space-y-4">
          <h2 className="text-3xl md:text-4xl font-extralight text-stone-300">
            {t("visionIndex.emergingHeading")}
          </h2>
          <p className="text-stone-500 text-lg max-w-2xl mx-auto">
            {t("visionIndex.emergingLede")}
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-6">
          {hub.emerging.map((vision) => (
            <Link
              key={vision.id || vision.href}
              href={localizedHref(vision.href, lang)}
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
          {hub.emerging.length === 0 && <EmptyHubGroup label="emerging vision" />}
        </div>

        {/* Explore all concepts */}
      </section>

      {/* Orientation */}
      <section className="border-t border-stone-800/30">
        <div className="max-w-3xl mx-auto px-6 py-24 text-center space-y-10">
          <div className="flex flex-wrap justify-center gap-3 text-sm">
            {hub.orientation_words.map(
              (word) => (
                <span
                  key={word}
                  className="px-4 py-2 rounded-full border border-stone-700/40 text-stone-400 bg-stone-900/30"
                >
                  {word}
                </span>
              ),
            )}
            {hub.orientation_words.length === 0 && <EmptyHubGroup label="orientation word" />}
          </div>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href={localizedHref("/vision/immerse", lang)}
              className="inline-flex items-center gap-2 px-8 py-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300/90 hover:bg-amber-500/20 hover:border-amber-500/30 transition-all font-medium"
            >
              {t("visionIndex.orientationImmerse")}
            </Link>
            <Link
              href={localizedHref("/vision/lived", lang)}
              className="inline-flex items-center gap-2 px-8 py-3 rounded-xl bg-violet-500/10 border border-violet-500/20 text-violet-300/90 hover:bg-violet-500/20 hover:border-violet-500/30 transition-all font-medium"
            >
              {t("visionIndex.orientationLived")}
            </Link>
            <Link
              href={localizedHref("/vision/realize", lang)}
              className="inline-flex items-center gap-2 px-8 py-3 rounded-xl bg-teal-500/10 border border-teal-500/20 text-teal-300/90 hover:bg-teal-500/20 hover:border-teal-500/30 transition-all font-medium"
            >
              {t("visionIndex.orientationRealize")}
            </Link>
            <Link
              href={localizedHref("/vision/join", lang)}
              className="inline-flex items-center gap-2 px-8 py-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300/90 hover:bg-amber-500/20 hover:border-amber-500/30 transition-all font-medium"
            >
              {t("visionIndex.orientationJoin")}
            </Link>
          </div>
          <Link href={localizedHref("/vision/aligned", lang)} className="text-sm text-stone-500 hover:text-violet-300/80 transition-colors">
            {t("visionIndex.orientationAligned")}
          </Link>
          <p className="text-stone-600 text-sm pt-6">
            {t("visionIndex.orientationNervous")}
          </p>
          <p className="text-stone-700 text-xs italic">{t("visionIndex.orientationItsAlive")}</p>
          <div className="pt-8">
            <Link
              href={localizedHref("/", lang)}
              className="text-sm text-stone-500 hover:text-amber-400/80 transition-colors"
            >
              {t("visionIndex.orientationReturn")}
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
