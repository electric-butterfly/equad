# eQuad

Electric conversion of a 2012 Suzuki King Quad 400 (LT-A400F), retaining the standard
shaft drivetrain and replacing the engine and CVT with a PMSM motor, a 26S2P lithium pack
and a Fardriver controller.

The vehicle keeps both differentials, both propeller shafts and the selectable 4WD front
end. An intermediate drive replaces the engine, transmission and transfer case, taking the
motor's output down to propeller-shaft speed and splitting it fore and aft.

## Duty

A working farm quad in Far North Queensland. It has to tow, it will spend its life in
heat, and it is the first build of a conversion approach intended to carry across to other
off-road machines — quads, side-by-sides, buggies and small ride-ons.

That duty sets the priorities: continuous thermal capability and low-speed tractive effort
ahead of top speed, and a battery box design that repeats across builds rather than one
tailored to this frame alone.

**Top speed target is 60–70 km/h flat out.** Range modes come from the controller's three
digital speed inputs, which select between three parameter maps.

---

## Current focus — the modelling workflow

The immediate objective is not the vehicle. It is a repeatable, AI-supported 3D modelling
workflow that turns a scan of the donor quad into Fusion or SolidWorks models good enough
to hand a fabricator for final manufacturing design and setup.

Everything downstream depends on it. The intermediate drive, the battery and switchgear
boxes and the cooling system are all packaging problems on a machine whose geometry exists
only as a scan and a set of physical parts.

### The workflow, end to end

| Stage | Output |
| --- | --- |
| Capture | Artec scan of the complete vehicle (held) |
| Condition | Decimated, hole-filled mesh aligned to a vehicle datum |
| Reference | Mesh imported to CAD as a non-parametric backdrop |
| Interface capture | Parametric solids for mounting faces, frame rails and shaft flanges only |
| Design | New assemblies modelled against those interfaces |
| Handover | STEP plus dimensioned drawings, toleranced at the interfaces |

The scan is a backdrop, not a model. Only the surfaces a new part actually touches get
reverse-engineered into parametric geometry; the rest stays as mesh. That keeps the CAD
tractable and puts the tolerance discussion exactly where the fabricator needs it.

### Where AI carries load

- Mesh conditioning and datum alignment driven as scripted, repeatable steps rather than
  by hand in a GUI.
- Fusion API (Python) and SolidWorks API scripting to generate parametric features from
  captured interface geometry.
- Maintaining a single parameter table — ratios, envelopes, centre distances — as the one
  source of truth that both the CAD and this repository read from.
- Extracting and cross-checking dimensions against the supplier datasheets and the Suzuki
  shop manual, so any number in the model can be traced back to a document.

### Source geometry

Two Artec exports of the complete vehicle:

| File | Triangles | Size |
| --- | --- | --- |
| King Quad 400 Full Res.stl | 35 074 344 | 1.75 GB |
| King Quad 400 Low Res.stl | 1 844 914 | 92.2 MB |

Both are valid binary STL. The low-res mesh bounds a volume of 2093 × 1850 × 1125 mm,
which places it in millimetres at roughly life size against the vehicle's 2060–2160 mm
overall length and 1145 mm overall height.

The 1850 mm intermediate extent is well beyond the vehicle's 1200 mm overall width, so the
mesh is either rotated within its own frame or carries geometry captured beyond the quad
itself. Establishing a vehicle datum — and trimming to it — is the first stage of
conditioning.

Scan data lives in the project drive, not in this repository.

### Design packages

**Intermediate drive.** The load-bearing item. A single cross-shaft carrying output stubs
for the standard front and rear propeller shafts, driven from the motor, with tension taken
up by the motor mount. It has to reproduce the propeller shaft spline interfaces exactly,
set the centre distance for the chosen drive, and shed mud and debris.

Chain is the working assumption over toothed belt, on the fabricator's recommendation:
higher torque capacity, tolerant of an unsealed housing, smaller footprint, durable in a
rugged environment, and length adjustable and breakable for installation. The costs are
noise, lubrication and maintenance, and higher rotating inertia.

The shop manual gives service data for the output shafts — bevel gear backlash
0.03–0.15 mm, output and bevel gear nuts at 100 N·m — but no spline or flange dimensions.
Those interfaces have to come from measurement of the parts and from the scan.

**Battery boxes.** Two packs in an inverted V, one either side, leaving a channel down the
centre for the front propeller shaft. The channel doubles as the cooling duct, so the two
packages are dimensionally coupled — cells set the wall angle, and the duct sets the
minimum clear width between them.

The inverted V also puts pack mass low and outboard, which suits a machine that tows, and
it splits the pack into two enclosures that can carry their own contactor and fuse. Whether
the volume is really there is a scan question, not a paper one.

**Controller box.** An aluminium box in the fuel tank position holding the controller, the
AC and DC terminations and control wiring, with its base doubling as the duct roof and
heatsink. The relay-version BMS drives remote contactors, so no main current passes through
box electronics.

Sealing it against mud and water means everything inside loses its own path to air. Busbar
and terminal joint losses at pack current are tens of watts with nowhere to go but the base
plate already carrying the controller. Solar gain on an aluminium box in the open in FNQ is
worth a thought too.

**Switchgear box.** Separate. Contactors, fuses, fuse holders, pre-charge and the DC-DC
converter. Two packs with two-pole isolation each accounts for the four main contactors;
pre-charge needs a fifth, and six were purchased.

**Cooling.** Forced air. The motor is air-cooled and is the continuous bottleneck; the
controller is natural-convection cooled and fully potted. Neither will look after itself
under a sustained tow in the heat, and natural airflow at crawl speed is close to zero —
which is exactly when the load is highest.

The donor supplies most of the hardware. It carries a cooling fan on a bracket at the oil
cooler, and the LT-A400 also has moulded V-belt cooling ducts running from a high intake
down into the centre of the machine — the same channel the battery box is aiming at, and
already routed the way it is because grass seed and mud are the enemy of a low intake.
Both the fan mounting and the duct geometry are in the scan and are worth capturing rather
than redesigning.

Fan control comes from the motor's KTY83-122 probe and controller temperature, not the
stock thermo-switch, which closes at about 120 °C engine oil temperature — at or past the
motor's own working ceiling. Run-on after shutdown matters more on an air-cooled motor than
it did on the engine, because a hot motor with the machine stopped has no airflow at all.

### Duct and fan sizing

Design point: 35 °C ambient at 750 m, which gives an air density of 1.047 kg/m³. Air enters
at the centre channel, passes the controller, then the motor, and rejects to the rear.
Controller first is correct — it is the temperature-sensitive item, rated to 55 °C ambient
against a 120 °C motor.

| Duty | Motor loss | Controller loss | Total |
| --- | --- | --- | --- |
| 4.0 kW shaft | 444 W | 91 W | 535 W |
| 7.5 kW shaft | 833 W | 170 W | 1003 W |

Carrying 1000 W on a 15 K air temperature rise needs **64 L/s, about 140 cfm**. The lighter
duty needs 34 L/s. Duct section then sets velocity, and velocity sets both heat transfer
and fan work:

| Duct | Velocity | Pressure drop | Fan power at 12 V |
| --- | --- | --- | --- |
| 200 × 120 mm | 2.7 m/s | 30–56 Pa | 1.2 A |
| 150 × 100 mm | 4.3 m/s | 76–143 Pa | 3.0 A |
| 120 × 80 mm | 6.7 m/s | 186–349 Pa | 7.4 A |

**150 × 100 mm is the sensible compromise.** Wider and the air moves too slowly to pick the
heat up; narrower and fan power climbs faster than the heat transfer it buys.

The fan has to hold pressure, not just move free air. At 64 L/s against 150 Pa the air
power is only 9 W, but at realistic fan efficiency that is around 3 A at 12 V — comfortable
against the 30 A DC-DC. A centrifugal automotive cabin blower or a high-static axial suits;
a cheap muffin-style axial stalls well below this pressure. Whether the donor's oil-cooler
fan is pressure-capable enough is not established.

### The controller needs fins

The controller is a sealed, potted brick. Its heat leaves through the aluminium baseplate,
189 × 122 mm, so it bolts baseplate-down onto whatever does the rejecting. The potted body
itself is not a useful radiating surface, and putting the brick in the airstream achieves
little beyond obstructing the duct.

Mounting it to the duct wall does not work. At 4.3 m/s the inner face sees about
18 W/m²K and the outer face sits in still air under the machine at perhaps 6 W/m²K. On a
150 mm wide duct that yields:

| Wall panel | Wetted area | Heat rejected |
| --- | --- | --- |
| 150 × 300 mm | 0.045 m² | 25 W |
| 150 × 400 mm | 0.060 m² | 33 W |
| 150 × 600 mm | 0.090 m² | 49 W |

Against 170 W the required bare wall is 0.31 m² — a duct 2.1 m long. Not available.

A plate spreads heat poorly at that scale, too. Acting as a fin, a 6 mm aluminium plate
runs at 73% efficiency 200 mm from the source and 45% at 400 mm; 15 mm plate reaches 87%
and 64%. The far corners of a large plate contribute much less than their area suggests.

### Switchgear box as the heatsink

The arrangement: an aluminium box in the fuel tank position, controller bolted flat to the
box base, and that base forming the roof of the duct. Welded sheet strips hang down from it
into the airstream. The tank position gives roughly the right envelope — the stock tank is
16.0 L including 2.9 L reserve — and the box also carries the BMS and terminals.

Welded strips suit this better than an extrusion. Thick strips conduct well, so fin
efficiency stays high, and the wide pitch that welding forces keeps pressure drop and
fouling down — both of which matter more here than packing density.

Fin efficiency, weldable alloy at about 150 W/m·K:

| Strip thickness | 40 mm high | 60 mm high | 80 mm high |
| --- | --- | --- | --- |
| 3 mm | 0.96 | 0.91 | 0.86 |
| 4 mm | 0.97 | 0.93 | 0.89 |
| 6 mm | 0.98 | 0.96 | 0.92 |

Sizing with 4 mm strips at 20 mm pitch — seven fins across the 150 mm duct:

| Fin height | Length | Wetted area | Rejected | Duct blockage |
| --- | --- | --- | --- | --- |
| 40 mm | 300 mm | 0.199 m² | 108 W | 7% |
| 40 mm | 400 mm | 0.266 m² | 144 W | 7% |
| 60 mm | 300 mm | 0.272 m² | 147 W | 11% |
| 60 mm | 400 mm | 0.363 m² | 196 W | 11% |

**60 mm strips over 350–400 mm covers the 170 W worst case with margin**, at about 11%
blockage — a small velocity rise and a modest pressure penalty.

The base plate has to spread heat from the controller's 189 × 122 mm footprint out to the
far fins. At 8–10 mm it runs 0.82–0.85 efficient 150 mm beyond the controller; 6 mm drops
to 0.78. Ten millimetres is the sensible base, and it welds and stiffens well. Fins
directly beneath the controller work at full effect, so they earn their length there first.

**Open input:** the manual gives the controller a working temperature of −30 to +55 °C
without saying whether that is ambient or baseplate. If it is ambient and the baseplate may
run to 85 °C, the temperature difference goes from 30 K to 50 K and the required area falls
from 0.39 m² to 0.24 m². That single answer changes the heatsink by a factor of 1.6 and is
worth getting from Fardriver before the switchgear box is drawn.

The motor is the easier problem because it tolerates a much larger temperature difference,
but at 0.3–0.6 m² of case area it is still marginal at the 7.5 kW duty. If the case does
not provide that, the practical continuous rating in this installation is nearer 4 kW than
7.5 kW — which is a reason to gear for tractive effort rather than speed.

**Layout.** Mass distribution, ground clearance and service access across the whole
vehicle.

---

## Vehicle

2012 Suzuki King Quad 400, LT-A400F — automatic (V-belt CVT), 2-speed transfer with
reverse, selectable 4WD, shaft drive front and rear.

| | |
| --- | --- |
| Overall length | 2060–2160 mm |
| Overall width | 1200 mm |
| Overall height | 1145 mm |
| Wheelbase | 1220 mm |
| Front / rear track | 880 / 900 mm |
| Ground clearance | 250 mm |
| Seat height | 840 mm |
| Dry mass | 252–275 kg |
| Tyres | AT25 × 8-12 front, AT25 × 10-12 rear |

Stock driveline ratios, from the shop manual:

| | LT-A400 (auto) |
| --- | --- |
| Primary (CVT) | 2.938 – 0.813 variable |
| Secondary | 2.730 (42/19 × 21/17) |
| Final drive, front and rear | 3.600 (36/10) |
| Transfer — low / high / reverse | 2.500 / 1.375 / 2.125 |

The conversion deletes the engine, CVT and transfer case. Only the 3.600 final drive
survives, and reverse moves to the controller and a DNR selector.

## Drivetrain sizing

The V3 motor carries a 1:2.35 reduction inside it, so the motor's rotor speed and the
speed presented to the intermediate drive are not the same number. Ratios below are stated
from the rotor.

| | |
| --- | --- |
| Motor maximum speed | 7000 rpm |
| Internal gearbox | 2.350 |
| Motor output shaft, maximum | 2979 rpm |
| Motor output sprocket | 428 chain, 14–16 teeth |
| Final drive | 3.600 |
| Rolling circumference | 1.995 m (AT25, 635 mm diameter) |

### Selecting the intermediate ratio

Road speed and tractive effort trade directly against each other through this one ratio.
Candidates on standard 428 sprockets, against the 60–70 km/h target:

| Drive | Driven | Ratio | Top speed | Peak effort | Continuous effort |
| --- | --- | --- | --- | --- | --- |
| 15 | 21 | 1.400 | 70.7 km/h | 2381 N | 508 N |
| 14 | 20 | 1.429 | 69.3 km/h | 2430 N | 518 N |
| 15 | 22 | 1.467 | 67.5 km/h | 2494 N | 532 N |
| 14 | 21 | 1.500 | 66.0 km/h | 2551 N | 544 N |
| 15 | 23 | 1.533 | 64.6 km/h | 2608 N | 556 N |
| 14 | 22 | 1.571 | 63.0 km/h | 2673 N | 570 N |
| 15 | 24 | 1.600 | 61.9 km/h | 2721 N | 581 N |
| 14 | 23 | 1.643 | 60.3 km/h | 2794 N | 596 N |

Effort figures are total at the axles on a 635 mm tyre, from 150 N·m peak and 32 N·m
continuous at the motor output. The band is narrow — 60 km/h buys only 17% more tractive
effort than 70 km/h — so the choice can be made on packaging and sprocket availability
rather than agonised over. Something near 14/21 or 15/22 sits mid-target.

For reference, the originally sketched 2:1 gives 49.5 km/h with 3402 N peak.

### Control mapping

Three digital speed inputs select three parameter maps. The intent is distinct throttle
and response curves per map — a genuine low-speed crawler mode with a softened throttle
curve and a lower ramp rate, a general working map, and an unrestricted map.

Crawl control was the part of the deleted low range that mattered most day to day, and
mapping recovers it. What mapping cannot recover is thermal headroom under sustained load,
which stays a function of the mechanical ratio alone. That keeps sustained towing duty —
not crawl feel — as the argument for the lower end of the ratio band.

The wiring inputs are confirmed in the controller manual: high gear / low gear, reverse and
cruise. Which parameters are per-map rather than global is not documented in the material
held, and it needs establishing before the crawler map can be specified.

## Powertrain

**Motor** — SIAECOSYS QS138 90H V3, PMSM mid-drive with integrated single-stage gearbox.

| | |
| --- | --- |
| Rated voltage | 72 V |
| Rated power | 4000 W |
| Peak power | 11–13.5 kW |
| Motor speed, rated / maximum | 4800 / 7000 rpm |
| Internal gear ratio | 1:2.35 |
| Output | 428 chain sprocket |
| Torque at output, rated / maximum | 32 / 150 N·m |
| Rated current | 60 A |
| Maximum bus current | 200 A |
| Maximum efficiency | 90–93% |
| Magnet | 90 mm, 5 pole pairs |
| Sensor | Single hall set |
| Mass | 14.5–16.6 kg |
| Protection | IP67 |

Reseller figures vary — continuous power is quoted anywhere from 4 kW to 7.5 kW and peak
from 11 kW to 20 kW. The torque figures are internally consistent with the gearbox ratio,
so they are the ones to design against.

**Controller** — Fardriver ND961000, NS48 family.

| | |
| --- | --- |
| Rated voltage | 96 V |
| Bus current | 450 A |
| Phase current | 1000 A |
| Rated power | 5.0–9.0 kW |
| Envelope | 189 × 122 × 54.7 mm |
| Cooling | Natural convection, fully potted |
| Operating temperature | −30 to +55 °C |
| Interfaces | CAN, RS485, one-wire, analogue |

**Battery** — CALB L148N58A prismatic lithium-ion, 26S2P.

| Cell | |
| --- | --- |
| Nominal capacity | 58 Ah at 1C |
| Working voltage | 2.75–4.35 V above 0 °C |
| Internal resistance | 0.60–0.80 mΩ at 1 kHz, 70% SOC |
| Continuous discharge | 1C (58 A) at 20–40 °C |
| Pulse discharge | 450 A for 10 s below 50 °C |
| Recommended SOC window | 5–97% |
| Mass | 926 ± 20 g |
| Envelope | 148.24 × 26.66 × 105.9 mm |
| Terminal spacing | 110.6 mm |
| Case | Aluminium alloy |

| Pack (26S2P) | |
| --- | --- |
| Nominal | 96.2 V |
| Range | 71.5–113.1 V |
| Capacity | 116 Ah |
| Energy | 11.16 kWh, 10.04 kWh at 90% DoD |
| Continuous | 116 A, 11.2 kW |
| Cell mass | 48.2 kg for 52 cells |

Charge current is temperature-limited: 1.2C peak at 20–45 °C, falling to 0.2C at 0–10 °C
and disallowed below −20 °C. Regenerative braking is limited by state of charge as well as
temperature — 5C for 10 s at 80% SOC and 20–40 °C, and not permitted at all above 95% SOC.
Both constraints belong in the BMS configuration, not only in the documentation.

**BMS** — ANT 21S–30S, 24–112 V, 400 A / 1000 A, with CAN customisation.

**Switchgear** — TE Kilovac EV200HAANA sealed contactors, SPST-NO, 500 A, 9–36 V DC coil.
Littelfuse JLLN Class T fuses with LSCR holders.

**Auxiliary** — 48–120 V to 12 V, 30 A, 400 W DC-DC converter.

**Charging** — two chargers held. Output voltage and current are unconfirmed and no
charger appears in the BOM.

## CAN architecture

The Fardriver CAN protocol is SAE J1939-21 over CAN 2.0B at 500 kbit/s, PDU2 format.

| Node | Source address |
| --- | --- |
| BMS | 1 |
| Motor controller | 2 |
| Instrument | 3 |
| Central control | 4 |

Termination is not uniform across the bus. The controller carries its own 120 Ω and a
non-isolated transceiver; the instrument needs an isolated transceiver and provides a
120 Ω; the BMS provides no resistor and references the bus to battery negative. The harness
design has to respect that asymmetry.

## Reference library

Held in the project drive alongside the scans:

- Suzuki King Quad 400 LT-A400F / LT-F400F shop manual, 2008–2014
- CALB L148N58A cell specification and dimensioned drawing, plus superseded cell
  candidates from CATL, CALB and JMRI
- Fardriver controller manual, tuning guide, NS48 and S60 datasheets, CAN18 protocol
- TE Kilovac contactor and Littelfuse JLLN datasheets
- EB-Quad BOM and gear ratio calculator
- Drive pulley concept sketch
- Supplier contracts and invoices

## Open engineering questions

**Cell continuous rating.** The BOM records these cells at 8C and 268 A continuous. The
datasheet allows 1C continuous — 58 A per cell, 116 A at pack level — with 8C available
only as a 450 A, 10-second pulse. The supplier listing reads the same way, so the 8C
figure is a misreading rather than a supplier claim.

It does not force a redesign. The motor is the continuous bottleneck, not the pack:

| Limit | Current at 96.2 V | Power |
| --- | --- | --- |
| Motor, continuous | 42–78 A | 4.0–7.5 kW |
| Pack, continuous (1C) | 116 A | 11.2 kW |
| Motor, maximum bus | 200 A | 19.2 kW |
| Pack, 10-second pulse | 900 A | — |
| Controller bus limit | 450 A | 43.3 kW |

The pack comfortably outruns what the motor can absorb continuously, and its pulse
capability sits well above the motor's peak. What the 8C figure does need to change is the
BMS configuration — set discharge limits from the datasheet, not the BOM — and any future
sizing calculation that inherits it.

**Voltage margin.** The binding limit is the controller, not the fuse. The ND961000's peak
battery voltage is 115 V; a pack charged to 4.35 V per cell reaches 113.1 V — under two
volts of headroom. The JLLN fuse is the looser constraint at 125 V DC. Capping charge
voltage below 4.35 V per cell costs a little capacity and buys cycle life anyway, and is
the cheaper fix than dropping to 25S.

**Fuse sizing.** An 800 A element sits far above both the 450 A controller bus limit and
the 116 A cell limit, so it protects against a short circuit and nothing else. Overload
protection has to come from the BMS and controller.

**Contactor datasheet.** The parts held are EV200HAANA; the datasheet on file is for the
LEV200 series. The EV200 datasheet is the one to design the switchgear box against.

**Intermediate ratio.** Narrowed to 1.40–1.64 by the 60–70 km/h target, but not yet
fixed. The remaining input is packaging: sprocket diameters and the centre distance they
imply have to fit the space the engine vacates, which is a scan question. This is the
last drivetrain number the fabricator needs.

**Motor speed limit.** Rated voltage is 72 V; the pack is 96.2 V nominal and 113.1 V at
full charge. Speed scales with voltage, so at full charge the motor would run past its
7000 rpm mechanical ceiling before flux weakening is asked for. The controller's rpm limit
has to be set deliberately, not left at default.

**Thermal headroom.** The motor is air-cooled and it is the continuous bottleneck, on a
machine that tows in FNQ heat. Forced air is the plan; what is not yet settled is the duct
routing, whether the stock fan moves enough air for the new heat load, and how the
controller derates on temperature. All three want answering before the layout is fixed
rather than after the first hot tow.

**ANT CAN protocol.** The BMS was ordered with CAN customisation specifically to join the
J1939 bus, and the supplier confirmed they can provide the protocol document. It is not in
the reference library. Without it the BMS cannot be integrated, and the harness and dash
design cannot be closed out.

**Pre-charge.** Required. Two distinct inrush problems exist in this architecture and only
one of them is solved by matching pack voltages.

Matching the two packs before paralleling controls pack-to-pack circulating current, and
that plan is sound. It does nothing for the controller's DC bus capacitors, which sit at
zero volts every time the system is switched on regardless of how well the packs agree.
Closing a main contactor straight onto them is a capacitor charging event limited only by
loop resistance.

Peak inrush is set by loop resistance alone — capacitance governs how long it lasts, not
how high it goes. The pack's own internal resistance dominates the loop at 9.1 mΩ for
26S2P, from the cell datasheet's 0.6–0.8 mΩ:

| Added cable, contactor and ESR | Peak inrush |
| --- | --- |
| 5 mΩ | 8021 A |
| 10 mΩ | 5921 A |
| 20 mΩ | 3887 A |
| 40 mΩ | 2303 A |

Even with no external resistance at all the pack can only deliver 12 429 A, and holding
inrush to the contactors' 2000 A interrupt rating would need 56.5 mΩ of added loop —
six times the pack's own resistance, which a short heavy-cable HV loop will not provide.
The conclusion holds across the whole plausible range: making a main contactor onto a
discharged bus welds contacts, and not necessarily the first time, which is why the
omission surfaces late.

A resistor across one pack's main contactor, switched by a pre-charge contactor, fixes it.
Sequence is pre-charge, confirm bus voltage has risen to pack voltage, close the pack mains
onto an already-charged bus, then drop pre-charge. The second pack then closes onto a bus
already at its own voltage, which is where the manual voltage matching does its work.

**Sizing the resistor needs the bus capacitance, which is not published.** It is absent
from the controller manual, the NS48 datasheet and the reseller listings. It sets both the
pre-charge duration (5RC to 99%) and the pulse energy the resistor must absorb, which is
½CV² per closure regardless of resistor value. Measuring it settles both: charge the bus
through a known high resistance from a bench supply and time the rise to 63%.
