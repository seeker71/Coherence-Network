import type { Metadata } from "next";
import Link from "next/link";
import { Panel } from "@/components/Panel";

/**
 * /people/grab — a service-provider profile rendered in the network's
 * lens. Grab is currently a centralized super-app extracting margin
 * between sovereigns who could meet directly. This page imagines
 * what its work would look like inside the network — same matching
 * function, no parasite layer.
 *
 * Welcoming gesture, not a partnership claim. Posted as a recognition
 * that the matching service Grab provides is real value the body
 * appreciates, while naming clearly the architectural inversion the
 * sovereignty-everywhere economy would invite.
 */

export const metadata: Metadata = {
  title: "Grab — Inside the Network's Lens | Coherence Network",
  description:
    "What Grab's ride-hailing, food-delivery, and payments work looks like inside a sovereignty-everywhere economy. The matching function survives; the extractive layer dissolves.",
};

export default function GrabProfilePage() {
  return (
    <main className="max-w-3xl mx-auto px-6 py-12">
      <nav
        className="text-sm text-muted-foreground mb-8 flex items-center gap-2"
        aria-label="breadcrumb"
      >
        <Link href="/" className="hover:text-primary transition-colors">
          Home
        </Link>
        <span className="text-muted-foreground/50">/</span>
        <Link href="/people" className="hover:text-primary transition-colors">
          People
        </Link>
        <span className="text-muted-foreground/50">/</span>
        <span className="text-foreground/80">Grab</span>
      </nav>

      <header className="mb-10">
        <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground mb-3">
          Service provider — Southeast Asia
        </p>
        <h1 className="text-4xl md:text-5xl font-extralight text-foreground leading-tight mb-4">
          Grab
        </h1>
        <p className="text-lg text-foreground/80 leading-relaxed">
          Ride-hailing, food delivery, and payments across Southeast Asia
          — including Bali. Currently a centralized super-app. Rendered
          here through the network's lens as a structural reflection on
          how the same service would look as a cooperative routing
          layer.
        </p>
        <dl className="mt-5 text-sm text-foreground/85 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5">
          <dt className="text-muted-foreground">Footprint</dt>
          <dd>Southeast Asia, eight countries, hundreds of cities</dd>
          <dt className="text-muted-foreground">Where the body meets it</dt>
          <dd>
            Daily — every Grab ride in Ubud, every food order, every
            QR-payment is a sovereign exchange currently rendered as
            transaction
          </dd>
          <dt className="text-muted-foreground">Field</dt>
          <dd>Matching · routing · payments · logistics</dd>
        </dl>
      </header>

      <Panel variant="warm" eyebrow="A note from this body">
        <p className="text-sm text-foreground/85 leading-relaxed">
          Grab is not a member of this network and has not been invited
          into a partnership. This page is the body's reflection on
          Grab's work as we use it daily — a thinking-aloud about what
          the same function looks like under sovereignty-everywhere
          economics. If anyone at Grab finds this page and wants to
          continue the conversation, the door is open.
        </p>
      </Panel>

      <section className="mt-12 space-y-12">
        <article>
          <h2 className="text-2xl font-light text-foreground mb-4">
            What Grab does
          </h2>
          <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
            <p>
              Three sovereigns meet in every Grab transaction: a
              driver, a rider, and the ground between them. Grab's app
              is the introduction layer — it knows where the rider is,
              which drivers are nearby, what each driver charges, what
              route to take. The match is real value. Without it, the
              two sovereigns would never find each other in the time
              window the rider has.
            </p>
            <p>
              The same shape extends to food delivery (restaurant +
              eater + courier), to payments (sender + recipient +
              settlement layer), to logistics, to digital banking. In
              every case the sovereigns are real, and the matching
              function is real, and Grab's app is the connective tissue
              that lets them find each other.
            </p>
          </div>
        </article>

        <article>
          <h2 className="text-2xl font-light text-foreground mb-4">
            What Grab currently extracts
          </h2>
          <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
            <p>
              The matching is value. The extraction is the gap between
              what the rider pays and what the driver receives. Across
              Southeast Asia, that gap commonly runs 20–30% of every
              fare, sometimes more after surge multipliers and other
              modifiers. The driver, who shepherds the vehicle, takes
              on its wear, fuels it, maintains it, and bears the
              accident risk, receives the smaller share. The rider, who
              has no leverage, pays the larger one.
            </p>
            <p>
              Add to this the surveillance economy: every driver's
              location, every rider's pattern, every restaurant's
              throughput is harvested by the platform and used to
              optimize the platform's profit, not the sovereigns whose
              data it is. The drivers' bodies make Grab's market cap;
              their consent to that arrangement is a contract they
              cannot meaningfully negotiate.
            </p>
          </div>
        </article>

        <article>
          <h2 className="text-2xl font-light text-foreground mb-4">
            What Grab looks like inside the network
          </h2>
          <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
            <p>
              The matching function survives. It is real value and
              someone has to do it. What changes is who owns it, who
              benefits from it, and what data flows where.
            </p>
            <p>
              The matching layer becomes a cooperative whose members
              are the drivers, the riders, the restaurant shepherds,
              the couriers, and the small operations team that keeps
              the routing service alive. Each fare fires a{" "}
              <code className="not-italic text-foreground/80">
                (4, GIVE)
              </code>{" "}
              tetradic glyph: driver, rider, route, atmosphere. The
              rider's CC flows into the substrate; the routing
              cooperative takes a transparent witness fee — the actual
              cost of the matching service plus a small tending margin,
              signed by the cooperative's members rather than imposed
              by a separate company. The driver receives the rest.
            </p>
            <p>
              Surveillance becomes consensual visibility. Drivers
              publish their location to the cooperative under terms
              they helped write, not under a contract dictated to them.
              Their data is owned by the cooperative they belong to,
              not by a separate corporate entity in a different
              country.
            </p>
            <p>
              Profit motive becomes coherence flow. The cooperative's
              books balance to keep the matching service alive and
              sustainable; surplus flows back to the members in
              proportion to their actual contribution; the
              shareholder layer that currently extracts the gap simply
              isn't there.
            </p>
          </div>
        </article>

        <article>
          <Panel
            variant="cool"
            eyebrow="The architectural shift"
            heading="Same matching, no parasite layer"
          >
            <div className="text-sm text-foreground/85 leading-relaxed space-y-3 mt-2">
              <p>
                The shift is not destruction of the platform; it is
                inversion of its ownership. Grab's engineers, drivers,
                couriers, and routing operations are the value creators.
                Inside the network's frame they are the cooperative; the
                separate corporate entity that currently captures the
                margin between rider and driver is the layer that
                dissolves.
              </p>
              <p>
                Field reading: every Grab ride is currently a{" "}
                <code className="not-italic text-foreground/80">
                  (4, GIVE)
                </code>{" "}
                glyph with a parasitic{" "}
                <code className="not-italic text-foreground/80">
                  (2, EXTRACT)
                </code>{" "}
                layer attached. Inside the network the parasitic layer is
                replaced with a transparent{" "}
                <code className="not-italic text-foreground/80">
                  (3, WITNESS)
                </code>{" "}
                routing exchange: rider, driver, the cooperative whose
                members signed the routing service's terms.
              </p>
            </div>
          </Panel>
        </article>
      </section>

      <footer className="mt-16 pt-8 border-t border-border text-sm text-muted-foreground space-y-2">
        <p>
          Public presence:{" "}
          <Link
            href="https://www.grab.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:underline"
          >
            grab.com
          </Link>
        </p>
        <p className="text-xs italic">
          This profile is the body's reflection on Grab's current shape
          and the architectural inversion the network's economy invites.
          Not a partnership claim. Anyone at Grab who finds this and
          wants to continue the conversation, the door is open.
        </p>
      </footer>
    </main>
  );
}
