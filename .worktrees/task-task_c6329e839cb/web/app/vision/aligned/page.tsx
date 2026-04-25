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

type CuratedCommunity = {
  id?: string;
  name: string;
  slug: string;
  location: string;
  size: string;
  image: string;
  url: string;
  resonates: string;
  learn: string;
  concepts: string[];
  concept_labels: string[];
};

type HostSpace = {
  id?: string;
  title: string;
  image: string;
  context: string;
  energy: string;
  body: string;
  first_move: string;
  note: string;
};

type Gathering = {
  id?: string;
  title: string;
  image: string;
  body: string;
  energy: string;
};

type Practice = {
  id?: string;
  name: string;
  image: string;
  url: string;
  what: string;
  concepts: string[];
};

type Network = {
  id?: string;
  name: string;
  url: string;
  scope: string;
  resonates: string;
};

type AlignedContent = {
  source: "graph";
  communities: CuratedCommunity[];
  host_spaces: HostSpace[];
  gatherings: Gathering[];
  practices: Practice[];
  networks: Network[];
  counts: {
    communities: number;
    host_spaces: number;
    gatherings: number;
    practices: number;
    networks: number;
  };
};

const EMPTY_ALIGNED_CONTENT: AlignedContent = {
  source: "graph",
  communities: [],
  host_spaces: [],
  gatherings: [],
  practices: [],
  networks: [],
  counts: {
    communities: 0,
    host_spaces: 0,
    gatherings: 0,
    practices: 0,
    networks: 0,
  },
};

async function fetchAlignedContent(): Promise<AlignedContent> {
  const base = getApiBase();
  try {
    const res = await fetch(`${base}/api/vision/aligned`, { cache: "no-store" });
    if (!res.ok) return EMPTY_ALIGNED_CONTENT;
    const data = await res.json();
    return {
      ...EMPTY_ALIGNED_CONTENT,
      ...data,
      counts: {
        ...EMPTY_ALIGNED_CONTENT.counts,
        ...(data?.counts || {}),
      },
    };
  } catch {
    return EMPTY_ALIGNED_CONTENT;
  }
}

function EmptyAlignedGroup({ label }: { label: string }) {
  return (
    <div className="rounded-[1.5rem] border border-dashed border-stone-800/50 bg-stone-900/10 p-6 text-sm leading-relaxed text-stone-500">
      No {label} records are published in the graph yet.
    </div>
  );
}

function CardImage({
  src,
  alt,
  aspectClass,
  sizes,
}: {
  src: string;
  alt: string;
  aspectClass: string;
  sizes: string;
}) {
  return (
    <div className={`relative ${aspectClass} overflow-hidden`}>
      {src ? (
        <Image
          src={src}
          alt={alt}
          fill
          className="object-cover transition-transform duration-700 group-hover:scale-105"
          sizes={sizes}
        />
      ) : (
        <div className="absolute inset-0 bg-stone-900" />
      )}
      <div className="absolute inset-0 bg-gradient-to-t from-stone-950 via-stone-950/20 to-transparent" />
    </div>
  );
}

export default async function AlignedPage() {
  const alignedContent = await fetchAlignedContent();
  const { communities, host_spaces: hostSpaces, gatherings, practices, networks, counts } = alignedContent;

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
          {communities.map((community) => (
            <article
              key={community.id || community.name}
              className="overflow-hidden rounded-[1.5rem] border border-stone-800/30 bg-stone-900/20"
            >
              <CardImage
                src={community.image}
                alt={community.name}
                aspectClass="aspect-[16/9]"
                sizes="(max-width: 1024px) 100vw, 50vw"
              />
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
                      {community.concept_labels[index] || conceptId.replace("lc-v-", "").replace("lc-", "").replace(/-/g, " ")}
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
          {communities.length === 0 && <EmptyAlignedGroup label="community" />}
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
          {hostSpaces.map((space) => (
            <article
              key={space.id || space.title}
              className="overflow-hidden rounded-[1.5rem] border border-stone-800/30 bg-stone-900/20"
            >
              <CardImage
                src={space.image}
                alt={space.title}
                aspectClass="aspect-[4/5]"
                sizes="(max-width: 1280px) 50vw, 25vw"
              />
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
                  <p className="mt-1 text-xs leading-relaxed text-stone-400">{space.first_move}</p>
                </div>
                <p className="text-xs uppercase tracking-[0.24em] text-stone-500">{space.note}</p>
              </div>
            </article>
          ))}
          {hostSpaces.length === 0 && <EmptyAlignedGroup label="host-space" />}
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
          {gatherings.map((gathering) => (
            <article
              key={gathering.id || gathering.title}
              className="overflow-hidden rounded-[1.5rem] border border-stone-800/30 bg-stone-900/20"
            >
              <CardImage
                src={gathering.image}
                alt={gathering.title}
                aspectClass="aspect-[5/4]"
                sizes="(max-width: 1024px) 100vw, 33vw"
              />
              <div className="space-y-3 p-6">
                <h3 className="text-xl font-light text-violet-200">{gathering.title}</h3>
                <p className="text-sm leading-relaxed text-stone-400">{gathering.body}</p>
                <p className="text-xs uppercase tracking-[0.24em] text-stone-500">{gathering.energy}</p>
              </div>
            </article>
          ))}
          {gatherings.length === 0 && <EmptyAlignedGroup label="gathering" />}
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="rounded-[1.5rem] border border-stone-800/30 bg-stone-900/20 p-6">
          <h2 className="text-2xl font-extralight text-stone-200">Networks already doing the linking</h2>
          <div className="mt-6 space-y-5">
            {networks.map((network) => (
              <a
                key={network.id || network.name}
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
            {networks.length === 0 && <EmptyAlignedGroup label="network" />}
          </div>
        </div>

        <div className="rounded-[1.5rem] border border-stone-800/30 bg-stone-900/20 p-6">
          <h2 className="text-2xl font-extralight text-stone-200">Practices that help a place tune itself</h2>
          <div className="mt-6 grid gap-4 md:grid-cols-2">
            {practices.map((practice) => (
              <div
                key={practice.id || practice.name}
                className="overflow-hidden rounded-2xl border border-stone-800/30 bg-stone-950/30 transition-colors hover:border-stone-700/40"
              >
                <CardImage
                  src={practice.image}
                  alt={practice.name}
                  aspectClass="aspect-[16/10]"
                  sizes="(max-width: 1024px) 100vw, 50vw"
                />
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
            {practices.length === 0 && <EmptyAlignedGroup label="practice" />}
          </div>
        </div>
      </section>

      {(communities.length > 0 || networks.length > 0 || practices.length > 0) && (
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
