---
id: lc-network
hz: 639
status: deepening
updated: 2026-04-14
type: guide
---

# The Network -- Practical Guide

> See [concept story](../concepts/lc-network.md) for the living frequency behind this work.

## What Gets Exchanged

| Category | Examples | Flow Pattern |
|----------|---------|-------------|
| **Food + seed** | Surplus grain, high-altitude herbs, kelp, preserves, greenhouse seedlings, dried herbs. Seed exchange = compounding gift | Rotates with seasons |
| **Timber + materials** | Cordwood, dimensional lumber, poles, straw bales, cob material | From accumulation to need |
| **Skills + knowledge** | Midwife attending birth 80 mi away. Natural builder's 3-wk intensive. Permaculture designer walking struggling land | Human carriers > documents |
| **Technology + fabrication** | CNC router, metal lathe, 3D printer producing replacement parts. Fabrication knowledge more valuable than any single part | On request |
| **Health + healing** | Herbalist's 60 preparations, bodywork, emergency medicine. Distributed health system -- no single node has all capability | Network holds them all |
| **Emotional + cultural** | Songs, stories, conflict practices, grief rituals, morning silence, afternoon music | The nutrients no one thinks to exchange until they arrive |

## Exchange Models

| Model | How It Works | Example |
|-------|-------------|---------|
| **Gift economy** | Give surplus without invoice. Trust the network returns what you need | Gaviotas gave water pumps, solar heaters, reforestation techniques away for decades. Surrounding villages + Gaviotas both prospered |
| **Surplus sharing pool** | 3-5 bioregional communities maintain shared monthly surplus list. Not a marketplace -- a sensing instrument | Community A: 200 kg tomatoes, 1 carpenter in March. Community B: 50 fence posts, seed potatoes. Community C: welding, surplus solar panels |
| **Traveling members** | People move between communities for seasons. GEN has facilitated 30 years | Findhorn -> Auroville: consensus techniques adapted to different cultural silence norms. Pollination, not transaction |
| **Knowledge commons** | Shared open-source knowledge base. Building techniques, crop data, water designs, health protocols | Practical Farmers of Iowa model: farmer-to-farmer data sharing, no corporation mediating |

### What Does Not Work

- Barter with ledgers (re-creates transactional mindset)
- Centralized distribution (power center)
- Obligatory contribution quotas (resentment + gaming)
- Formal trade agreements (calcifies what should be fluid)

## Sovereignty and Interdependence

### The 80/20 Split

| Produce Locally (~80%) | Flows Through Network (~20%) |
|------------------------|------------------------------|
| All staple food | Technology components (microcontrollers, solar panels, batteries, pumps) |
| All water | Specialized medicine (antibiotics, surgery, dental, vision) |
| All daily energy | Rare materials (metals, glass, certain fibers) |
| Shelter construction + maintenance | Genetic diversity (seeds, tree stock from other bioregions) |
| Primary healthcare | Deep specialist knowledge (structural engineering, complex water) |
| Education | Cultural cross-pollination |
| Culture, governance | Emergency support (fire, flood, illness overwhelming a single node) |

Auroville: 3,000 people from 50+ countries, 50 years navigating this tension. Self-reliant within a web, not self-sufficient in isolation.

![Practical exchange between communities showing a truck loaded with timber and seed boxes arriving at a community](visuals:photorealistic small flatbed truck arriving at an intentional community loaded with stacked cordwood and wooden seed boxes, five people from diverse backgrounds unloading together, community garden and earthen buildings visible in background, practical working atmosphere, late morning light, handwritten labels on seed boxes)

## Starting a Network

### Year One: Visit and Listen

Visit 5 existing communities as a working guest (at least 1 week each). Eat their food. Join their circles. Ask what they need and what they overflow with.

**Where to find communities:**

| Network | Scope | Best For |
|---------|-------|----------|
| [GEN](https://ecovillage.org/) | 10,000+ communities, 5 continental networks | Regional gatherings = 20+ connections in one place. GEN Europe, GEN Africa, CASA, GENOA |
| [ic.org](https://www.ic.org/) | Most comprehensive English-language directory | Filter by location, size, focus. Honest listings = healthiest communities |
| [WWOOF](https://wwoof.net/) | Organic farms worldwide | Visit dozens of small farms, many proto-communities |
| Bioregional gatherings | Find or create within 2-hr drive radius | Physical exchange connections that matter most |
| [Transition Network](https://transitionnetwork.org/) | 50+ countries, 1,000+ initiatives | Know every alternative project in their region |

**Budget**: GEN gathering attendance: $500-1,000 for travel + registration.

### Year Two: Form the First Triangle

Network of 2 = partnership. Network of 3 = resilient. Find 2 closest allies, ideally within a day's drive. Begin: monthly pulse updates + one exchange visit per season.

### Year Three: Expand to Five

Triangle invites 2 more nodes (pentagon). Enough redundancy that losing 1 node doesn't break the web. Bioregional surplus sharing pool becomes viable. Annual gatherings self-sustaining.

### The Gathering as Catalyst

Host a bioregional gathering: 15-30 people from 3-5 communities, long weekend on one community's land. Cook together. Walk the land. Share honestly. The gathering creates the network more than any agreement ever could.

## Inter-Community Coordination

### Decision-Making Without Bureaucracy

| Practice | How It Works |
|----------|-------------|
| **Seasonal gatherings** | Every 3 months, reps from each community meet at rotating host. Part work session, part celebration. Network-wide decisions made in person |
| **Circle practice** | Quaker clearness adapted: question in center, each person speaks once, silence between speakers. If 3 rounds don't find resonance, question returns to communities until next gathering. No votes, no quorums |
| **Shared projects** | 3 communities building shared grain mill. 2 co-hosting children's summer gathering. 5 contributing to seed library. The project IS the connection |
| **Disagreement** | Each community speaks truth. Network holds tension without forcing resolution. Stepping back happens with love, not shame. Network breathes like a forest |

### What Does Not Work

Constitutions between communities. Binding agreements with penalties. Weighted voting by size. Executive committees. Anything resembling corporate bylaws.

## Technology for Connection

### Minimum Viable Stack

| Layer | Tool | Cost | Function |
|-------|------|------|----------|
| Local mesh | LoRa nodes (ESP32 + RFM95W) | $30-50/node | Text + sensor data, 2-15 km/hop, no cell towers |
| Local network | OpenWrt mesh routers | $20-40/router | WiFi between buildings/nearby communities, 5 km line-of-sight |
| Server | Raspberry Pi 4 or mini-PC | $100-300 | Hosts wiki, messaging, dashboard. Physical object in a room you can enter |
| Knowledge | Wiki.js or markdown + Git | Free | Shared intelligence, community-owned |
| Messaging | Matrix (Synapse or Conduit) | Free | Encrypted, federated, self-hosted |
| Video calls | Jitsi Meet (self-hosted) | Free | No account, no sensing |
| Surplus board | Custom or shared spreadsheet | Free | What each community has and needs |

For communities without reliable internet: **Sneakernet** -- data syncs to USB/phone when a traveler visits, syncs back at a connected node. Delay-tolerant networking.

### What to Avoid

Slack, Discord, Google Workspace, WhatsApp -- every corporate platform is a revocable, surveilled dependency. Build the alternative: one weekend + one person who enjoys tinkering.

![A small community server room with a Raspberry Pi and router on a wooden shelf, mesh antenna visible through a window](visuals:photorealistic small wooden shelf in a community workshop holding a Raspberry Pi in a clear case with status LEDs glowing green, a mesh WiFi router, and a small UPS battery, hand-labeled ethernet cables neatly routed, a window behind showing a LoRa antenna mounted on a wooden pole outside, warm workshop lighting, practical and DIY atmosphere)

## Timeline: What We're Building

| Year | Milestone |
|------|-----------|
| **1** | Connect with 3-5 sister communities (day's drive). Monthly pulse updates. 1 exchange visit/season. Bioregional surplus list on shared wiki. LoRa mesh linking nearest 2 communities |
| **2** | First bioregional gathering on our land (3 days, 15-30 people). One shared physical project (grain mill, seed library, solar install). Knowledge base reaches critical mass |
| **3** | Triangle becomes pentagon (2 new nodes). Annual gathering self-sustaining. Traveling members regular: builder 1 month, herbalist seasonal rounds. Digital infra robust: community servers, mesh, encrypted messaging, knowledge commons |
| **5** | Network self-sustaining. Surplus flows by gradient. New communities welcomed like seedlings. Annual gathering is the highlight. The network is a forest |

## First Steps (Start Today)

1. **Visit 5 communities this year.** Use ic.org, GEN, WWOOF. "I'd like to visit for a week as a working guest."
2. **Attend a GEN gathering.** $500-1,000. Best money you spend this year.
3. **Make a bioregional map.** On paper. Draw watershed, mountains, roads. Mark every community, farm, alt project within 2 hours. You'll be surprised how many.
4. **Find your first 2 allies.** Which resonate? Visit. Propose: monthly pulse updates + one shared meal/season. Triangle = smallest resilient network.
5. **Set up one piece of sovereign digital infra.** Matrix server. Shared wiki. LoRa node. Weekend project. Declares: our connections don't depend on any corporation.
6. **Share something.** Seeds. A skill. A tool. An honest failure. The network begins with the first gift.

## Resources

- [Global Ecovillage Network](https://ecovillage.org/) -- 10,000+ communities, 5 continental networks (type: community)
- [Foundation for Intentional Community](https://www.ic.org/) -- most comprehensive directory (type: community)
- [CASA Latina](https://casa.ecovillage.org/) -- Council of Sustainable Settlements of the Americas (type: community)
- [Transition Network](https://transitionnetwork.org/) -- 1,000+ resilience initiatives in 50 countries (type: community)
- [Gaviotas](https://www.gaviotas.org/) -- Alan Weisman's account of the community that gave its innovations away (type: book)
- [New Earth MicroNation](https://newearthhorizon.com/) -- sovereign territory, natural law, zero-point economics (type: community)
- [Meshtastic](https://meshtastic.org/) -- open-source LoRa mesh firmware (type: tool)
- [Matrix.org](https://matrix.org/) -- open-source encrypted federated messaging (type: tool)
- [Wiki.js](https://js.wiki/) -- open-source wiki for community knowledge bases (type: tool)
- [OpenWrt](https://openwrt.org/) -- open-source router firmware for mesh WiFi (type: tool)
- [Open Source Ecology](https://www.opensourceecology.org/) -- 50 open-source machines for self-sufficiency (type: tool)
- [Practical Farmers of Iowa](https://practicalfarmers.org/) -- farmer-to-farmer knowledge commons model (type: community)
- [WWOOF](https://wwoof.net/) -- worldwide organic farm network, gateway to community connections (type: community)
