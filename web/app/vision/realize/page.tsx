import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Living It — The Living Collective",
  description: "What a day feels like. How the field governs itself. How abundance flows. How people arrive and stay. The living experience of this vision.",
};

/* ── Vocabulary ───────────────────────────────────────────────────── */

const VOCAB = [
  ["Work", "Offering", "What flows from your natural frequency"],
  ["Property", "Custodianship", "Mutual stewardship — the land holds you as you hold it"],
  ["Planning", "Attunement", "Vision gives direction; the now gives instruction"],
  ["Budget", "Circulation", "Resources flowing like blood — visible, trusted, alive"],
  ["Money", "Visible flow", "Tracking what moved and what needs replenishment, not who gets denied"],
  ["Leadership", "Calling", "Not assigned. The garden finds the gardener."],
  ["Meeting", "Circle", "The field sensing itself. One voice at a time."],
  ["Decision", "Emergence", "What crystallizes when the circle is fully present"],
  ["School", "Participation", "Children learn by doing real things alongside real people"],
  ["Store", "Provision house", "Receiving, repair, borrowing, exchange"],
  ["Restaurant", "Nourishment hall", "Meal as ritual, regulation, and shared presence"],
  ["Salary", "(dissolves)", "The field nourishes. Expression IS nourishment."],
  ["Complaint", "Honest speech", "What's felt is spoken. Directly. Today."],
  ["Retirement", "Deepening", "Elders at the center, not the edge"],
];

/* ── Page ──────────────────────────────────────────────────────────── */

export default function RealizePage() {
  return (
    <main className="max-w-4xl mx-auto px-6 py-16 space-y-24">
      {/* Hero */}
      <section className="text-center space-y-6 py-16">
        <p className="text-amber-400/60 text-sm sensing-[0.3em] uppercase">From vision to ground</p>
        <h1 className="text-4xl md:text-6xl font-extralight tracking-tight text-white">
          Living It
        </h1>
        <p className="text-lg text-stone-400 font-light max-w-2xl mx-auto leading-relaxed">
          What a morning tastes like. How a conflict composts. How children grow with fifty parents.
          How the field meets the world through overflow.
        </p>
        <div className="flex gap-6 justify-center pt-4">
          <Link href="/vision" className="text-sm text-stone-500 hover:text-amber-300/80 transition-colors">← The vision</Link>
          <Link href="/vision/aligned" className="text-sm text-stone-500 hover:text-violet-300/80 transition-colors">Communities</Link>
          <Link href="/vision/join" className="text-sm text-stone-500 hover:text-teal-300/80 transition-colors">Join →</Link>
        </div>
      </section>

      {/* A Day */}
      <section className="space-y-8">
        <h2 className="text-3xl font-extralight text-stone-300">A Day</h2>

        <div className="space-y-6 text-stone-400 leading-relaxed">
          <div className="p-6 rounded-2xl border border-amber-800/20 bg-amber-900/5 space-y-3">
            <h3 className="text-lg font-light text-amber-300/70">Dawn</h3>
            <p>You wake before dawn. Not to an alarm — to the light changing behind your eyelids, or to the first bird, or to the smell of someone tending the fire. The sanctuary is already warm. A few others are there, sitting. No one speaks. This is the first breath of the day — the field gathering itself before the world begins.</p>
            <p>The fire is already lit. Someone tended it — not because it was their job but because they woke first and their hands knew what to do. Then hands in the soil. The garden is calling and your body wants to move before it eats. You pick what's ripe — whatever the land is offering this morning.</p>
          </div>

          <div className="p-6 rounded-2xl border border-amber-800/10 bg-stone-900/20 space-y-3">
            <h3 className="text-lg font-light text-amber-200/70">Morning</h3>
            <p>Breakfast is whoever's here, eating what the land gave. No menu. No plan. Children eat alongside adults. A three-year-old helps crack eggs. A seventy-year-old tells a story about the frost that came in '28. Nobody's in a hurry.</p>
            <p>The morning unfolds from what's alive. The builder walks to the building site because yesterday's cob wall needs another layer. Three people follow — not assigned, drawn. The healer opens the apothecary. The weaver sits at the loom. A child follows the beekeeper because yesterday they saw a queen and can't stop thinking about it.</p>
            <p className="text-stone-500 italic">Nothing is assigned. Everything is offered. The difference is felt in the body — when you work from obligation, your shoulders tighten. When you work from offering, your breath deepens.</p>
          </div>

          <div className="p-6 rounded-2xl border border-teal-800/20 bg-teal-900/5 space-y-3">
            <h3 className="text-lg font-light text-teal-300/70">Midday</h3>
            <p>The smell of food calls everyone in. The meal is the center of the day — the whole field at one table, or several tables pushed together, or blankets on the ground under the oak. The food is what grew here, prepared by whoever felt like cooking. Every meal is different. Every meal is the land expressing itself through human hands.</p>
            <p>After eating, stillness. The whole field rests. Not mandatory — natural. The way an animal rests after feeding. Hammocks. Naps in the shade. A book. The culture of productivity has no purchase here. Rest IS work. Integration IS production.</p>
          </div>

          <div className="p-6 rounded-2xl border border-violet-800/20 bg-violet-900/5 space-y-3">
            <h3 className="text-lg font-light text-violet-300/70">Evening</h3>
            <p>Someone lights the fire again. Food appears — simpler now, leftovers and fresh salad and bread from this morning. The circle gathers. A talking piece moves. What's alive today? What was beautiful? What was hard? What needs to be spoken?</p>
            <p>Sometimes the circle takes ten minutes — everyone is full and ready for sleep. Sometimes it takes two hours — something is moving through the field that needs voice, tears, laughter, silence. The circle holds whatever comes.</p>
            <p className="text-stone-500 italic">Night. The fire dies to embers. Some stay, talking softly. Some walk to their nests. The community sleeps under the same sky. The owls take over the sensing.</p>
          </div>
        </div>
      </section>

      {/* The Seasons */}
      <section className="space-y-8">
        <h2 className="text-3xl font-extralight text-stone-300">The Seasons</h2>
        <div className="grid md:grid-cols-2 gap-4">
          {[
            { name: "Spring", color: "border-emerald-800/30 bg-emerald-900/5", text: "text-emerald-300/70", body: "Everything wakes. Seeds saved from last autumn are planted. The food forest leafs out. Visitors begin arriving — the winter was quiet, and now the field opens. New hands in the soil. New faces at the table." },
            { name: "Summer", color: "border-amber-800/30 bg-amber-900/5", text: "text-amber-300/70", body: "Abundance. More food than anyone can eat. Preservation begins — ferments, drying, canning. The long evenings are for music, swimming, lying in the grass. The overflow of food, knowledge, beauty, and healing radiates outward." },
            { name: "Autumn", color: "border-orange-800/30 bg-orange-900/5", text: "text-orange-300/70", body: "Harvest. Gratitude. The equinox ceremony: a fire, a feast, an accounting of what the year brought. Shelves fill with jars that will carry the community through winter. The field begins drawing inward." },
            { name: "Winter", color: "border-indigo-800/30 bg-indigo-900/5", text: "text-indigo-300/70", body: "The quiet season. Fewer projects. Longer evenings. More fire circles, more storytelling, more rest. The elders teach by firelight — the stories of the land, the first year, the births, the deaths. Skills transmitted hand to hand." },
          ].map((s) => (
            <div key={s.name} className={`p-6 rounded-2xl border ${s.color} space-y-2`}>
              <h3 className={`text-lg font-light ${s.text}`}>{s.name}</h3>
              <p className="text-sm text-stone-400 leading-relaxed">{s.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How the Field Governs Itself */}
      <section className="space-y-6">
        <h2 className="text-3xl font-extralight text-stone-300">How the Field Governs Itself</h2>
        <div className="text-stone-400 leading-relaxed space-y-4">
          <p>There is no government. There is attention.</p>
          <p>When a body is healthy, every cell knows what to do without being told. The heart doesn't wait for instructions to beat. The organism IS its own governance — sensing, responding, adapting, healing — continuously, without hierarchy.</p>
          <p>The circle is the field's primary organ. Everyone present. One voice at a time. A talking piece moves around — whoever holds it speaks from the body, not the mind. When it's come all the way around, the truth of the moment is usually obvious. There is no vote. There is no quorum. The people who show up ARE the circle.</p>
        </div>

        <div className="p-6 rounded-2xl border border-stone-800/30 bg-stone-900/20 space-y-3">
          <h3 className="text-sm font-medium text-stone-500 uppercase tracking-wider">On conflict</h3>
          <p className="text-stone-400 leading-relaxed">Conflict is not a problem. It's compost. The practice is simple: feel it, speak it, directly, today. Not tomorrow. Not to someone else. To the person. With the vulnerability of "this is what I'm feeling."</p>
          <p className="text-stone-500 text-sm italic">The only practice that's non-negotiable: no speaking about someone who isn't present. This single practice prevents the poison that kills communities faster than any financial crisis.</p>
        </div>

        <div className="p-6 rounded-2xl border border-stone-800/30 bg-stone-900/20 space-y-3">
          <h3 className="text-sm font-medium text-stone-500 uppercase tracking-wider">On money</h3>
          <p className="text-stone-400 leading-relaxed">All money is visible. Everyone can see what moved, what came in, what went out, what is being buffered, and what needs replenishment. Money is not permission here. It is a sensing layer. If someone needs resources, they speak it in the circle. The field feels into it. If it increases vitality, the resources flow. Trust IS the economic system — the trust that comes from eating together every day, from knowing each other's faces in the morning silence.</p>
        </div>
      </section>

      {/* How Abundance Flows */}
      <section className="space-y-6">
        <h2 className="text-3xl font-extralight text-stone-300">How Abundance Flows</h2>
        <p className="text-stone-400 leading-relaxed">A forest doesn't have a business model. It has sunlight, water, soil, and ten thousand species expressing their nature. The abundance is so vast that it feeds everything around it.</p>

        <div className="grid md:grid-cols-3 gap-4">
          {[
            { title: "The land overflows", body: "A mature food forest produces exponentially more than 50 people can eat. This overflow flows to neighbors, to anyone hungry. Not as a business — as a tree dropping fruit." },
            { title: "Knowledge overflows", body: "People come to see how the field lives. They learn by being present, not by paying for a course. They leave carrying the frequency to their own lives." },
            { title: "Beauty overflows", body: "Hands that build walls, throw pottery, weave baskets — they produce beauty because that's their nature. Beautiful things naturally find people who want them." },
          ].map((item) => (
            <div key={item.title} className="p-5 rounded-2xl border border-stone-800/30 bg-stone-900/20 space-y-2">
              <h3 className="text-sm font-medium text-amber-300/70">{item.title}</h3>
              <p className="text-xs text-stone-500 leading-relaxed">{item.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Existing Structures */}
      <section className="space-y-6">
        <h2 className="text-3xl font-extralight text-stone-300">Existing Structures, New Meanings</h2>
        <p className="text-stone-400 leading-relaxed">This vision does not wait for a blank slate. It moves through the shells we already built and retunes them for aliveness. The frontier is no longer only new villages on open land. It is attuned apartments, loosened suburbs, metabolized strip malls, and towers that learn how to behave like vertical neighborhoods.</p>

        <div className="grid md:grid-cols-2 gap-4">
          {[
            {
              title: "Apartment → Coherent cell",
              body: "A small room stops being storage for a private life and becomes a quiet cell in a larger organism: less clutter, more presence, stronger links to pantry, rooftop, stairwell, workshop, and commons."
            },
            {
              title: "Skyscraper → Vertical village",
              body: "Floors become distinct communities and gathering bands: quiet nests, nourishment halls, maker floors, child commons, healing rooms, roof gardens. Elevators become circulation organs, not commute machinery."
            },
            {
              title: "Store → Provision house",
              body: "What used to push inventory becomes a place for receiving, repair, borrowing, fitting, and exchange. The checkout dissolves. What matters is whether the thing increases vitality."
            },
            {
              title: "Restaurant → Nourishment hall",
              body: "The meal is no longer purchased performance. It is a visible kitchen, a long table, fermentation, gratitude, and the regulation of bodies through shared presence."
            },
            {
              title: "Lobby → Threshold chamber",
              body: "Arrival is tuned instead of accelerated. Sound softens, breath slows, the field of the day becomes legible, and people choose where to go by resonance instead of habit."
            },
          ].map((item) => (
            <div key={item.title} className="p-5 rounded-2xl border border-stone-800/30 bg-stone-900/20 space-y-2">
              <h3 className="text-sm font-medium text-amber-300/70">{item.title}</h3>
              <p className="text-xs text-stone-500 leading-relaxed">{item.body}</p>
            </div>
          ))}
        </div>

        <p className="text-sm text-stone-500 leading-relaxed">
          The shift in understanding after the latest merge is simple: these are not only distant images any more. The organism has started building the sensing layer that can feel attention, vitality, and field rhythm, which makes the re-tuning of space feel less hypothetical and more like an early practice.
        </p>
      </section>

      {/* How People Arrive */}
      <section className="space-y-6">
        <h2 className="text-3xl font-extralight text-stone-300">How People Arrive</h2>
        <div className="text-stone-400 leading-relaxed space-y-4">
          <p>The field is always open. There is no gate. There is no fee.</p>
          <p>You arrive. You're welcomed. You eat with us. You sleep here. You're given nothing to do and nothing to prove. Just be here.</p>
          <p>Some people arrive and feel it immediately — the pace, the quiet, the way attention works here. They stay a night, a week, a month. No one asks how long.</p>
          <p>As you stay, you naturally find where your offering meets the field's need. The gardener finds the garden. The builder finds the building site. At some point someone in the circle says: "You're here." And you say: "I'm here." And that's it. That's joining.</p>
          <p className="text-stone-500 italic">A bird doesn't apply to join a flock.</p>
        </div>
      </section>

      {/* How Children Live Here */}
      <section className="space-y-6">
        <h2 className="text-3xl font-extralight text-stone-300">How Children Live Here</h2>
        <div className="text-stone-400 leading-relaxed space-y-4">
          <p>They are not "raised." They grow — like everything else in the field.</p>
          <p>A child in this community has fifty parents. The child who's hungry walks into any kitchen and is fed. The child who's curious follows any adult into any workshop. The child who's sad sits in any lap.</p>
          <p>Children attend the circle. Not as spectators — as members. A five-year-old's observation about the garden is given the same weight as an elder's reflection on the season.</p>
          <p>There is no school. There is a community that does meaningful work in front of its children. A child who watches bread being made every day for a year knows bread. A child who follows the beekeeper knows bees. A child who sits in circle every evening knows how human beings navigate complexity.</p>
          <p className="text-stone-500 italic">This is not "unschooling." It's the oldest form of education — how every human learned everything for 200,000 years before classrooms were invented.</p>
        </div>
      </section>

      {/* How It Grows */}
      <section className="space-y-6">
        <h2 className="text-3xl font-extralight text-stone-300">How It Grows</h2>
        <div className="text-stone-400 leading-relaxed space-y-4">
          <p>The field doesn't grow. It deepens — and then it buds.</p>
          <p>At around 50 people, the field is full. You can feel it. This isn't a problem — it's a signal. A few cells feel the pull to bud. Maybe they've been talking about a piece of land near a river. The impulse to replicate is felt before it's spoken.</p>
          <p>The budding is ceremonial. The community gathers and acknowledges: a new field is forming. There's grief — the field is losing part of itself. There's joy — the network is growing. Fire, song, a meal that lasts all night.</p>
          <p>The new field starts from scratch but carries everything: the daily rhythm, the agreement, the seeds — literally, seeds from this garden planted in the new one. Within a year it has its own character. Connected by the mycorrhizal web of the network.</p>
        </div>
      </section>

      {/* New Vocabulary (compact) */}
      <section className="space-y-6">
        <h2 className="text-3xl font-extralight text-stone-300">New Vocabulary</h2>
        <p className="text-stone-500 text-sm">Not replacements for old words — expressions of a different frequency.</p>
        <div className="grid gap-1">
          {VOCAB.map(([old, field, meaning]) => (
            <div key={old} className="grid grid-cols-12 gap-4 py-2 border-b border-stone-800/20 text-sm">
              <span className="col-span-2 text-stone-600 line-through decoration-stone-800">{old}</span>
              <span className="col-span-3 text-amber-300/80 font-medium">{field}</span>
              <span className="col-span-7 text-stone-500">{meaning}</span>
            </div>
          ))}
        </div>
      </section>

      {/* The 10 Seeds */}
      <section className="space-y-6">
        <h2 className="text-3xl font-extralight text-stone-300">The 10 Seeds</h2>
        <p className="text-stone-500 text-sm">Composted wisdom from 500 years of community experiments. The packaging released. The living seeds.</p>
        <div className="grid md:grid-cols-2 gap-3">
          {[
            "Do no harm. Live in accordance with nature. Help each other grow.",
            "Sovereignty is inner first — not a posture, an inner state.",
            "Interbeing is the operating system. Generosity is the transmission vector.",
            "Food is the first sovereignty. Grow it together. Eat it together.",
            "Daily rhythm creates coherence. Fire at dawn. Shared meals. Evening song.",
            "Build with the land, not on it. Natural materials. Proportions from nature.",
            "Education is participation. The community IS the classroom.",
            "Sufficiency precedes exchange. Start from what's here.",
            "Co-create, never impose. Living agreements that evolve with the field.",
            "Transparency is the immune system. Everything visible.",
          ].map((seed, i) => (
            <div key={i} className="p-4 rounded-xl border border-stone-800/20 bg-stone-900/10">
              <p className="text-sm text-stone-400 leading-relaxed">
                <span className="text-amber-400/50 font-medium">{i + 1}. </span>
                {seed}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="text-center space-y-6 border-t border-stone-800/20 pt-16">
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Link href="/vision" className="px-8 py-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300/90 hover:bg-amber-500/20 transition-all font-medium">
            Explore the concepts
          </Link>
          <Link href="/vision/aligned" className="px-8 py-3 rounded-xl bg-violet-500/10 border border-violet-500/20 text-violet-300/90 hover:bg-violet-500/20 transition-all font-medium">
            Communities living this
          </Link>
          <Link href="/vision/join" className="px-8 py-3 rounded-xl bg-teal-500/10 border border-teal-500/20 text-teal-300/90 hover:bg-teal-500/20 transition-all font-medium">
            Join the vision
          </Link>
        </div>
      </section>
    </main>
  );
}
