---
id: lc-energy
hz: 417
status: deepening
updated: 2026-04-14
---

# Energy Metabolism

> The field's metabolism. Like a mature forest: net producer. The community feels its own energy flowing.

## The Feeling

Late afternoon in January. The sun is low but the south-facing array is still pulling in current — you can feel it if you stand near the inverter shed, a faint hum that has become as familiar as your own heartbeat. Inside the common house, the thermal mass floor is warm under your socks. It absorbed six hours of winter sun through the big windows and will release that warmth slowly through the evening, into the night, like a stone pulled from a fire and tucked into a bed.

No switch was flipped. No furnace ignited. The building itself is doing what a forest canopy does — catching energy, storing it, releasing it when needed. The warmth feels different from forced-air heat. It rises from below, from the mass of the earth itself. It is patient warmth. Unhurried.

You glance at the dashboard on the common house wall. The community generated 847 kWh this week, consumed 612. The surplus flowed back into the battery, into the ground, into the grid as a gift. You are a net producer. Not because of some heroic engineering feat, but because passive solar design, good insulation, and modest living add up to a metabolism that runs cooler than industrial civilization thought possible.

The biogas digester behind the kitchen turns last night's food scraps into this morning's cooking flame. The loop is so tight you can taste it — yesterday's potato peels becoming the heat under today's soup pot. The digestate flows to the gardens as liquid fertilizer. The gardens produce the vegetables that become tomorrow's scraps.

The circle has no edge. There is no "fuel" and no "waste." There is only metabolism.

![Solar panels on south-facing rooftops with a community energy dashboard glowing in a common house window at dusk](visuals:photorealistic late afternoon winter scene of community buildings with solar panels on south-facing rooftops catching low golden sun, warm light glowing from a common house window where a colorful energy dashboard screen is visible, battery storage shed with wooden walls nearby, frost on winter garden in foreground, purple and orange dusk sky with last rays hitting the panels)

## Energy Budget for 50 People

Before sizing any system, you have to know what you actually need. The average American household uses 30 kWh per day. That number is obscene — it includes air conditioning set to 68 degrees in August, a clothes dryer running daily, an always-on entertainment system, phantom loads from dozens of plugged-in devices, and an electric water heater keeping forty gallons at 120 degrees whether anyone showers or not. A community of 50 people living with intention, passive solar design, and shared infrastructure uses a fraction of that.

Here is what 50 people actually need, broken into the loads that matter:

**Cooking** — 15-25 kWh/day electric equivalent. But most of this is handled by biogas (see below) and a wood-fired oven in the hearth kitchen. A community that cooks together uses far less energy than 50 people cooking separately. One big pot of soup on one burner versus fifty small pots on fifty burners. The communal kitchen is an energy technology. Electric backup for food processing (grain mill, blender, dehydrator) adds 5-8 kWh/day.

**Lighting** — 5-8 kWh/day. LED lighting throughout. Common spaces need more; private quarters need less. Skylights and large south-facing windows eliminate daytime lighting loads entirely. A well-designed building barely needs artificial light before sunset.

**Water pumping** — 3-6 kWh/day. A submersible well pump drawing 1,000 watts runs 3-6 hours a day to fill cisterns and gravity-feed the system. Once water is in the cisterns, gravity does the distribution work for free. If you have a spring or creek above your buildings, pumping cost drops to zero.

**Refrigeration and food preservation** — 8-12 kWh/day. Two or three large community chest freezers (chest, not upright — they lose far less cold air when opened) and two community-scale refrigerators. A root cellar maintained at 35-40 degrees handles much of what refrigerators handle in a conventional household. Fermentation and canning eliminate the need to refrigerate most preserved food.

**Workshop and tools** — 5-15 kWh/day. This varies enormously. Hand tools need nothing. A table saw draws 1,800 watts but runs in bursts. A welder draws 5,000 watts but runs minutes per day. The compressed earth block press draws 3,000 watts. The 3D printer runs overnight on 200 watts. Average it at 10 kWh/day with spikes on heavy building days.

**Communication and computing** — 3-5 kWh/day. Laptops, mesh network nodes, the community server, phones charging. All low-draw devices. The community server runs 24/7 on about 100 watts. LoRa sensor nodes run on solar and draw milliwatts.

**Laundry** — 3-5 kWh/day. Shared high-efficiency washing machines. No dryers — clotheslines and a covered drying room with good airflow. A dryer is one of the single largest energy consumers in a household. Eliminating it saves 5 kWh per load.

**Water heating** — 0-10 kWh/day electric. Most hot water comes from solar thermal and wood-fired systems (see below). Electric backup for cloudy stretches.

**Heating and cooling** — 0-20 kWh/day electric. In a well-designed passive solar building, this can be zero for eight months of the year. Rocket mass heaters handle winter. Earth-sheltered and high-thermal-mass buildings stay cool in summer without AC. Electric backup heat pumps for extreme cold snaps.

**Total realistic daily need: 50-100 kWh/day for 50 people.**

That is 1-2 kWh per person per day of electricity. The American average is 30 kWh per person per day. The difference is not deprivation — it is design. Shared infrastructure, passive systems, thermal mass, biogas, and the simple fact that people who can see their energy dashboard behave differently from people whose electricity arrives from an invisible grid and departs as an incomprehensible bill.

Peak demand matters as much as daily total. The workshop firing up the welder while the kitchen runs the grain mill while someone starts the washing machine can spike to 10-15 kW. Your inverter and battery system must handle peaks, not just averages.

## Solar — The Primary Source

Solar is the backbone. In most locations between 60 degrees north and 60 degrees south, solar provides the majority of a community's electricity. Here is how to size it.

**How much array do you need?** Take your daily consumption (75 kWh as a middle estimate) and divide by your location's peak sun hours. Peak sun hours are not daylight hours — they are the equivalent hours of full 1,000 W/m2 irradiance. Phoenix gets 6.5 peak sun hours. Portland gets 3.5. Munich gets 3.0. London gets 2.7. Nairobi gets 5.5.

For a temperate location averaging 4 peak sun hours and accounting for system losses (inverter efficiency, wiring, dust, temperature derating — typically 20-25% total loss):

75 kWh / 4 hours / 0.78 efficiency = 24 kW array

That is roughly 55-60 panels at 400-430 watts each. At standard panel dimensions (roughly 1.1m x 1.8m), you need about 120 square meters of south-facing roof or ground-mount area — less than the roof area of a single common house.

For a sun-rich location (5.5 peak sun hours), you need only 17-18 kW — about 42 panels. For a northern European location (2.7 peak sun hours), you need 35 kW — about 82 panels.

**Panel costs (2025-2026):** Wholesale panels run $0.25-0.40 per watt. A 24 kW array of panels costs $6,000-9,600 in panels alone. Racking, wiring, combiner boxes, and installation hardware add another $3,000-5,000. The panels are the cheap part now.

**Inverter sizing.** For off-grid or hybrid systems, you need inverter-chargers — units that convert DC from panels and batteries to AC, and also charge batteries from any AC source (generator, grid). Size the inverter for your peak load, not your average. A community with workshop tools needs 15-20 kW of inverter capacity. Two or three 8 kW inverter-chargers (like the Victron Quattro, Sol-Ark 15K, or Schneider XW Pro) in parallel give you redundancy — if one fails, the others carry essential loads while you repair.

Expect $4,000-8,000 per inverter-charger unit. Budget $12,000-20,000 for the inverter system.

**Battery bank.** This is the most expensive component and the one that determines whether you can truly go off-grid. You need enough storage to cover your nighttime consumption plus one to two cloudy days.

Nighttime consumption for 50 people: roughly 25-35 kWh (refrigeration, some lighting, the server, a few evening loads). One cloudy day reserve: add another 50-75 kWh. Total useful storage needed: 75-110 kWh.

Lithium iron phosphate (LiFePO4) batteries are the standard now. They handle 6,000+ cycles to 80% depth of discharge, which means 15-20 years of daily cycling. At $400-600 per kWh installed, a 100 kWh battery bank costs $40,000-60,000. This is the single largest line item.

Lead-acid batteries cost less upfront ($150-200/kWh) but last only 800-1,200 cycles at 50% depth of discharge — you will replace them every 3-5 years and they require maintenance (watering, equalization charging). Over a 20-year horizon, LiFePO4 is cheaper.

Second-life EV batteries are emerging as a middle option: $150-250/kWh for batteries with 70-80% of original capacity remaining. They require a compatible battery management system but can cut storage costs significantly.

**Ground mount vs roof mount.** Ground-mounted arrays are easier to clean, easier to access for repair, can be optimally angled for your latitude, and can be built by the community without anyone working at height. They do take up land. A 24 kW ground-mount array needs about 150 square meters — a plot roughly 10m x 15m. Roof mount saves land but requires structural assessment and makes maintenance harder. For a community with land, ground mount is usually the better choice.

**DIY vs professional installation.** The panels, racking, and wiring are straightforward — many communities do this themselves. The critical parts requiring licensed electricians in most jurisdictions: the connection between inverter and main panel, any grid-tie interconnection, and the battery bank wiring (high-current DC is more dangerous than AC). Budget for a licensed electrician to do the final connections and inspection. Everything else, a team of four people with basic tools can install in a week.

**Maintenance.** Solar panels have no moving parts. Wash them twice a year (or let the rain do it in wet climates). Check wiring connections annually. Inverters last 10-15 years; budget for replacement. Batteries need monitoring — a good battery management system (BMS) handles this automatically and alerts you to any cell imbalance. The Libre Solar open-source BMS is a real option for the technically inclined.

![Community solar array ground-mounted in a meadow with battery shed and people maintaining panels](visuals:photorealistic ground-mounted solar panel array of about 60 panels in neat rows on a green meadow, small wooden battery storage shed with open door showing battery racks inside, two people cleaning panels with soft brushes and water, community buildings with living roofs visible in background, wildflowers growing between panel rows, clear blue sky, practical and beautiful installation)

## Wind — The Night Shift

Solar produces nothing at night and little in winter at high latitudes. Wind often peaks at night and in winter — the complementary pattern. A wind turbine paired with solar smooths your generation curve and reduces the battery storage you need.

**When wind makes sense.** You need average wind speeds above 5 m/s (11 mph) at hub height. Hilltops, ridgelines, coastal sites, and open plains work. Forested valleys and sheltered inland sites usually do not. Before investing, install an anemometer at your proposed turbine height for at least six months — ideally a full year. Wind data from the nearest airport or weather station gives a rough indication but local terrain effects can double or halve wind speeds over short distances.

**Small turbine sizing.** A quality small wind turbine in the 5-10 kW range — Bergey Excel 15, Xzeres 442, or the open-source designs from Hugh Piggott — produces 500-1,500 kWh per month in a good wind site. That is 15-50 kWh per day, enough to cover nighttime loads and reduce your solar/battery requirement significantly.

A 10 kW turbine on a 30-meter tower costs $30,000-50,000 installed, including tower, foundation, wiring, and charge controller. The tower is often half the cost — do not skimp on it. A turbine on a short tower in turbulent air produces little energy and wears out fast.

**Hugh Piggott's designs** are built by hand from wood, steel, and permanent magnets. Hundreds of communities worldwide have built them in workshop courses. The materials cost $2,000-4,000. The labor is the community's own. They are not as efficient as commercial turbines, but they are repairable with local skills and local materials, which matters more than peak efficiency when your nearest dealer is 500 kilometers away.

**Maintenance.** Wind turbines have moving parts — bearings, blades, yaw mechanisms. Expect annual inspection and occasional bearing replacement. Budget $500-1,000 per year for parts and maintenance on a small turbine. A well-maintained turbine lasts 20-25 years. The tower lasts longer than the turbine.

**The complementary pattern.** In most temperate climates, solar peaks June-August, wind peaks November-March. A system with both sources can be sized smaller in total because the generation curves overlap less. A community that would need 110 kWh of battery storage with solar alone might need only 60-70 kWh with solar plus wind — saving $15,000-25,000 in batteries.

## Biogas — Closing the Kitchen Loop

A biogas digester turns organic waste into methane-rich gas and liquid fertilizer. It is the tightest energy loop a community can build: food scraps from dinner become cooking gas for breakfast, and the digestate feeds the garden that grows tomorrow's dinner.

**What goes in.** Kitchen scraps, garden waste, animal manure (goat, chicken, cow, pig — not dog or cat), crop residues, and spoiled food. A community of 50 people with a kitchen garden and some animals produces 50-100 kg of feedstock per day.

**What comes out.** Biogas is roughly 60% methane and 40% CO2. One kilogram of food waste produces about 0.1-0.2 cubic meters of biogas. One cubic meter of biogas provides roughly 6 kWh of thermal energy — equivalent to about half a liter of propane. Fifty kilograms of feedstock per day yields 5-10 cubic meters of gas, or 30-60 kWh of thermal energy.

In practical terms: enough gas for 3-5 hours of cooking on a standard burner per day. For a community kitchen cooking two main meals a day, biogas covers the stovetop work. Baking and heavy cooking can be supplemented by the wood-fired oven.

**The digestate** is liquid gold. Rich in nitrogen, phosphorus, and potassium, biologically active, and immediately plant-available. It flows directly to the raised beds and food forest as a free, continuous supply of liquid fertilizer. A community with a biogas digester can reduce or eliminate purchased fertilizer inputs.

**How to build one.** The simplest proven design is the IBC tote digester developed by Solar CITIES. Two 1,000-liter IBC totes (the kind that ship bulk liquids — available used for $50-100 each) connected by pipes. Feedstock goes in one end, gas collects at the top, digestate overflows from the other end. Total materials cost: $300-600. Build time: a weekend. It works in any climate where temperatures stay above 15 degrees Celsius, or where you can insulate and heat the digester.

For colder climates, an insulated underground digester maintains temperature through earth coupling. A 6-cubic-meter underground digester (built from reinforced concrete or a buried insulated tank) costs $2,000-5,000 and produces gas year-round in climates down to -20 degrees Celsius, because soil temperature at 2 meters depth stays above 8-10 degrees even in deep winter. A small heating loop from a solar thermal panel or rocket mass heater exhaust keeps the digester in its optimal 35-40 degree range.

Larger fixed-dome digesters (the Indian Deenbandhu or Chinese design, built from brick and cement) handle the full waste stream of a 50-person community with animals and cost $3,000-8,000 to build. They last 20-30 years with minimal maintenance.

**Safety.** Methane is flammable. Biogas systems need proper piping (rated for gas), a flame arrestor at the burner, and a pressure relief valve. These are simple, well-understood safety measures. Thousands of household and community digesters operate safely worldwide. The technology is older than electricity.

![Cross-section diagram of a biogas digester system showing input, gas collection, digestate output, and connection to kitchen](visuals:photorealistic cutaway view of an underground biogas digester system showing insulated concrete chamber with feedstock inlet pipe from above, gas collection dome at top with pipe leading to a kitchen building, liquid digestate overflow pipe leading to garden beds, thermometer showing internal temperature, layers of soil and insulation visible in cross-section, person adding kitchen scraps at inlet, garden with healthy plants receiving digestate, educational and clear)

## Heating and Cooling — The Biggest Energy Question

In most climates, space heating and cooling consume more energy than everything else combined. Industrial civilization solves this by burning fossil fuels or running massive compressors. A living community solves it by building correctly in the first place.

**Passive solar design** is not a technology — it is orientation. A building with its long axis running east-west, with large south-facing windows (north-facing in the southern hemisphere), roof overhangs sized to admit winter sun and block summer sun, and 30-60 cm of thermal mass in floors and walls will maintain comfortable temperatures through most of the year in most climates without any active heating or cooling system. The Passivhaus standard proves this at industrial scale — buildings that need 90% less heating energy than conventional construction, verified in climates from Scandinavia to Japan.

The key numbers: R-40 walls (30 cm of straw bale or double-wall construction), R-60 roof, R-20 foundation, triple-pane south-facing windows, airtight construction with heat-recovery ventilation. A building meeting these specifications in a temperate climate (4,000 heating degree days) needs only 15 kWh per square meter per year of heating energy — about one-tenth of a conventional building.

**Rocket mass heaters** for the heating that remains. A rocket mass heater burns wood at 800-1,000 degrees Celsius in an insulated combustion chamber, driving hot exhaust through a long thermal mass bench or floor before exiting through the chimney. The thermal mass absorbs the heat and radiates it for 12-24 hours after the fire goes out. They burn 80% less wood than a conventional woodstove because the combustion is so complete — the exhaust is mostly water vapor and CO2, with almost no particulates or creosote.

A single rocket mass heater with a 5-meter thermal mass bench heats 60-80 square meters of well-insulated space. The common house needs two or three. Each one burns 5-10 kg of small-diameter wood per firing — branches, mill scraps, coppiced wood from the property. One hectare of managed coppice woodland produces enough wood to heat a 50-person community in a cold climate indefinitely, because coppiced trees regrow from the stump every 5-7 years. The fuel supply is renewable on a human timescale.

Erica and Ernie Wisner's book and workshop plans provide complete construction details. A skilled team of four builds one in a week from firebrick, cob, and salvaged materials. Cost: $200-800 in materials.

**Earth-sheltered buildings** stay cool without air conditioning. Earth temperature at 2 meters depth is roughly the annual average air temperature of your location — 10-15 degrees in temperate climates, 20-25 degrees in the tropics. An earth-sheltered building with its north, east, and west walls buried into a hillside maintains 18-22 degrees year-round with minimal heating or cooling input. The south face opens to the sun for passive solar gain, light, and ventilation.

**For cooling without AC:** thermal mass (rammed earth, cob, stone floors) absorbs daytime heat and releases it at night. Night ventilation — opening the building to cool night air and closing it at dawn — flushes accumulated heat. A solar chimney (a dark-painted vertical shaft on the south side of the building) creates a convective draft that pulls cool air through earth tubes buried at 2 meters depth, delivering air at near-ground-temperature without any electrical input. Earth tube cooling delivers 2-4 degrees Celsius of cooling in dry climates and 4-8 degrees in humid climates.

Shade. Deciduous trees on the south and west sides of buildings provide shade in summer and allow sun through in winter after leaves drop. A mature deciduous tree reduces summer cooling loads by 25-40% on the side it shades. This is a three-year investment that compounds forever.

**For extreme cold (below -20 degrees Celsius):** passive solar and rocket mass heaters still form the core. Add a small air-source or ground-source heat pump for backup — a modern cold-climate heat pump (Mitsubishi Hyper-Heat, Fujitsu XLTH) operates down to -25 degrees and delivers 2-3 kWh of heat per kWh of electricity consumed. A 5 kW heat pump for the common house backup costs $3,000-5,000 installed and draws from the solar/battery system. This is not dependence on industrial technology — it is a bridge for the coldest weeks, the way a forest drops its leaves to survive winter.

![Interior of a common house with a rocket mass heater bench where people gather, warm earthen walls, south-facing windows with low winter sun streaming in](visuals:photorealistic interior of community common house with a long curved cob thermal mass bench built around a rocket mass heater with small fire visible in firebox, five people sitting and lounging on the warm bench reading and talking, thick rammed earth walls in warm tones, large south-facing windows with low angle winter sunlight streaming across an earthen floor, wool blankets draped over bench, tea mugs on a wooden ledge, deeply warm and inviting atmosphere)

## Water Heating — Hot Water for 50 People

Hot water is the second-largest thermal load after space heating. Fifty people showering, washing dishes, and doing laundry need 1,500-2,500 liters of hot water per day. Heating that electrically would consume 50-80 kWh/day — more than the entire rest of the community's electrical load combined. Do not heat water with electricity if you can possibly avoid it.

**Solar thermal** is the primary solution. Evacuated tube collectors are 60-70% efficient — far more efficient than PV panels at converting sunlight to useful energy when that energy is heat. A 30-tube evacuated tube collector produces 5-8 kWh of thermal energy per day in a temperate climate. Eight to twelve collectors (total cost $4,000-8,000) feeding a 2,000-3,000 liter insulated storage tank provide 80-95% of hot water needs from April through October in most temperate locations.

Flat plate collectors are simpler, cheaper ($200-400 each), and last 30+ years with almost no maintenance. They are less efficient in cold weather than evacuated tubes but more robust. In Mediterranean and tropical climates, flat plate collectors are sufficient year-round.

**The insulated storage tank** is critical. A well-insulated 3,000-liter tank (200mm of mineral wool or polyurethane foam) loses only 1-2 degrees per day. This means hot water produced on a sunny day is still warm two days later. Stratification within the tank keeps the hottest water at the top where it is drawn off, and the coolest at the bottom where it returns from collectors. A properly stratified tank is an engineering marvel that uses no energy — just physics.

**Wood-fired batch heaters** cover the gap. A simple batch heater — a 200-liter insulated tank with a firebox beneath it — heats water to 70 degrees in 2-3 hours using 5 kg of wood. A community bathhouse with a wood-fired boiler is both practical infrastructure and a social space. The Japanese tradition of communal bathing (sento) and the Finnish sauna tradition both understood this: heating water is an occasion for gathering.

**Heat recovery.** Greywater from showers exits at 30-35 degrees. A drain-water heat recovery unit (a simple copper coil wrapped around the drain pipe) preheats incoming cold water, recovering 40-60% of the heat that would otherwise go down the drain. Cost: $300-500 per installation. Payback: immediate and perpetual.

**Biogas backup.** A biogas-fired instantaneous water heater provides hot water on demand during cloudy winter stretches. The biogas digester produces gas continuously; a fraction diverted to water heating covers the solar thermal gap without any fossil fuel input.

## How It Lives Here

Saturday morning, the energy circle meets. Not engineers — a retired teacher, a teenager who built her first Arduino at twelve, a carpenter, and the cook. They read the weekly numbers together the way a family reads a letter. Generation, consumption, storage, surplus. The teenager notices the workshop drew more than usual — someone left the compressor running overnight. No blame. Just awareness. The system becomes visible, and visibility changes behavior without anyone needing to enforce rules or post signs or threaten consequences.

The biogas digester is the most beloved piece of infrastructure on the property. Everyone calls it "the stomach." It is fed twice daily — kitchen scraps, garden waste, occasionally goat manure. In return it produces four hours of cooking gas and a rich liquid fertilizer that goes straight to the raised beds. The children understand the loop instinctively. When visitors ask "where does your energy come from?" the cook points at the compost bucket and says "dinner." The visitor looks confused. The cook smiles.

The rocket mass heater in the common house burns eighty percent less wood than the old woodstove it replaced. It combusts so completely that the exhaust is mostly steam. The thermal mass bench stays warm for twelve hours after the fire goes out. On winter evenings, people gather on the bench the way cats gather on a warm engine. The heater does not just warm the room. It creates a gathering place. The energy system shapes the social life as much as the social life shapes the energy use.

![A biogas digester next to a community kitchen, person adding scraps, pipes leading to stove, garden beds fertilized with digestate](visuals:photorealistic biogas digester system beside an earthen community kitchen building with clay walls, person in apron adding food scraps to inlet pipe, visible plumbing connecting through wall to indoor stove, raised garden beds nearby with rich dark soil fertilized with digestate, chickens foraging, morning light with steam rising from kitchen chimney, practical and alive)

## Sovereignty vs Exchange

Not all energy independence is worth pursuing. The question is not "can we generate everything ourselves?" but "what gives us sovereignty — the ability to make our own choices about how we live?"

**Full sovereignty systems** — things worth owning completely:

Cooking energy. Biogas and wood give you cooking fuel that no utility can price, ration, or cut off. A community that cannot cook independently is not sovereign. This is the first system to secure.

Heating. Passive solar design, rocket mass heaters, and coppiced firewood mean your warmth depends on the sun and the trees on your land. No gas pipeline. No propane delivery truck. No price spikes in January.

Water pumping. A solar-powered well pump with a gravity-fed cistern system means water flows even during grid outages, storms, and price hikes. Water sovereignty is energy sovereignty.

Lighting and communication. A modest solar/battery system covering lights, phones, laptops, and the mesh network means you are never in the dark and never disconnected. This is the minimum viable energy system.

**Where grid connection makes sense:**

If the grid is available and net metering is offered, a grid-tie connection can serve as a giant free battery. Export surplus solar during the day, draw back at night. This eliminates or greatly reduces your battery bank — saving $40,000-60,000 in the most expensive component. The grid becomes a buffer, not a dependency.

The tradeoff is real: grid-tied systems shut down during grid outages (by code requirement, to protect line workers) unless you have a hybrid inverter with transfer switch and battery backup. A hybrid system — grid-tied with battery backup for essential loads — gives you the economic benefit of net metering with the sovereignty of islanding during outages. This is the pragmatic middle path for most communities in their first years.

**When to cut the cord entirely.** If you are rural and the cost of running grid power to your site exceeds $20,000-30,000 (the utility charges per-pole for line extension, often $5,000-15,000 per pole), the economics of off-grid solar/battery/wind beat the grid on day one. Many of the best community land sites are rural enough that grid connection was never the cheaper option.

**The sovereignty gradient:** Start grid-tied if the grid is there. Oversize your solar. Build battery capacity gradually as prices continue falling. Shift loads to daytime (run the washing machine and workshop tools when the sun is up). As your battery bank grows and your biogas/wood systems mature, your grid draw approaches zero. At some point you realize you have not imported a kilowatt-hour in three months. The grid connection becomes insurance, not sustenance. That is sovereignty — not a dramatic cut-off, but a gradual realization that you have been feeding yourself all along.

## First Year Energy Plan — Minimum Viable Metabolism

You cannot build everything at once. Here is what to install first, what to add when, and what it costs, so that the community has power from day one and grows toward full sovereignty over five years.

**Month 1-2: Light and Water ($8,000-15,000)**

The absolute minimum: a 3-5 kW solar array (8-12 panels), one 5 kW hybrid inverter, and a 10-15 kWh battery bank. This powers LED lighting for all buildings, charges phones and laptops, runs the community server, and — critically — powers the well pump to fill cisterns during the day. Add a small DC-powered pressure pump for water distribution.

This system costs $8,000-15,000 fully installed. It does not run the workshop, the kitchen appliances, or any heating. But it means you are never in the dark, you always have water, and you can communicate. It is the heartbeat of the energy system — everything else is muscle and organ added to this core.

If the grid is available, connect it now as backup. The monthly cost will be minimal because your loads are small.

**Month 3-4: Cooking ($500-2,000)**

Build the biogas digester. The IBC tote design takes a weekend and costs $300-600. It needs 4-6 weeks to establish its microbial culture before it produces gas reliably. Feed it daily from kitchen scraps and any animal manure. Within two months you have cooking gas.

Simultaneously, build or commission the wood-fired oven for the hearth kitchen. Cob oven: $200-500 in materials, built in a weekend by the community. This handles bread, roasts, and slow-cooked meals. Between biogas and wood, your cooking is sovereign before summer.

**Month 4-8: Hot Water ($3,000-6,000)**

Install solar thermal collectors and a stratified storage tank. Eight evacuated tube collectors and a 2,000-liter insulated tank. Plumb it to the kitchen and a bathhouse. From spring through fall, you have free hot water for 50 people. A wood-fired batch heater covers cloudy days and winter.

**Month 6-12: Scale Solar, Add Battery ($25,000-50,000)**

Expand the solar array to full capacity (20-30 kW). Add battery storage in stages — start with 30-40 kWh and expand as budget allows. Each additional 10 kWh of LiFePO4 storage costs $4,000-6,000 but buys another 3-4 hours of autonomy after dark.

At this point the community runs on solar for all electrical loads during the day and has enough battery to cover evening and night. The grid (if connected) fills any gaps. The workshop operates during sunny hours.

**Year 2: Wind and Heat ($20,000-50,000)**

If your site has wind, install a 5-10 kW turbine. This fills the winter and nighttime solar gap. If your site lacks wind, invest the same money in additional battery storage.

Build rocket mass heaters in every common space before the second winter. Materials: $200-800 each, mostly labor. This is a community building project — a week per heater, and the knowledge transfers so each one is faster.

**Year 3-5: Surplus and Sovereignty ($10,000-30,000)**

Expand battery bank to full autonomy (80-110 kWh). Add micro-hydro if you have a stream (even a small one — 500 watts continuous from a 3-meter head and modest flow generates 12 kWh/day, 365 days a year, rain or shine, day or night). Build the underground biogas digester for year-round gas production. Install drain-water heat recovery. The system is now complete and net-producing.

**Total five-year energy investment: $65,000-150,000 for 50 people.** That is $1,300-3,000 per person for a lifetime of energy sovereignty. An American household spends $2,000-3,000 per year on energy. The community system pays for itself in one to two years per person and then produces free energy for decades.

## Climate Adaptations

Energy needs are not universal. A community in Norway and a community in Costa Rica face opposite problems and need different solutions. The principles are the same — sovereignty, passive design, closed loops — but the expression is radically different.

**Heating-dominated climates (Northern Europe, Canada, Northern US, mountain regions)**

The challenge: 5-7 months of heating season, short winter days (6-8 hours of weak sunlight), long cold nights. Heating is 60-70% of total energy demand.

The response: Superinsulated buildings are non-negotiable — R-40 walls minimum, R-60 roof, triple-pane windows, airtight construction with heat-recovery ventilation. Passive solar gain through large south-facing windows sized for winter sun angle. Thermal mass floors and walls to store what sun there is. Rocket mass heaters for the deep cold months. Ground-source heat pumps where electricity is available (coefficient of performance 3-4 even at -15 degrees ground temp).

Wind is strong in winter when you need it most. A wind turbine is worth more here than in any other climate. Oversize your wind capacity and use surplus winter wind power for heat pump operation.

Solar thermal with a large insulated tank (4,000-5,000 liters) and evacuated tube collectors extends the hot water season. A wood-fired boiler backs up solar thermal in the darkest months.

Firewood budget: 3-5 cords per dwelling per winter with rocket mass heaters (vs 8-12 cords with conventional woodstoves). A 2-3 hectare coppice woodland produces this sustainably.

Biogas digesters need underground insulated construction with a heating loop to maintain 35 degrees through winter. Worth the extra investment — winter is when you need the cooking gas most and when the compost pile stops working.

**Cooling-dominated climates (Tropics, subtropics, desert)**

The challenge: 8-12 months of cooling demand. Abundant solar energy but temperatures that make unshaded buildings unbearable. Humidity compounds heat in tropical regions. Heating demand is negligible or zero.

The response: Building orientation, shading, and ventilation matter more than any active system. Deep verandas and wide overhangs shade walls from direct sun. Light-colored roofs and walls reflect heat. High ceilings with operable clerestory windows create stack-effect ventilation — hot air rises and exits high while cool air enters low.

Earth-sheltered construction is supremely effective. Underground or earth-bermed buildings maintain 24-26 degrees year-round in tropical climates. Earth tubes deliver cooled air without any electricity.

Cross-ventilation through carefully placed openings can lower perceived temperature by 3-5 degrees. Courtyard designs create microclimates where plants and water features cool the air through evapotranspiration.

Solar is abundant — a 15-18 kW array is sufficient for 50 people because there are no heating loads. Battery needs are smaller because solar hours are long and consistent year-round. A 40-60 kWh battery bank covers nighttime loads comfortably.

Biogas digesters work at peak efficiency in warm climates — no insulation or heating needed. Gas production is year-round and consistent.

Water heating requires minimal infrastructure — a simple thermosiphon solar water heater (black-painted tank on the roof) provides hot water with no pump and no controller. Cost: $100-300 per unit.

The enemy is humidity, not temperature. Ventilation, dehumidification through desiccant systems or earth tube cooling, and mold-resistant natural materials (lime plaster, bamboo) are essential.

**Balanced climates (Mediterranean, temperate coastal, highland tropical)**

The gift: mild winters, warm summers, no extreme of either. The energy budget is smallest here.

Four-season passive solar design works beautifully. Moderate thermal mass, good insulation (R-25 walls, R-40 roof), south-facing orientation. Rocket mass heaters for the few cold months. Natural ventilation for summer. Solar thermal provides hot water 9-10 months of the year.

A 20-22 kW solar array with a 60-80 kWh battery bank achieves full off-grid capability. Wind is optional but helpful for winter gap-filling.

These are the climates where community energy sovereignty is easiest and cheapest. If you are choosing a location and energy independence matters to you, Mediterranean and temperate coastal climates offer the gentlest path.

**Arid climates (high desert, steppe)**

Extreme temperature swings — hot days, cold nights — are actually an advantage for thermal mass buildings. Thick rammed earth or adobe walls absorb daytime heat and release it at night, moderating both extremes. A 50 cm rammed earth wall can shift the temperature peak by 10-12 hours, so the wall is releasing its warmth at midnight when you need it and absorbing heat at noon when you want to be cool.

Solar is excellent — 5-7 peak sun hours, few clouds. But dust is a real maintenance issue. Panels need washing monthly in dusty environments. Water for washing panels must be budgeted — a real consideration in arid climates.

Evaporative cooling works in dry heat. A simple evaporative cooler (wet pads with a fan) can drop air temperature by 10-15 degrees when humidity is below 30%. This uses water, not electricity. Combined with earth tubes and thermal mass, it eliminates the need for compressor-based AC.

Wind is often strong in arid regions, especially at ridgelines and passes. A wind turbine complements solar well here — wind often picks up in the afternoon and evening as thermal convection builds.

## What Nature Teaches

A mature forest is a net producer. It generates more oxygen than it consumes, stores more carbon than it releases, retains more water than it sheds, builds more soil than it loses. It does this not through efficiency but through integration — every output becomes someone else's input. Dead leaves feed fungi. Fungi feed roots. Roots feed trees. Trees feed leaves. The metabolism has no waste stream because there is no "away."

Everything cycles. Everything nourishes something else. The forest does not try to be efficient. It tries to be complete.

A human body at rest generates about a hundred watts of heat. Twenty people in a room generate two kilowatts — enough to noticeably warm a well-insulated space. The oldest heating system in the world is gathering. The passive solar house simply extends this ancient principle: let the sun in, keep the warmth close, release it slowly.

The insulated wall does what fur does. The south-facing window does what a flower does, turning toward the light. The thermal mass floor does what a sun-warmed rock does — stores heat when there is too much and releases it when there is too little. None of this is technology in the modern sense. It is architecture remembering that it lives inside a star's energy field.

## Where You Can See It

Samso Island, Denmark. Four thousand people. They decided in 1997 to become energy self-sufficient. Not the government — the people. A farmer named Jorgen Tranberg put up the first wind turbine on his own land because he thought it was the right thing to do. His neighbors followed. Within a decade the island was producing more energy than it consumed, exporting the surplus.

The turbines are community-owned. The profits stay on the island. Energy sovereignty became economic sovereignty became cultural pride. Nobody tells the people of Samso what to do with their energy, because it is theirs. They can see the turbines from their kitchen windows. The energy is not abstract. It is visible, local, understood.

At Barefoot College in Tilonia, Rajasthan, grandmothers from rural villages across Africa and Asia learn to install and maintain solar systems. Not engineers. Grandmothers. They return home and electrify their villages. The knowledge stays local. The dependency on distant grids and foreign technicians dissolves.

At El Hierro in the Canary Islands, wind and hydroelectric power run the entire island — a closed system, self-sufficient, community-governed. The pattern is always the same: sovereignty begins when you can feel your own metabolism.

Earthaven Ecovillage in North Carolina has operated off-grid since 1994. Sixty people on 329 acres. Individual solar systems on each dwelling plus community micro-hydro on a creek. They have lived the learning curve — undersized batteries in year one, generator dependence in year three, gradual expansion to surplus by year eight. Their honest accounting of mistakes is more valuable than any success story.

Findhorn Foundation in Scotland runs a community-owned wind turbine that generates more electricity than the community uses. The surplus powers neighboring homes. They went from being criticized for their electricity bills to being net exporters — the same arc every community follows when it takes its own metabolism seriously.

![Wind turbines on a green coastal island landscape with village buildings and agricultural fields, ocean in background](visuals:photorealistic community-owned wind turbines on green rolling coastal hills of a small island, colorful village houses clustered below, agricultural fields and pastures in foreground, deep blue ocean stretching to horizon in background, bright cloudy sky with dramatic light, sense of energy independence and community self-sufficiency)

## Energy Systems at Scale

**50 people:** One community solar array (20-30 kW), one battery bank (80-110 kWh), one biogas digester, rocket mass heaters in common spaces, solar thermal for hot water, one wind turbine if site permits. All systems maintained by a rotating energy circle of 3-5 people. Total infrastructure: $65,000-150,000. Everyone can see the dashboard, everyone understands the numbers.

**100 people:** Two clusters, each with its own solar array and battery bank, connected by a shared DC bus or AC microgrid. The biogas digester scales up to a fixed-dome design handling double the feedstock. A second wind turbine if the site supports it. The energy circle expands to 6-8 people with specialized knowledge emerging naturally — someone becomes the battery person, someone becomes the biogas person. Not assigned roles — callings that emerge from interest and aptitude. Total: $120,000-280,000.

**200 people:** A true microgrid with multiple generation sources, distributed storage, and intelligent load management. At this scale, a community energy system starts to resemble a small utility — but community-owned, transparent, and governed by the people it serves. Micro-hydro becomes proportionally more valuable because it provides baseload. A biogas system at this scale can generate electricity via a small combined heat and power unit, not just cooking gas. The energy circle may birth a small enterprise that maintains neighboring communities' systems. Total: $220,000-500,000.

## Resources
- [Open Source Ecology - GVCS](https://www.opensourceecology.org/gvcs/) — 50 open-source industrial machines including power systems at 1/8th cost
- [OSE Solar Energy Construction Set](https://wiki.opensourceecology.org/wiki/Open_Source_Solar_Energy_Construction_Set) — open-source PV, thermal, and solar hydrogen systems
- [Libre Solar Project](https://libre.solar/) — open-source MPPT charge controllers and battery management
- [Solar CITIES Biodigester](https://www.appropedia.org/Open_Source_Solar_CITIES_biodigestor_system) — open-source IBC tote biogas system
- [ATTRA Micro-Scale Biogas Guide](https://attra.ncat.org/publication/micro-scale-biogas-production-a-beginners-guide/) — beginner's guide to small-scale anaerobic digestion
- [DOE Microhydropower Guide](https://www.energy.gov/energysaver/planning-microhydropower-system) — US DOE guide to micro-hydro planning and installation
- [Appropedia Energy Portal](https://www.appropedia.org/) — open wiki with 3000+ articles on appropriate energy technology
- [Hugh Piggott Wind Turbine Plans](https://scoraigwind.co.uk/) — hand-built wind turbine designs, workshop schedules, and construction manuals
- [Erica and Ernie Wisner - Rocket Mass Heaters](https://www.ernieanderica.info/) — definitive resource for rocket mass heater design and construction
- [Passive House Institute](https://passivehouse.com/) — building standard for superinsulated, minimal-energy construction
- [Victron Energy System Design](https://www.victronenergy.com/information/system-design) — off-grid and hybrid inverter/battery system sizing guides
- [Andy Wekin - IBC Biodigester Build](https://www.youtube.com/watch?v=qlta6F-XHBQ) — step-by-step video of the Solar CITIES IBC tote biogas system
- [Earthaven Energy Report](https://www.earthaven.org/) — 30 years of real-world off-grid community energy data and lessons learned

## The Questions That Live Here

- How do you handle the winter solar deficit in temperate climates without falling back on the grid as a crutch?
- What is the right balance between energy independence and maintaining a grid connection as safety net?
- How do you train every community member — not just the technically inclined — to understand and feel the metabolism?
- When does energy surplus become generosity — and what does a community do with more than it needs?
- At what point does community battery storage become cheaper than grid connection — and how fast is that threshold moving?
- How do you finance $65,000-150,000 of energy infrastructure when the community is just starting and cash is scarce? Phased installation? Cooperative lending? Sweat equity offset?
- What is the minimum viable energy literacy every member needs — and what is the best way to teach it?
- How do you design an energy system that a community can maintain for 30 years without depending on any single person's expertise?
- What happens when the teenager who built the monitoring system grows up and leaves?

## Connected Frequencies
→ lc-nourishing, lc-land, lc-v-shelter-organism, lc-v-living-spaces, lc-instruments, lc-circulation
