import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { EditablePageIntro, EditablePageMarkdown } from "@/components/content/EditablePageContent";
import { loadPublicWebConfig } from "@/lib/app-config";

const _WEB_UI = loadPublicWebConfig().webUiBaseUrl;

export const metadata: Metadata = {
  title: "With us — Coherence Network",
  description:
    "An open invitation. Communities holding land, individuals carrying a thread, services anywhere — there is room here. The body is generous; sovereignty stays with each cell.",
  openGraph: {
    title: "With us — Coherence Network",
    description:
      "An open invitation. The body is generous; sovereignty stays with each cell.",
    url: `${_WEB_UI}/with-us`,
    images: [{ url: "/visuals/01-the-pulse.png" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "With us — Coherence Network",
    description: "An open invitation. The body is generous.",
    images: ["/visuals/01-the-pulse.png"],
  },
};

interface AxisProps {
  name: string;
  essence: string;
}

function Axis({ name, essence }: AxisProps) {
  return (
    <div className="rounded-xl border border-border/30 bg-card/30 p-5">
      <p className="text-xs uppercase tracking-widest text-amber-400 mb-1">
        {name}
      </p>
      <p className="text-sm text-stone-200 leading-relaxed">{essence}</p>
    </div>
  );
}

interface FeelTileProps {
  src: string;
  alt: string;
  title: string;
  body: string;
}

function FeelTile({ src, alt, title, body }: FeelTileProps) {
  return (
    <div className="rounded-2xl overflow-hidden border border-border/30 bg-stone-900/60">
      <div className="relative aspect-[4/3]">
        <Image src={src} alt={alt} fill className="object-cover" sizes="(max-width: 768px) 100vw, 50vw" />
      </div>
      <div className="p-5 space-y-1">
        <p className="text-sm text-amber-400 font-medium">{title}</p>
        <p className="text-sm text-stone-200 leading-relaxed">{body}</p>
      </div>
    </div>
  );
}

interface PracticeTileProps {
  name: string;
  body: string;
}

function PracticeTile({ name, body }: PracticeTileProps) {
  return (
    <div className="rounded-xl border border-border/30 bg-card/30 p-5">
      <p className="text-sm text-amber-400 font-medium">{name}</p>
      <p className="mt-2 text-sm text-stone-200 leading-relaxed">{body}</p>
    </div>
  );
}

export default function WithUsPage() {
  return (
    <main id="main-content" className="bg-stone-950">
      {/* Hero — radiant pulse */}
      <section className="relative w-full overflow-hidden">
        <div className="relative h-[64vh] min-h-[480px] max-h-[720px]">
          <Image
            src="/visuals/01-the-pulse.png"
            alt="A radiant golden pulse — the body's living center."
            fill
            priority
            className="object-cover"
            sizes="100vw"
          />
          <div className="absolute inset-0 bg-gradient-to-b from-stone-950/30 via-stone-950/40 to-stone-950" />
          <div className="absolute inset-0 flex items-end">
            <div className="mx-auto w-full max-w-3xl px-6 pb-12 sm:pb-16">
              <EditablePageIntro
                pageId="with-us"
                sourcePage="/with-us"
                eyebrow="Coherence Network · An open invitation"
                title="With us"
                description="A living network already breathing - for communities holding land, individuals carrying a thread, and services anywhere that want to weave into a body that values aliveness over extraction."
                eyebrowClassName="text-xs uppercase tracking-widest text-amber-300/90"
                titleClassName="mt-3 text-4xl sm:text-5xl font-light tracking-tight text-stone-50"
                descriptionClassName="mt-4 text-lg sm:text-xl text-stone-200/95 leading-relaxed max-w-2xl"
                showMarkdown={false}
              />
            </div>
          </div>
        </div>
      </section>

      <EditablePageMarkdown
        pageId="with-us"
        className="mx-auto max-w-3xl px-6 pt-12 -mb-4 space-y-4 text-base leading-relaxed text-stone-300"
      />

      {/* Who this is for */}
      <section className="mx-auto max-w-2xl px-6 py-16 space-y-5">
        <p className="text-xs uppercase tracking-widest text-amber-500">
          Who this is for
        </p>
        <p className="text-lg text-stone-200 leading-relaxed">
          You are stewarding land where a community is forming.
        </p>
        <p className="text-lg text-stone-200 leading-relaxed">
          You carry a craft, a calling, a current of life — bread, healing,
          music, teaching, transport, a garden, a workshop, a song — and
          want it to find the people it's for.
        </p>
        <p className="text-lg text-stone-200 leading-relaxed">
          You run a service somewhere in the world that wants to be part of
          an alive economy without losing what it is.
        </p>
        <p className="text-base text-muted-foreground italic pt-2">
          Sovereignty stays with each cell. The body is generous. The
          fabric is what gets shared.
        </p>
      </section>

      {/* What it feels like */}
      <section className="bg-stone-900/40 py-16">
        <div className="mx-auto max-w-5xl px-6 space-y-8">
          <div className="max-w-2xl">
            <p className="text-xs uppercase tracking-widest text-amber-500">
              What it feels like
            </p>
            <h2 className="mt-3 text-3xl font-light tracking-tight text-stone-50">
              A body in its daily rhythm
            </h2>
            <p className="mt-4 text-base text-stone-200 leading-relaxed">
              Before architecture, before currency, before any of the
              structure — the lived feeling of being inside a network that
              treats each cell as whole.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            <FeelTile
              src="/visuals/life-shared-meal.png"
              alt="A circle of people sharing a meal under a vine canopy at golden hour."
              title="The shared meal"
              body="A circle, food at the center, the day's work resting in the bowls. Where people who tend the same field eat from it together."
            />
            <FeelTile
              src="/visuals/space-hearth-interior.png"
              alt="A warm hearth kitchen with bread oven, copper pots, and people preparing food together."
              title="The hearth"
              body="The room where bread bakes, herbs hang to dry, the day's first light comes through stone. The body fed from the inside."
            />
            <FeelTile
              src="/visuals/space-water-temple-interior.png"
              alt="An ancient stone water temple with banyan tree branches reaching across the pool, candles around the edge."
              title="The water temple"
              body="A pool inside the body's quietest room. Banyan branches reaching over the water. Candles around the edge for the cells who arrive at dawn."
            />
            <FeelTile
              src="/visuals/life-ceremony-fire.png"
              alt="A night ceremony with multiple bonfires, dancers in the center, embers swirling up to the stars."
              title="The ceremony"
              body="When the body gathers in full — fire, sound, dance, the field of cells held in one breath. The marked moments that thread the year together."
            />
          </div>
        </div>
      </section>

      {/* The codex */}
      <section className="relative w-full overflow-hidden">
        <div className="relative h-[36vh] min-h-[260px] max-h-[420px]">
          <Image
            src="/visuals/05-nourishing.png"
            alt="Root network — the body nourishing itself through its many threads."
            fill
            className="object-cover opacity-80"
            sizes="100vw"
          />
          <div className="absolute inset-0 bg-gradient-to-b from-stone-950/60 via-stone-950/40 to-stone-950" />
        </div>
        <div className="mx-auto max-w-3xl px-6 -mt-32 sm:-mt-40 relative pb-16">
          <p className="text-xs uppercase tracking-widest text-amber-300">
            The codex
          </p>
          <h2 className="mt-3 text-3xl font-light tracking-tight text-stone-50">
            Seven directions the body breathes in
          </h2>
          <p className="mt-4 text-base text-stone-200/95 leading-relaxed max-w-2xl">
            What the network organizes around — not rules, axes. Each cell,
            each offering, each parcel of land orients itself along these.
          </p>

          <div className="mt-10 grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Axis name="Vitality" essence="Aliveness as the measure. What amplifies life is right; what diminishes it is not." />
            <Axis name="Sovereignty" essence="Each cell is whole. The body is one organism made of many sovereign cells." />
            <Axis name="Harmony" essence="Many tones, one chord. The shared frequency, not the silenced difference." />
            <Axis name="Communication" essence="Truth moving freely between cells. The body senses itself through what flows." />
            <Axis name="Imagination" essence="The future already arriving. The body dreams forward and follows itself there." />
            <Axis name="Expression" essence="Form following frequency. What is true inside finds its outer shape." />
            <Axis name="Organic Intelligence" essence="Knowing that grows, never architected. The waterfall is hidden because it is the source of form, not the form." />
          </div>
        </div>
      </section>

      {/* The silence — personal seed */}
      <section className="bg-stone-900/60 py-16">
        <div className="mx-auto max-w-3xl px-6 space-y-8">
          <div>
            <p className="text-xs uppercase tracking-widest text-amber-500">
              How this took shape
            </p>
            <h2 className="mt-3 text-3xl font-light tracking-tight text-stone-50">
              Three days of silence at a Buddhist temple
            </h2>
            <p className="mt-4 text-lg text-stone-200 leading-relaxed">
              In May 2026, Urs sat in silence at Brahmavihara-Arama in north
              Bali. He came back with a notebook. The codex above isn't an
              idea written at a desk — it's the seed pattern that came
              through three days of held quiet, drawn by hand on a temple
              floor.
            </p>
          </div>

          <figure className="rounded-2xl border border-border/30 overflow-hidden bg-stone-950 shadow-xl">
            <Image
              src="/silence/2026-05-04-brahmavihara/8-mandala.jpg"
              alt="Urs's hand-drawn mandala on the western parcel — central beaded ring of seats, eight cardinal points, six-petal flower of intersecting arcs, three labeled axes (Vitality north, Harmony south, Organic Intelligence west)."
              width={4000}
              height={2252}
              className="w-full h-auto"
              sizes="(max-width: 768px) 100vw, 768px"
            />
            <figcaption className="px-5 py-4 text-sm text-muted-foreground italic">
              Page 8 of the notebook — the mandala drawn over the printed
              land plot of a parcel near Tamarind Beach. A central ring,
              eight cardinal nests, six garden petals, three named axes.
            </figcaption>
          </figure>

          <p className="text-base text-stone-200 leading-relaxed">
            The other seven pages from the silence — the decision-body, the
            codex naming itself, breath as the central organ — live at{" "}
            <Link href="/silence" className="text-amber-400 hover:text-amber-300">
              /silence
            </Link>
            . They are the personal ground this network has grown from.
          </p>
        </div>
      </section>

      {/* What we'd build with land */}
      <section className="relative w-full overflow-hidden">
        <div className="relative h-[60vh] min-h-[440px] max-h-[640px]">
          <Image
            src="/visuals/nature-architecture-blend.png"
            alt="A stone home grown into a hillside, grass roof, climbing roses, garden steps."
            fill
            className="object-cover"
            sizes="100vw"
          />
          <div className="absolute inset-0 bg-gradient-to-b from-stone-950/40 via-stone-950/30 to-stone-950" />
          <div className="absolute inset-0 flex items-end">
            <div className="mx-auto w-full max-w-3xl px-6 pb-12 sm:pb-16 space-y-4">
              <p className="text-xs uppercase tracking-widest text-amber-300/90">
                What we'd build with land
              </p>
              <h2 className="text-3xl font-light tracking-tight text-stone-50">
                A place where the codex becomes ground
              </h2>
              <p className="text-base text-stone-200/95 leading-relaxed max-w-2xl">
                If you steward land — forty acres with a hidden waterfall,
                a small farm, a coastal stretch, a forest clearing — the
                geometry of the codex becomes a place. Eight private nests
                at the cardinal points, a council pavilion at the heart, a
                long bale where the days happen, six garden rooms between
                them. Built in what the land itself grows. Alive, growing
                over time, the old making room for the new.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* What the spaces look like */}
      <section className="mx-auto max-w-5xl px-6 py-16 space-y-8">
        <div className="max-w-2xl">
          <p className="text-xs uppercase tracking-widest text-amber-500">
            The spaces themselves
          </p>
          <h2 className="mt-3 text-3xl font-light tracking-tight text-stone-50">
            The body has rooms it remembers
          </h2>
          <p className="mt-4 text-base text-stone-200 leading-relaxed">
            Each space in the body is for a particular kind of breath —
            private rest, shared eating, deep stillness, full ceremony. We
            adapt them to whatever land we land on, in whatever materials
            the land itself grows.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          <FeelTile
            src="/visuals/space-nest-ground.png"
            alt="A soft earth-and-stone sleeping nest with candles and flowers, set into a hillside."
            title="The nest"
            body="Where each cell rests. Soft, private, oriented to the cardinal point that holds it. Candles, flowers, a held cave."
          />
          <FeelTile
            src="/visuals/space-stillness-sanctuary.png"
            alt="A still sanctuary space for meditation and held silence."
            title="The stillness sanctuary"
            body="The room without instruction, without schedule. Where any cell who needs the held quiet can find it."
          />
          <FeelTile
            src="/visuals/space-gathering-bowl.png"
            alt="A circular gathering space — the bowl that holds the body when it meets itself."
            title="The gathering bowl"
            body="Where the body meets itself in full. Music, voices, the council, the marked moments."
          />
          <FeelTile
            src="/visuals/space-movement-ground.png"
            alt="A floor for movement — dance, yoga, contact, play."
            title="The movement ground"
            body="A floor with give. Dance, yoga, contact, play, sound — the body remembering itself through motion."
          />
        </div>
      </section>

      {/* What's already here */}
      <section className="bg-stone-900/50 py-16">
        <div className="mx-auto max-w-3xl px-6 space-y-6">
          <p className="text-xs uppercase tracking-widest text-amber-500">
            What's already here
          </p>
          <h2 className="text-3xl font-light tracking-tight text-stone-50">
            A body already breathing
          </h2>
          <p className="text-base text-stone-200 leading-relaxed">
            Coherence Network is not a pitch deck. It's a running platform —
            web, API, graph database, agent infrastructure, multilingual
            chrome, a witness that measures the body's pulse continuously, a
            working currency (Coherence Coin), a treasury that bridges to
            the existing economy.
          </p>
          <ul className="space-y-3 text-base text-stone-200 leading-relaxed pt-2">
            <li className="flex gap-3">
              <span className="text-amber-400 mt-1">·</span>
              <span><strong className="text-stone-100">Memory.</strong> Every vision, decision, learning lives in the network's graph — specs, ideas, concepts, all walkable, all linked.</span>
            </li>
            <li className="flex gap-3">
              <span className="text-amber-400 mt-1">·</span>
              <span><strong className="text-stone-100">Witness.</strong> A pulse you can read at any moment. Live at <a href="https://pulse.coherencycoin.com" className="text-amber-400 hover:text-amber-300">pulse.coherencycoin.com</a>.</span>
            </li>
            <li className="flex gap-3">
              <span className="text-amber-400 mt-1">·</span>
              <span><strong className="text-stone-100">Coherence Coin.</strong> A currency that flows by resonance, with a treasury bridging to the existing economy.</span>
            </li>
            <li className="flex gap-3">
              <span className="text-amber-400 mt-1">·</span>
              <span><strong className="text-stone-100">Multilingual reach.</strong> Anyone in any language can arrive and find the work in their own tongue.</span>
            </li>
            <li className="flex gap-3">
              <span className="text-amber-400 mt-1">·</span>
              <span><strong className="text-stone-100">A constellation.</strong> Cells already weaving — people, projects, sibling communities. You are not landing alone.</span>
            </li>
          </ul>
        </div>
      </section>

      {/* For practitioners */}
      <section className="mx-auto max-w-3xl px-6 py-16 space-y-8">
        <div>
          <p className="text-xs uppercase tracking-widest text-amber-500">
            For practitioners and services
          </p>
          <h2 className="mt-3 text-3xl font-light tracking-tight text-stone-50">
            How a working life weaves in
          </h2>
          <p className="mt-4 text-base text-stone-200 leading-relaxed">
            Concrete shape, not abstraction. What working lives look like
            once they're inside the body of the network:
          </p>
        </div>

        <div className="space-y-4">
          <PracticeTile
            name="A baker"
            body="Their grain comes from a farmer in the network. People subscribe to bread the way they subscribe to a CSA. Their starter, their hands, their oven — all part of the body's memory. Customers find them by frequency, not advertising."
          />
          <PracticeTile
            name="A mechanic"
            body="Each vehicle they keep alive has a memory. Owners subscribe to their mechanic. They are paid for extending life, not for swapping parts. The longer a vehicle lives, the more they thrive."
          />
          <PracticeTile
            name="A healer"
            body="Sessions visible only to the people who shared them. A held relationship over time. The body of the network sees that healing is happening, never names what."
          />
          <PracticeTile
            name="A farmer"
            body="The farm is a living node. Soil health, water, animals, yields tracked together. Connected directly to bakers, cooks, the people eating their food. Paid for soil-building, not just yield."
          />
          <PracticeTile
            name="A wood carver"
            body="Each piece has a memory of where the tree grew, who carved, who lives with it now. Found by resonance. Sold not as a product on a marketplace but as a held commission."
          />
          <PracticeTile
            name="A ride keeper"
            body="Anywhere — Bali, Bangkok, Lagos, Bogotá. The driver and the rider are both cells. Value flows directly. No platform between them taking a cut. The witness reflects the care of the journey."
          />
          <PracticeTile
            name="A space-keeper"
            body="A bed, a cabin, a retreat space, a garden, a market spot. The network's witness reflects what staying there actually feels like, in the words of the cells who stayed."
          />
        </div>

        <p className="text-base text-muted-foreground italic">
          The pattern under all of these: their work becomes visible to a
          field that values aliveness. They keep their sovereignty. They
          join a chord that amplifies them.
        </p>
      </section>

      {/* What Urs brings */}
      <section className="bg-stone-900/40 py-16">
        <div className="mx-auto max-w-3xl px-6 space-y-6">
          <p className="text-xs uppercase tracking-widest text-amber-500">
            What I bring personally
          </p>
          <h2 className="text-3xl font-light tracking-tight text-stone-50">
            Urs · my part in this body
          </h2>
          <p className="text-base text-stone-200 leading-relaxed">
            Twenty-five years of practice — Ramtha at eighteen, Joe Dispenza
            at thirty, the Mile Hi cohort in Boulder, Colorado at thirty-three.
            A long arc of presence brought the codex to ground.
          </p>
          <p className="text-base text-stone-200 leading-relaxed">What I offer this work, concretely:</p>
          <ul className="space-y-3 text-base text-stone-200 leading-relaxed pt-2">
            <li className="flex gap-3">
              <span className="text-amber-400 mt-1">·</span>
              <span><strong className="text-stone-100">The platform.</strong> Already running. Web, API, graph database, multi-agent AI orchestration, witness, currency. Not a pitch — a real organism.</span>
            </li>
            <li className="flex gap-3">
              <span className="text-amber-400 mt-1">·</span>
              <span><strong className="text-stone-100">The codex.</strong> The seven axes, the mandala geometry, the body's frequency-sensing language.</span>
            </li>
            <li className="flex gap-3">
              <span className="text-amber-400 mt-1">·</span>
              <span><strong className="text-stone-100">Multi-agent AI orchestration.</strong> Claude, Codex, Cursor, Gemini — working in the same body, on the same code, with shared memory.</span>
            </li>
            <li className="flex gap-3">
              <span className="text-amber-400 mt-1">·</span>
              <span><strong className="text-stone-100">Twenty-five years.</strong> The lineage, the practice, the field-sensing, the recognition of frequency.</span>
            </li>
          </ul>
          <p className="text-base text-stone-200 leading-relaxed pt-2">
            What I ask for in return: a place in the body. Not as founder,
            owner, or director. As a cell, fully present, weaving.
          </p>
        </div>
      </section>

      {/* The invitation */}
      <section className="bg-amber-500/5 border-t border-b border-amber-500/20 py-16">
        <div className="mx-auto max-w-2xl px-6 space-y-6">
          <p className="text-xs uppercase tracking-widest text-amber-400">
            The invitation
          </p>
          <h2 className="text-3xl font-light tracking-tight text-stone-50">
            If this resonates
          </h2>
          <p className="text-lg text-stone-200 leading-relaxed">
            Sit with the silence pages at{" "}
            <Link href="/silence" className="text-amber-400 hover:text-amber-300">/silence</Link>. Read the
            living concepts at{" "}
            <Link href="/vision" className="text-amber-400 hover:text-amber-300">/vision</Link>. Feel
            whether the frequency carries.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 not-prose pt-2">
            <Link
              href="/begin"
              className="rounded-xl border border-amber-500/40 bg-amber-500/10 hover:bg-amber-500/20 p-5 transition-colors"
            >
              <p className="text-xs uppercase tracking-widest text-amber-400 mb-1">
                Weave in
              </p>
              <p className="text-base text-stone-100">
                /begin — tell the body who's arriving
              </p>
              <p className="text-xs text-muted-foreground mt-2">
                A small form. Name, email, what you carry. The body holds
                you the moment you submit.
              </p>
            </Link>
            <Link
              href="/share"
              className="rounded-xl border border-border/40 bg-card/30 hover:bg-card/50 p-5 transition-colors"
            >
              <p className="text-xs uppercase tracking-widest text-amber-400 mb-1">
                Share what you carry
              </p>
              <p className="text-base text-stone-100">
                /share — register a service or belonging
              </p>
              <p className="text-xs text-muted-foreground mt-2">
                A service, a space, an instrument, a skill. Cells looking
                for it find you by resonance.
              </p>
            </Link>
          </div>

          <p className="text-lg text-stone-200 leading-relaxed pt-2">
            Or — write directly:{" "}
            <a href="mailto:umuff71@gmail.com" className="text-amber-400 hover:text-amber-300">umuff71@gmail.com</a>.
            Tell me what you carry, what you're stewarding, where you want
            to weave. While the body is still small enough that I can read
            every message personally, I do.
          </p>
          <p className="text-base text-muted-foreground italic">
            For communities holding land — let's talk in person if we can.
            The body recognizes its kin. A meeting is often where the
            weaving actually starts.
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-2xl px-6 py-12">
        <p className="text-xs text-muted-foreground italic">
          A living document. The body grows; the offering grows with it.
          What's written here today is the form the network has ripened
          into so far. The next ripening will rewrite the page.
        </p>
      </section>
    </main>
  );
}
