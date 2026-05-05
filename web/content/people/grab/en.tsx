import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Grab — Inside the Network's Lens | Coherence Network",
    description:
      "What Grab's ride-hailing, food-delivery, and payments work looks like inside a sovereignty-everywhere economy. The matching function survives; the extractive layer dissolves.",
  },
  breadcrumbName: "Grab",
  hero: {
    background:
      "radial-gradient(120% 80% at 85% 15%, hsl(var(--primary) / 0.32) 0%, transparent 55%), " +
      "radial-gradient(110% 80% at 10% 90%, hsl(var(--chart-2) / 0.30) 0%, transparent 60%), " +
      "linear-gradient(135deg, hsl(var(--background)) 0%, hsl(var(--card)) 50%, hsl(var(--background)) 100%)",
    overlayClass:
      "absolute inset-0 bg-gradient-to-t from-background via-background/85 to-background/20",
    eyebrow: "Service provider — Southeast Asia",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Grab",
    welcome: (
      <p>
        Every ride in Ubud, every QR-payment at a warung, every food
        order across eight countries — the matching layer this body
        uses daily. Held here with appreciation, and rendered through
        the network's lens as a quiet thinking-aloud about what the
        same service would look like as a cooperative.
      </p>
    ),
  },
  facts: [
    {
      label: "Footprint",
      value: "Southeast Asia, eight countries, hundreds of cities",
    },
    {
      label: "Where the body meets it",
      value:
        "Daily — every Grab ride in Ubud, every food order, every QR-payment is a sovereign exchange currently rendered as transaction",
    },
    {
      label: "Field",
      value: "Matching · routing · payments · logistics",
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        Grab is not a member of this network and has not been invited
        into a partnership. This page is the body's reflection on
        Grab's work as we use it daily — a thinking-aloud about what
        the same function looks like under sovereignty-everywhere
        economics. If anyone at Grab finds this page and wants to
        continue the conversation, the door is open.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "What Grab does",
      body: (
        <>
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
        </>
      ),
    },
    {
      kind: "narrative",
      heading: "What Grab currently extracts",
      body: (
        <>
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
        </>
      ),
    },
    {
      kind: "narrative",
      heading: "What Grab looks like inside the network",
      body: (
        <>
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
        </>
      ),
    },
    {
      kind: "panel",
      variant: "cool",
      eyebrow: "The architectural shift",
      heading: "Same matching, no parasite layer",
      body: (
        <>
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
        </>
      ),
    },
  ],
  footer: (
    <>
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
    </>
  ),
};

export default content;
