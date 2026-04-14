---
id: lc-energy
hz: 417
status: deepening
updated: 2026-04-14
type: guide
---

# Energy Metabolism -- Practical Guide

> See [concept story](../concepts/lc-energy.md) for the living frequency behind this work.

## Energy Budget for 50 People

Community living = 1-2 kWh/person/day electricity (vs 30 kWh American average). The difference is design, not deprivation.

| Load | kWh/day | Notes |
|------|---------|-------|
| Cooking (electric backup) | 5-8 | Most cooking via biogas + wood-fired oven |
| Lighting (LED) | 5-8 | Skylights + south windows eliminate daytime loads |
| Water pumping | 3-6 | Submersible pump fills cisterns; gravity distributes |
| Refrigeration/preservation | 8-12 | Community chest freezers + root cellar handles most |
| Workshop/tools | 5-15 | Hand tools need nothing; power tools run in bursts |
| Communication/computing | 3-5 | Laptops, server (100W 24/7), phones, mesh nodes |
| Laundry | 3-5 | Shared HE washers, no dryers (clotheslines) |
| Water heating (backup) | 0-10 | Most from solar thermal + wood |
| Heating/cooling (backup) | 0-20 | Passive solar + rocket mass heaters handle most |
| **Total** | **50-100** | **Peak demand: 10-15 kW (workshop + kitchen + laundry)** |

## Solar -- The Primary Source

### Array Sizing

Daily need (75 kWh middle estimate) / peak sun hours / 0.78 efficiency = array size

| Location | Peak Sun Hours | Array Needed | Panels (~420W) |
|----------|---------------|-------------|----------------|
| Phoenix | 6.5 | 15 kW | ~36 |
| Nairobi | 5.5 | 18 kW | ~42 |
| Generic temperate | 4.0 | 24 kW | ~57 |
| Portland | 3.5 | 28 kW | ~66 |
| Munich | 3.0 | 32 kW | ~76 |
| London | 2.7 | 36 kW | ~85 |

24 kW array = ~120 sqm south-facing area (ground or roof mount).

### Costs (2025-2026)

| Component | Cost | Notes |
|-----------|------|-------|
| Panels (24 kW) | $6K-9.6K | Wholesale $0.25-0.40/W |
| Racking, wiring, combiners | $3K-5K | |
| Inverter-chargers (2-3 x 8 kW) | $12K-20K | Victron Quattro, Sol-Ark 15K, or Schneider XW Pro. Size for peak load 15-20 kW |
| **Total solar system** | **$21K-35K** | Before batteries |

### Battery Bank

| Option | $/kWh | Cycles | Lifespan | 100 kWh Cost |
|--------|-------|--------|----------|-------------|
| LiFePO4 | $400-600 | 6,000+ at 80% DoD | 15-20 yr | $40K-60K |
| Lead-acid | $150-200 | 800-1,200 at 50% DoD | 3-5 yr | $15K-20K (replace 4-5x) |
| Second-life EV | $150-250 | Varies (70-80% original) | 8-12 yr | $15K-25K |

Nighttime consumption: 25-35 kWh. One cloudy day: add 50-75 kWh. Total useful storage: 75-110 kWh.

**LiFePO4 is cheapest over 20-year horizon.** Open-source BMS: [Libre Solar](https://libre.solar/).

### Ground Mount vs Roof Mount

Ground: easier to clean/access/repair, optimal angle, community-buildable, no height work. 24 kW needs ~150 sqm (~10m x 15m). Roof: saves land but needs structural assessment.

### DIY vs Professional

Community can do: panels, racking, wiring. Licensed electrician required: inverter-to-panel connection, grid-tie interconnection, battery bank wiring (high-current DC). A team of 4 installs in a week.

### Maintenance

Wash panels 2x/year (or let rain). Check wiring annually. Inverters last 10-15 yr (budget replacement). BMS monitors batteries automatically.

## Wind -- The Night Shift

Wind peaks at night and in winter -- complementary to solar. Reduces battery needs by 40-50%.

| Requirement | Value |
|-------------|-------|
| Minimum avg wind speed | 5 m/s (11 mph) at hub height |
| Best sites | Hilltops, ridgelines, coastal, open plains |
| Measurement | Anemometer at proposed height for 6-12 months |

| Turbine | Output | Cost |
|---------|--------|------|
| 5-10 kW commercial (Bergey Excel, Xzeres 442) | 500-1,500 kWh/mo in good site | $30K-50K installed (tower is half the cost) |
| Hugh Piggott hand-built | Lower efficiency, locally repairable | $2K-4K materials + community labor |

**Complementary pattern**: Solar peaks Jun-Aug, wind peaks Nov-Mar. Solar-only: 110 kWh battery needed. Solar+wind: 60-70 kWh sufficient (saves $15K-25K in batteries).

Maintenance: annual inspection, occasional bearing replacement. Budget $500-1K/yr. Lifespan: 20-25 yr.

![Community solar array ground-mounted in a meadow with battery shed and people maintaining panels](visuals:photorealistic ground-mounted solar panel array of about 60 panels in neat rows on a green meadow, small wooden battery storage shed with open door showing battery racks inside, two people cleaning panels with soft brushes and water, community buildings with living roofs visible in background, wildflowers growing between panel rows, clear blue sky, practical and beautiful installation)

## Biogas -- Closing the Kitchen Loop

Food scraps become cooking gas; digestate becomes garden fertilizer.

**Input**: 50-100 kg/day kitchen scraps, garden waste, animal manure (not dog/cat).

**Output**: 5-10 m3 biogas/day (60% methane) = 30-60 kWh thermal = 3-5 hrs cooking on standard burner.

**Digestate**: liquid fertilizer rich in N-P-K, biologically active, immediately plant-available.

| Digester Type | Cost | Capacity | Climate |
|--------------|------|----------|---------|
| IBC tote (Solar CITIES) | $300-600 | Small community | Above 15C or insulated |
| Insulated underground (6 m3) | $2K-5K | 50-person community year-round | Down to -20C (soil temp + heating loop) |
| Fixed-dome (Deenbandhu/Chinese) | $3K-8K | Full waste stream + animals | 20-30 yr lifespan |

**Safety**: rated gas piping, flame arrestor, pressure relief valve. Build guide: [Solar CITIES](https://www.appropedia.org/Open_Source_Solar_CITIES_biodigestor_system).

![Cross-section diagram of a biogas digester system](visuals:photorealistic cutaway view of an underground biogas digester system showing insulated concrete chamber with feedstock inlet pipe from above, gas collection dome at top with pipe leading to a kitchen building, liquid digestate overflow pipe leading to garden beds, thermometer showing internal temperature, layers of soil and insulation visible in cross-section, person adding kitchen scraps at inlet, garden with healthy plants receiving digestate, educational and clear)

## Heating and Cooling

### Passive Solar Design

Orient building long axis east-west. Large south-facing windows (north in southern hemisphere). Roof overhangs sized for winter sun / summer shade. 30-60 cm thermal mass in floors and walls.

**Passivhaus numbers**: R-40 walls (30 cm straw bale), R-60 roof, R-20 foundation, triple-pane south windows, airtight + heat-recovery ventilation. Result: 15 kWh/sqm/yr heating -- 1/10th conventional.

### Rocket Mass Heaters

Burns wood at 800-1,000C in insulated combustion chamber. Hot exhaust through thermal mass bench/floor. Mass radiates heat 12-24 hr after fire goes out. Burns 80% less wood than conventional woodstove. Exhaust: mostly water vapor + CO2, near-zero particulates.

- 5m thermal mass bench heats 60-80 sqm
- Burns 5-10 kg small-diameter wood per firing
- 1 hectare coppice woodland = indefinite fuel supply (regrows every 5-7 yr)
- Build cost: $200-800 materials, 1 week with team of 4
- Plans: [Erica & Ernie Wisner](https://www.ernieanderica.info/)

### Cooling Without AC

| Method | Effectiveness | Cost |
|--------|-------------|------|
| Thermal mass (rammed earth, cob, stone floors) | Absorbs daytime heat, releases at night | Integral to building |
| Night ventilation | Flush accumulated heat; close at dawn | Free |
| Solar chimney + earth tubes | Convective draft pulls air through buried pipes at ground temp. 2-4C cooling (dry), 4-8C (humid) | Moderate |
| Deciduous trees (south/west of buildings) | 25-40% summer cooling load reduction | 3-yr investment |
| Earth-sheltered buildings | 18-22C year-round with minimal input | Higher build cost, near-zero operating |

### Extreme Cold Backup

Cold-climate heat pump (Mitsubishi Hyper-Heat, Fujitsu XLTH): operates to -25C, delivers 2-3 kWh heat per kWh electricity. 5 kW unit for common house: $3K-5K installed.

## Water Heating for 50 People

50 people need 1,500-2,500 L hot water/day. Electric heating = 50-80 kWh/day (avoid).

| System | Details | Cost |
|--------|---------|------|
| **Solar thermal (primary)** | Evacuated tube collectors, 60-70% efficient. 8-12 collectors feed 2,000-3,000 L insulated tank. Covers 80-95% Apr-Oct (temperate) | $4K-8K |
| **Flat plate collectors** | Simpler, cheaper, 30+ yr life. Sufficient in Mediterranean/tropical | $200-400 each |
| **Insulated storage tank** | 3,000 L, 200mm insulation. Loses 1-2C/day. Stratification keeps hottest at top | Included above |
| **Wood-fired batch heater** | 200 L tank + firebox. Heats to 70C in 2-3 hr using 5 kg wood | Low |
| **Drain-water heat recovery** | Copper coil on drain pipe. Recovers 40-60% shower heat | $300-500 per unit |
| **Biogas backup** | Instantaneous water heater during cloudy stretches | Low |

## Sovereignty vs Exchange

### Full Sovereignty (own these completely)

- **Cooking**: biogas + wood (no utility can price/ration/cut off)
- **Heating**: passive solar + rocket mass + coppiced firewood
- **Water pumping**: solar-powered well pump + gravity cisterns
- **Lighting/communication**: modest solar/battery for lights, phones, server, mesh

### Grid Connection Strategy

If grid is available with net metering: grid-tie = giant free battery (eliminates $40K-60K battery bank). Hybrid inverter + transfer switch + battery backup for essential loads = best of both. When grid extension costs >$20K-30K ($5K-15K per pole), off-grid wins on day one.

**Sovereignty gradient**: Start grid-tied, oversize solar, build battery gradually, shift loads to daytime. Grid draw approaches zero. Connection becomes insurance.

## First Year Energy Plan

| Phase | Timeline | Investment | What It Does |
|-------|----------|-----------|-------------|
| **Light + Water** | Month 1-2 | $8K-15K | 3-5 kW solar, 1x 5kW inverter, 10-15 kWh battery. Powers: LED lighting, phones, laptops, server, well pump. The heartbeat. |
| **Cooking** | Month 3-4 | $500-2K | IBC biogas digester ($300-600, 1 weekend) + cob oven ($200-500). Cooking sovereign before summer. |
| **Hot Water** | Month 4-8 | $3K-6K | 8 evacuated tube collectors + 2,000 L tank + wood batch heater backup |
| **Scale Solar + Battery** | Month 6-12 | $25K-50K | Expand to 20-30 kW. Battery: start 30-40 kWh, expand as budget allows (+$4K-6K per 10 kWh) |
| **Wind + Heat** | Year 2 | $20K-50K | 5-10 kW turbine (if site has wind) OR more battery. Rocket mass heaters in all common spaces ($200-800 each) |
| **Surplus + Sovereignty** | Year 3-5 | $10K-30K | Full battery (80-110 kWh). Micro-hydro if stream available (500W continuous from 3m head = 12 kWh/day). Underground biogas. Drain heat recovery |
| **Total 5-year** | | **$65K-150K** | **$1,300-3,000 per person.** American household: $2K-3K/yr. Payback: 1-2 yr/person |

## Climate Adaptations

### Heating-Dominated (N Europe, Canada, N US, Mountain)

5-7 month heating season. R-40+ walls, R-60 roof, triple-pane, airtight + heat recovery ventilation. Passive solar + thermal mass + rocket mass heaters + ground-source heat pump backup. Wind is worth most here (strong in winter). Oversize wind, use surplus for heat pump. Firewood: 3-5 cords/dwelling/winter (rocket). 2-3 ha coppice woodland sustains this. Biogas needs underground insulated construction with heating loop.

### Cooling-Dominated (Tropics, Subtropics, Desert)

Deep verandas, light colors, high ceilings, stack-effect ventilation. Earth-sheltered: 24-26C year-round. Earth tubes. Cross-ventilation: -3 to -5C perceived. 15-18 kW solar sufficient (no heating loads). 40-60 kWh battery. Biogas at peak efficiency. Simple thermosiphon solar water heater ($100-300). Enemy is humidity, not temperature.

### Balanced (Mediterranean, Temperate Coastal, Highland Tropical)

Easiest and cheapest. 20-22 kW solar + 60-80 kWh battery = full off-grid. Moderate insulation (R-25 walls, R-40 roof). Solar thermal covers hot water 9-10 months. Wind optional.

### Arid (High Desert, Steppe)

Thick rammed earth/adobe: shifts temperature peak 10-12 hr. Solar excellent (5-7 peak sun hours) but dust = monthly washing. Evaporative cooling: -10 to -15C when humidity <30%. Wind often strong at ridgelines.

## Systems at Scale

| Scale | Solar | Battery | Other | Total Cost |
|-------|-------|---------|-------|-----------|
| 50 people | 20-30 kW | 80-110 kWh | 1 biogas, RMH in commons, solar thermal, 1 wind turbine | $65K-150K |
| 100 people | 2 arrays connected | 2 banks, shared microgrid | Fixed-dome biogas, 2nd turbine | $120K-280K |
| 200 people | Multiple sources | Distributed + intelligent load mgmt | CHP from biogas, micro-hydro baseload | $220K-500K |

## Resources

- [Open Source Ecology - GVCS](https://www.opensourceecology.org/gvcs/) -- 50 open-source machines including power systems
- [OSE Solar Energy Construction Set](https://wiki.opensourceecology.org/wiki/Open_Source_Solar_Energy_Construction_Set)
- [Libre Solar](https://libre.solar/) -- open-source charge controllers and BMS
- [Solar CITIES Biodigester](https://www.appropedia.org/Open_Source_Solar_CITIES_biodigestor_system)
- [ATTRA Micro-Scale Biogas](https://attra.ncat.org/publication/micro-scale-biogas-production-a-beginners-guide/)
- [DOE Microhydropower Guide](https://www.energy.gov/energysaver/planning-microhydropower-system)
- [Appropedia Energy Portal](https://www.appropedia.org/)
- [Hugh Piggott Wind Turbines](https://scoraigwind.co.uk/) -- hand-built designs and workshops
- [Erica & Ernie Wisner - Rocket Mass Heaters](https://www.ernieanderica.info/)
- [Passive House Institute](https://passivehouse.com/)
- [Victron Energy System Design](https://www.victronenergy.com/information/system-design)
- [Andy Wekin - IBC Biodigester Build](https://www.youtube.com/watch?v=qlta6F-XHBQ) -- step-by-step video
- [Earthaven Energy Report](https://www.earthaven.org/) -- 30 years real-world off-grid data
