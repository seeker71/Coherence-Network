import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { loadPublicWebConfig } from "@/lib/app-config";

const _WEB_UI = loadPublicWebConfig().webUiBaseUrl;

export const metadata: Metadata = {
  title: "Built — the mandala growing into place",
  description:
    "The notebook geometry from Brahmavihara, envisioned in local Bali materials and grown over fifteen years. Eight nests, a council pavilion, a long bale, six garden petals — the architecture as a living organism that the body adds to and lets compost.",
  openGraph: {
    title: "The mandala growing into place",
    description:
      "The notebook geometry built in alang-alang, bamboo, paras stone — and let to grow over fifteen years.",
    url: `${_WEB_UI}/silence/built`,
    images: [{ url: "/silence/2026-05-04-brahmavihara/built/aerial.jpg" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "The mandala growing into place",
    description:
      "The notebook geometry built in alang-alang, bamboo, paras stone — and let to grow over fifteen years.",
    images: ["/silence/2026-05-04-brahmavihara/built/aerial.jpg"],
  },
};

const BASE = "/silence/2026-05-04-brahmavihara/built";

interface ViewProps {
  src: string;
  alt: string;
  caption: React.ReactNode;
  width?: number;
  height?: number;
}

function View({ src, alt, caption, width = 1280, height = 768 }: ViewProps) {
  return (
    <figure className="not-prose my-10">
      <div className="rounded-2xl border border-border/30 overflow-hidden bg-stone-950 shadow-xl">
        <Image
          src={src}
          alt={alt}
          width={width}
          height={height}
          className="w-full h-auto"
          sizes="(max-width: 768px) 100vw, 768px"
        />
      </div>
      <figcaption className="mt-3 text-sm italic text-muted-foreground leading-relaxed">
        {caption}
      </figcaption>
    </figure>
  );
}

function Held({ children }: { children: React.ReactNode }) {
  return (
    <p className="not-prose rounded-md border-l-2 border-amber-500/40 bg-amber-500/5 px-4 py-3 text-sm italic text-stone-300">
      {children}
    </p>
  );
}

export default function SilenceBuiltPage() {
  return (
    <main
      id="main-content"
      className="mx-auto max-w-2xl px-4 sm:px-6 py-12 prose prose-stone dark:prose-invert prose-headings:tracking-tight prose-a:text-amber-600 dark:prose-a:text-amber-400 max-w-none"
    >
      <p className="not-prose text-xs uppercase tracking-widest text-muted-foreground">
        <Link
          href="/silence"
          className="text-muted-foreground/80 hover:text-amber-400"
        >
          ← Silence
        </Link>{" "}
        · The geometry, built and grown
      </p>
      <h1 className="text-3xl font-light tracking-tight">
        The mandala growing into place
      </h1>

      <p className="text-lg leading-relaxed text-stone-300">
        The notebook drawing on{" "}
        <Link href="/silence/mandala">page 8</Link> is a seed pattern, not a
        building plan. What follows is what that geometry could look like
        once it lives in local Bali materials — alang-alang thatched roofs,
        bamboo posts, paras stone, coconut wood, earth — on the parcel near
        Tamarind Beach. Or on any land that calls for it.
      </p>

      <Held>
        The whole concept is that all is alive. The building grows over
        time. When it expands, the old makes room for the new to organically
        grow. There is no final state — only the seed pattern, and the
        organism it grows into.
      </Held>

      <hr className="border-border/30 my-10" />

      <h2 className="text-2xl font-light">From all sides</h2>

      <View
        src={`${BASE}/aerial.jpg`}
        alt="Aerial view of the mandala compound: a central round pavilion with conical alang-alang roof, surrounded by eight smaller nest bales at cardinal points, six garden petals between curving stone paths, a long bale on the south side, beach visible at the top of frame."
        caption={
          <>
            The mandala from above. Central council pavilion, eight nest bales
            at the cardinal points, six garden petals between the arcs, the
            long bale running along the southern axis toward the sea. The
            beach sits a quarter-mile beyond the canopy.
          </>
        }
        width={1280}
        height={1280}
      />

      <View
        src={`${BASE}/entry.jpg`}
        alt="Ground level view approaching a carved paras stone gate with a striped Balinese umbrella, a small lotus shrine, frangipani trees lining a path, alang-alang roofs visible beyond."
        caption={
          <>
            The entry along the <em>Vitality</em> axis (north). A carved paras
            stone gate, a small <em>padmasana</em> shrine where the morning's
            canang sari is placed, frangipani lining the processional path.
            Visitors arrive into welcome.
          </>
        }
      />

      <View
        src={`${BASE}/sea-side.jpg`}
        alt="View from a grass lawn toward the long pavilion, polished coconut wood floor, deep eaves, the council pavilion's conical roof rising behind, single old tamarind tree."
        caption={
          <>
            From the sea side — the <em>Harmony</em> axis (south). The long
            bale stretches across the frame, the council pavilion's conical
            roof rises behind it, a single old tamarind tree shades the
            opening. The breath of the place flows out toward the water.
          </>
        }
      />

      <View
        src={`${BASE}/council-interior.jpg`}
        alt="Interior of the round council pavilion looking up into the high conical alang-alang roof, eight giant bamboo posts ringing the space, oculus at the apex, ring of paras stone seats around a black lava stone fire pit, small smoke rising."
        caption={
          <>
            Inside the council pavilion at the center. Conical alang-alang
            roof on eight giant bamboo posts, a small oculus at the apex,
            paras stone seats ringing a black lava stone fire pit. Sacred
            ground for marked moments — ceremony, sound, marriages, births,
            the held silences.
          </>
        }
        width={1280}
        height={1280}
      />

      <View
        src={`${BASE}/commons-interior.jpg`}
        alt="Long open Balinese pavilion interior at evening, polished coconut wood floor, alang-alang thatched roof on tabah bamboo trusses, woven gedeg bamboo screens, stone hearth and earth oven at one end, woven mats and cushions, low oil lamps, jasmine vines climbing posts."
        caption={
          <>
            Inside the long bale (the <em>commons</em>). Polished coconut
            wood floor that dances, kitchen at the western end, sliding
            gedeg screens that subdivide the room, woven mats unrolled for
            silence or movement or sharing. Where the days actually happen.
          </>
        }
      />

      <View
        src={`${BASE}/nest-dawn.jpg`}
        alt="Small private Balinese sleeping bale at dawn, sliding bamboo screens, sleeping platform with kapok mattress, mosquito netting, frangipani branches above, jasmine vines on the threshold."
        caption={
          <>
            One of the eight nests at dawn. Raised an inch off the earth on
            ironwood feet, mostly air, woven gedeg screens that close at
            night, jasmine on the threshold, mosquito net hanging like a
            soft cloud. You don&apos;t wake inside a building. You wake
            inside the garden.
          </>
        }
        width={1024}
        height={1280}
      />

      <hr className="border-border/30 my-10" />

      <h2 className="text-2xl font-light">Growing over time</h2>

      <p>
        The building is alive. The seed pattern is what gets built in the
        first six months. After that, the body keeps growing — new bales
        arrive where they&apos;re called, old bales compost back into the
        garden when their work is done, the alang-alang gets re-thatched,
        the bamboo gets replaced one post at a time, the moss thickens,
        the fruit forest fills its canopy.
      </p>

      <View
        src={`${BASE}/year-1-seedling.jpg`}
        alt="Year 1: freshly built compound with golden new alang-alang roofs, pale bamboo posts, young frangipani trees, earth still bare in places, the buildings looking new and clean."
        caption={
          <>
            <strong>Year 1 — the seedling.</strong> The crew of thirteen has
            finished. The roofs are golden new alang-alang, the bamboo is
            pale, the frangipani trees are young, the earth is still bare
            where the gardens are starting. People can move in. The body
            has a place to sit.
          </>
        }
      />

      <View
        src={`${BASE}/year-5-mature.jpg`}
        alt="Year 5: alang-alang roofs slightly silvered with age, bamboo posts gone honey-amber, frangipani trees full and blossoming, fruit trees beginning to canopy, mosses in stone path cracks, lotus pond with full leaves, vines climbing posts."
        caption={
          <>
            <strong>Year 5 — maturing.</strong> The roofs have silvered
            slightly. The bamboo posts have gone honey-amber. Mosses fill
            every crack in the stone paths. The lotus pond is full. Jasmine
            and passion flower climb every post. The fruit forest is
            beginning to canopy. The body has lived a few hundred ceremonies
            now.
          </>
        }
      />

      <View
        src={`${BASE}/year-15-elder.jpg`}
        alt="Year 15: deep silver-grey alang-alang roofs, dark amber bamboo, thick moss covering everything, mature fruit forest with full canopy embracing the buildings, vines wrapping every post, an old bale partly composted into garden, deep shade."
        caption={
          <>
            <strong>Year 15 — the elder.</strong> The roofs are silver-grey.
            The bamboo is deep amber. Moss covers the stone paths thick
            enough to muffle footsteps. The fruit forest has closed its
            canopy over the compound — at midday you forget you&apos;re
            inside human-made space. One of the original bales has been
            composted back into garden because the body needed that breath
            elsewhere; a new small bale grew where it was called. The
            geometry is still recognizable, but the organism has moved.
          </>
        }
      />

      <View
        src={`${BASE}/growth-detail.jpg`}
        alt="Macro detail of bamboo post wrapped in jasmine vine and tillandsia air plants, alang-alang thatch above with bird's-nest ferns growing from the corners, gecko on the post, soft tropical light."
        caption={
          <>
            The closer you look, the less the building stops and the garden
            starts. Bird&apos;s-nest ferns grow from the corners of the
            roof. Tillandsias and jasmine wrap the posts. The geckos live
            in the thatch. The architecture and the life become one body.
          </>
        }
        width={1024}
        height={1024}
      />

      <hr className="border-border/30 my-10" />

      <h2 className="text-2xl font-light">What this gives the body</h2>

      <p>
        Three nested depths of being-with-each-other, all under the same
        open garden:
      </p>

      <ul>
        <li>
          The <strong>nest</strong> is the personal tent under the canopy —
          private, soft, oriented to its cardinal point.
        </li>
        <li>
          The <strong>long bale</strong> is the shared clearing where the
          everyday happens — eating, dancing, silence, music, talking, in
          small or large groups.
        </li>
        <li>
          The <strong>council pavilion</strong> is the cave at the heart of
          the mountain — for the marked moments, the held ceremonies, the
          sound that needs to be done in the dark with fire.
        </li>
      </ul>

      <p>
        The corners are nests. The center is celebration and ritual focus.
        The long bale holds the days. The garden petals feed and heal and
        offer. The three axes — Vitality, Harmony, Organic Intelligence —
        orient the whole organism in conversation with the world, the sea,
        and the deep forest.
      </p>

      <Held>
        The mandala isn&apos;t placed <em>on</em> the land. It&apos;s the
        geometry the land was already making, drawn in materials the land
        grew, with people seated inside the drawing. And it grows.
      </Held>

      <hr className="border-border/30 my-10" />

      <h2 className="text-2xl font-light">Where this could happen</h2>

      <p>
        The geometry is portable. It was drawn for the parcel near Tamarind
        Beach, but the same seed pattern grows on any land that calls for
        it — forty acres with a hidden waterfall between two sacred places,
        a small farm in the temperate north, a coastal stretch in the
        Mediterranean, a clearing in the forest of the Pacific Northwest,
        anywhere. The materials change with the climate. The codex
        doesn&apos;t.
      </p>

      <p>
        If you steward land where the body wants to land, the network can
        weave with you.{" "}
        <Link href="/weave">Read about how →</Link>
      </p>

      <hr className="border-border/30 my-10" />

      <p className="text-sm text-muted-foreground italic">
        These views are AI-rendered from prompts written in the body&apos;s
        voice — Pollinations Flux, deterministic seeds, prompts in{" "}
        <code>scripts/generate_silence_built_visuals.py</code> and{" "}
        <code>scripts/generate_silence_alive_visuals.py</code>. They are not
        photographs of a place that exists. They are the body imagining
        forward, the way it imagines forward in any direction it&apos;s
        called.
      </p>
    </main>
  );
}
