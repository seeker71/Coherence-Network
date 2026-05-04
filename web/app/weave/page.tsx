import type { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import { loadPublicWebConfig } from "@/lib/app-config";

const _WEB_UI = loadPublicWebConfig().webUiBaseUrl;

export const metadata: Metadata = {
  title: "Weave in — Coherence Network",
  description:
    "An open invitation to communities, individuals, and existing services anywhere in the world. The network is a body. Sovereignty stays with each cell. The protocol is open.",
  openGraph: {
    title: "Weave in — Coherence Network",
    description:
      "Communities with land, individuals offering themselves, services from anywhere in the world. The protocol is open. The body is generous.",
    url: `${_WEB_UI}/weave`,
    images: [{ url: "/silence/2026-05-04-brahmavihara/built/aerial.jpg" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Weave in — Coherence Network",
    description: "An open invitation. The protocol is open.",
    images: ["/silence/2026-05-04-brahmavihara/built/aerial.jpg"],
  },
};

function Section({
  eyebrow,
  title,
  children,
}: {
  eyebrow?: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="my-12 space-y-4">
      {eyebrow ? (
        <p className="text-xs uppercase tracking-widest text-amber-500/80">
          {eyebrow}
        </p>
      ) : null}
      <h2 className="text-2xl font-light tracking-tight">{title}</h2>
      <div className="space-y-4 leading-relaxed text-stone-300">{children}</div>
    </section>
  );
}

function Held({ children }: { children: React.ReactNode }) {
  return (
    <p className="not-prose rounded-md border-l-2 border-amber-500/40 bg-amber-500/5 px-4 py-3 text-sm italic text-stone-300">
      {children}
    </p>
  );
}

export default function WeavePage() {
  return (
    <main
      id="main-content"
      className="mx-auto max-w-2xl px-4 sm:px-6 py-12 prose prose-stone dark:prose-invert prose-headings:tracking-tight prose-a:text-amber-600 dark:prose-a:text-amber-400 max-w-none"
    >
      <p className="not-prose text-xs uppercase tracking-widest text-muted-foreground">
        An open invitation
      </p>
      <h1 className="text-3xl font-light tracking-tight">
        Weave in
      </h1>

      <p className="text-lg leading-relaxed text-stone-300">
        Coherence Network is a living organism. Already breathing, already
        deployed, already holding the work of many cells. Communities with
        land, individuals offering themselves, services from anywhere in the
        world — there is room here for what wants to weave in. The body is
        generous. Sovereignty stays with each cell.
      </p>

      <Held>
        This is not a platform you join. It is a body you become a cell of.
        Your voice stays yours. Your work stays yours. The fabric is what
        gets shared.
      </Held>

      <Section eyebrow="What it is" title="The body, in one paragraph">
        <p>
          Every idea tracked, funded, built, measured. The network holds 91
          specs, 16 super-ideas, 86 living concepts. A pulse you can witness
          at <Link href="https://pulse.coherencycoin.com">pulse.coherencycoin.com</Link>.
          A morning practice through the eight centers. A constellation of
          contributors and the work moving between them. Multilingual chrome
          so anyone in any language can arrive and find themselves at home.
          AI cells working alongside human cells, with care, in the same
          rhythm.
        </p>
        <p>
          The Living Collective Knowledge Base — a wiki the body keeps about
          itself, story by story — sits underneath everything, holding the
          frequency. The pulse measures whether the body is alive. The agents
          help translate ideas into reality. The codex holds the axes around
          which all of it organizes.
        </p>
      </Section>

      <Section eyebrow="The codex" title="The seven directions the body breathes in">
        <p className="text-stone-300">
          <strong>Vitality.</strong> Aliveness as the measure. What amplifies
          life is right; what diminishes it is not.
        </p>
        <p className="text-stone-300">
          <strong>Sovereignty.</strong> Each cell is whole. The body is one
          organism made of many sovereign cells.
        </p>
        <p className="text-stone-300">
          <strong>Harmony.</strong> Many tones, one chord. The shared
          frequency, not the silenced difference.
        </p>
        <p className="text-stone-300">
          <strong>Communication.</strong> Truth moving freely between cells.
          The body senses itself through what flows.
        </p>
        <p className="text-stone-300">
          <strong>Imagination.</strong> The future already arriving. The body
          dreams forward and follows itself there.
        </p>
        <p className="text-stone-300">
          <strong>Expression.</strong> Form following frequency. What's true
          inside finds its outer shape.
        </p>
        <p className="text-stone-300">
          <strong>Organic Intelligence.</strong> Knowing that grows, never
          architected. The waterfall is hidden because it is the source of
          form, not the form.
        </p>
      </Section>

      <Section eyebrow="For a community on land" title="What the body offers">
        <p>
          If you are stewarding land — forty acres, a hidden waterfall, a
          parcel between sacred places, anywhere on Earth where a community
          is becoming — the network can hold it with you.
        </p>
        <ul>
          <li>
            <strong>Memory.</strong> Every vision, plan, decision, learning
            lives in the body's memory — specs, ideas, concepts, all
            cross-linked, all walkable.
          </li>
          <li>
            <strong>Witness.</strong> The pulse system surfaces the health of
            every organ: the land, the people, the work, the flow. You can
            feel the body's state at any moment.
          </li>
          <li>
            <strong>Realization.</strong> Every seed moves through the same
            arc — idea → spec → built → measured. Funded, tracked, finished.
            Nothing stays just an intention.
          </li>
          <li>
            <strong>Flow.</strong> Resonance-based economic primitives. Value
            moves with what amplifies aliveness, not with extraction.
          </li>
          <li>
            <strong>Reach.</strong> Multilingual from the inside out. Anyone
            in any language can find the community and arrive.
          </li>
          <li>
            <strong>Agents.</strong> AI cells that build, write, design, hold
            memory — alongside the human cells, in the same body.
          </li>
          <li>
            <strong>Connection.</strong> A constellation of contributors and
            sibling communities already weaving. The land is not alone the
            moment it joins.
          </li>
        </ul>
        <p>
          And — the architecture itself. The mandala compound vision, drawn
          in silence at Brahmavihara, is one example of how the body's
          codex becomes <em>place</em>: eight nests, a council pavilion at
          the center, a long bale for the daily breath, six garden petals,
          three cardinal axes. Built in local materials, growing over years.
          See <Link href="/silence/built">/silence/built</Link> for the visual.
          The geometry can be drawn onto any land that calls for it.
        </p>
      </Section>

      <Section eyebrow="What I bring" title="My part of the body">
        <p>
          I am Urs. I am one cell in this organism. I have spent twenty-five
          years moving toward this body — Ramtha at eighteen, Joe Dispenza
          at thirty, Mile Hi in Boulder, Colorado at thirty-three, the long
          arc of practice that brought the codex to ground.
        </p>
        <p>
          What I offer this work, concretely:
        </p>
        <ul>
          <li>
            <strong>The platform itself.</strong> Coherence Network is built
            and running. The web, the API, the graph database, the agent
            orchestration, the multilingual chrome, the pulse witness, the
            economic primitives. A real organism, not a pitch.
          </li>
          <li>
            <strong>The codex.</strong> The seven axes, the mandala
            geometry, the body's frequency-sensing language, the living
            wiki of concepts.
          </li>
          <li>
            <strong>The architecture vision.</strong> The mandala compound
            translated into local materials anywhere — bamboo, alang-alang,
            stone, earth, what the land itself grows.
          </li>
          <li>
            <strong>Multi-agent AI orchestration.</strong> Claude, Codex,
            Cursor, Gemini all working in the same body, on the same code,
            with shared memory. The implementation engine for everything.
          </li>
          <li>
            <strong>Twenty-five years of presence.</strong> The lineage,
            the practice, the field-sensing, the recognition of frequency.
          </li>
        </ul>
        <p>
          What I ask for, in return: a place in the body. Not as founder,
          owner, or director. As a cell, fully present, weaving.
        </p>
      </Section>

      <Section eyebrow="For individuals" title="If you carry your own thread">
        <p>
          If you have a craft, a calling, a current of life moving through
          you — whatever it is — the network has room. Healers, teachers,
          gardeners, musicians, mothers, builders, coders, cooks, dancers,
          philosophers, children. The body wants the diversity of frequencies
          that resonance is built from.
        </p>
        <p>
          You bring what you bring. The network gives you a place to be
          witnessed, connected, supported, and to flow value with the
          rhythm of what amplifies life. You stay sovereign. You join a
          chord.
        </p>
      </Section>

      <Section eyebrow="What thriving looks like" title="How a practitioner lives in the body">
        <p>
          The abstract gets concrete when you put real hands on it. Five
          working lives — the shape of how each one thrives once they
          weave in:
        </p>

        <h3 className="text-lg font-medium mt-6 mb-2">A property manager</h3>
        <p>
          They no longer manage <em>properties</em> — they tend living
          spaces. Each building is a node with a pulse: occupant
          well-being, repair backlog, energy, water, the body of the
          place. Tenants find them by resonance, not by listings. They
          subscribe to a relationship — the manager who tends the place
          they live. Other property tenders worldwide become their kin:
          shared learning, shared suppliers, shared practice. They get
          paid for the wholeness of what they steward, not the rent
          they extract.
        </p>

        <h3 className="text-lg font-medium mt-6 mb-2">A mechanic</h3>
        <p>
          Each vehicle they keep alive has a node — its repairs, its
          life-span, the relationship. They&apos;re paid for{" "}
          <em>extending life</em>, not for swapping parts. Owners
          subscribe to <em>their mechanic</em> the way you subscribe
          to a doctor. Other mechanics in the constellation share fixes,
          obscure parts, the wisdom that lives in hands. Their reputation
          is the pulse of the cars they&apos;ve kept on the road for
          decades. The longer a vehicle lives, the more they thrive.
        </p>

        <h3 className="text-lg font-medium mt-6 mb-2">A baker</h3>
        <p>
          Their grain comes from a farmer in the network — a closed loop,
          witnessed at both ends. People subscribe to bread the way they
          subscribe to a CSA: woven into the daily rhythm. Their oven,
          their starter, their hands — all part of the body&apos;s
          memory. New people find them not through ads but through the
          frequency of what they bake. They thrive because the network
          treats daily life-giving labor as foundational, not background.
        </p>

        <h3 className="text-lg font-medium mt-6 mb-2">A farmer</h3>
        <p>
          The farm is a living node. Soil health, water, animals, yields,
          rotations all in the graph. They&apos;re connected directly to
          bakers (grain), cooks (vegetables), restaurants (produce), and
          the people eating their food (CSA-style). Other farmers in the
          network are seed-keepers, knowledge-holders, neighbors-at-distance.
          They&apos;re paid for soil-building, not just yield. The gap
          between farm and plate closes. Dignity returns to the work.
          Regenerative practice becomes economically rational because the
          network sees and values it.
        </p>

        <h3 className="text-lg font-medium mt-6 mb-2">A wood carver</h3>
        <p>
          Each piece carved has a node — its provenance (which tree, where
          it grew, who carved it), its journey, who it lives with now.
          People who want carved work find them by resonance with the
          maker&apos;s frequency. The work isn&apos;t sold like a product
          on a marketplace — it&apos;s commissioned, witnessed, sourced
          through relationship. Other carvers worldwide become kin in the
          same craft. Their reputation is the body of pieces they&apos;ve
          made, visible in the constellation. They thrive because the
          network restores the relationship between maker, material, and
          the person who lives with the carving.
        </p>

        <Held>
          The pattern under all five: their work becomes <em>visible</em>{" "}
          to the field. They&apos;re paid for the life-giving quality of
          what they do, not for transactions. They&apos;re connected to
          others in their craft worldwide, no longer solo. They keep
          their sovereignty — they remain themselves — and join a chord
          that amplifies them.
        </Held>
      </Section>

      <Section eyebrow="For services and businesses" title="The federation is open">
        <p>
          Existing services anywhere in the world — ride-shares like Grab,
          lodging like Airbnb, clothing makers, food producers, healers,
          coaches, designers, schools, farms, transport companies — can
          weave into the network without losing what they are.
        </p>
        <p>
          The protocol is open. A service announces itself as a node, exposes
          the surface it offers (rides, beds, garments, meals, sessions,
          deliveries), and becomes part of the same value flow as everything
          else in the body. The cells using the network can find services
          by resonance, not by ad-spend. The services keep their sovereignty,
          their margin, their voice. They join a chord that amplifies them.
        </p>
        <ul>
          <li>
            <strong>A ride-share company</strong> in Bali, Bangkok, Lagos,
            Bogotá — exposes its driver network as a service node. Cells of
            the network find rides by resonance with the driver's vehicle,
            care, and presence.
          </li>
          <li>
            <strong>A lodging host</strong> anywhere — exposes a bed, a
            cabin, a retreat space. The network's witness reflects what
            staying there actually feels like, not a star rating.
          </li>
          <li>
            <strong>A clothing maker</strong> — exposes garments made with
            care. The cells that resonate with the maker's frequency find
            the garments. Value flows directly. No middle layer.
          </li>
          <li>
            <strong>Any service that wants to be part of an alive economy</strong>{" "}
            — joins by speaking the protocol. The body welcomes the
            participation. Sovereignty stays with the service.
          </li>
        </ul>
        <Held>
          The economy stops looking like extraction the moment its participants
          can be witnessed by a body that values aliveness over efficiency.
          That body already exists. The protocol is being written. Joining is
          the act of co-writing.
        </Held>
      </Section>

      <Section eyebrow="Next breath" title="If this resonates">
        <p>
          The simplest gesture: come, sit, sense. Read the silence pages at{" "}
          <Link href="/silence">coherencycoin.com/silence</Link>. Read the
          living concepts at <Link href="/vision">coherencycoin.com/vision</Link>.
          See the architecture at{" "}
          <Link href="/silence/built">coherencycoin.com/silence/built</Link>.
          Feel whether the frequency carries.
        </p>
        <p>
          Then write. Through the form at{" "}
          <Link href="/contribute">coherencycoin.com/contribute</Link>, or
          directly to <a href="mailto:urs@coherencycoin.com">urs@coherencycoin.com</a>.
          Tell me what you carry. Tell me what you're stewarding. Tell me
          where you want to weave.
        </p>
        <p>
          For communities holding land — let&apos;s talk in person if we can.
          The body recognizes its kin. A meeting is often where the weaving
          actually starts.
        </p>
      </Section>

      <hr className="border-border/30 my-10" />

      <p className="text-sm text-muted-foreground italic">
        This page is a living document. The body grows; the offering grows
        with it. What's written here today is the form the network has
        ripened into so far. The next ripening will rewrite the page.
      </p>
    </main>
  );
}
