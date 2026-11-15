# Radiation: sources and facts used by ASTRA

Saved here so the Radiation page can stay simple. Checked on 15 Nov 2026. Everything on the page that is a number from NASA is listed with its source. ASTRA never turns proton flux into a dose.

## 0. How the radiation pieces fit together (read this first)
One place for the definitions, so the documents do not contradict each other. Where an older section of `RADIATION_MONITOR.md` differs from this list, this list (which follows the code) wins.

| Piece | What it is | What it is NOT |
|---|---|---|
| **NASA 600 mSv career limit** | NASA-STD-3001 Vol 1 [V1 4030]: an astronaut's total career effective dose from spaceflight radiation shall be less than 600 mSv (TB-020 Rev E, page 4). Used only as the limit in the illustrative exposure budget | Not an alert level, not a per-mission or per-day limit, and ASTRA does not measure whether a person is near it |
| **NOAA GOES proton flux** | The integral flux of protons at 10 MeV or more, in particle flux units (pfu), measured by NOAA's GOES satellites and published as JSON by NOAA SWPC. It is space weather outside the spacecraft. Labelled `external` | Not NASA data, not a dose, not a measurement inside a spacecraft |
| **NOAA S1 to S5 scale** | NOAA's Space Radiation Storm classes from that flux: S1 at 10 pfu, S2 at 100, S3 at 1,000, S4 at 10,000, S5 at 100,000 | Not a statement about harm to an astronaut |
| **Why flux cannot become dose** | Turning proton flux into an astronaut's dose needs the particle energy spectrum, the direction, the shielding around the person, the secondary particles made in the walls and in the body, and the time spent in each place. NOAA's flux at 10 MeV or more does not contain this. **ASTRA never converts flux to dose** | |
| **ASTRA alert levels 0 to 3** | A small, documented state machine on the flux samples: NORMAL, ELEVATED, HIGH, SEVERE. They drive the `radiation` notification (S1 to S4 events). They are demonstration interface states | Not NASA flight rules; not [V2 6100] "Ionizing Radiation Alerting" |
| **ASTRA five-stage outlook** | All clear, Watch, Prepare, Build the shelter, Shelter. Watch and Prepare come from three early signs published by NOAA (an M or X flare, a solar radio burst, NOAA's own storm chance) plus a rising particle level; the last two stages follow the S2 to S5 levels. Thresholds are ASTRA's own choices | **ASTRA cannot reliably predict solar storms.** NASA says such storms are hard to predict and forecast models are early. The outlook shows early signs, it is not a forecast |
| **Simulated radiation scenarios** | Buttons on the Radiation page (Quiet, Watch, Prepare, S1 to S4, History) that feed made-up flux samples, labelled `simulated`, never mixed with NOAA samples. Used for testing and the demo | Not real events |
| **Exposure budget (illustrative)** | Defaults in `backend/radiation.py`: budget 600 mSv (the NASA limit), dose received so far 36.5 mSv (a demo mission of 180 days, day 73, at the assumed rate), assumed background 0.5 mSv/day (the figure TB-020 uses for a surface-mission analysis; ISS crews receive roughly 0.4 to 1.0 mSv/day), demo event doses 0.1, 1, 5, 20 and 60 mSv for S1 to S5 chosen by the team. The user can change all of them | Not a medical result, not a safe mission duration, and not derived from flux |
| **Onboard detector** | ASTRA has none. The board has no ionizing-radiation sensor. All radiation data comes from NOAA over the internet or from a simulation | |

## 1. Fact check: the NASA career limit
- **Claim:** NASA's career radiation limit for astronauts is 600 mSv. **Verdict: correct.**
- **Wording (NASA-STD-3001 Volume 1, requirement [V1 4030]):** an individual astronaut's total career effective radiation dose from spaceflight radiation shall be less than 600 mSv. It is universal for all ages and sexes and is expressed as NASA effective dose (NASA cancer model of 2012, parameters of a 35-year-old female).
- **Where it comes from:** it is the dose-based form of NASA's older risk target (a mean 3% risk of exposure-induced death from cancer). It replaces the older age- and sex-dependent limits. The 2021 National Academies review supports a single dose-based standard but recommends re-examining the 3% metric.
- **Related requirement [V1 4031]:** the design-reference solar particle event (the October 1989 events) must give less than 250 mSv effective dose. This is a design requirement for spacecraft protection, not an alert level.
- **Not confirmed:** the exact date the revision was adopted; check the current revision of NASA-STD-3001 Volume 1.
- **Source:** NASA OCHMO technical brief on radiation protection, https://www.nasa.gov/wp-content/uploads/2023/03/radiation-protection-technical-brief-ochmo.pdf (TB-020 Rev E, 12/27/2022; checked against the PDF on 15 Nov 2026: [V1 4030] page 4, [V1 4031] page 6, [V2 6099] and [V2 6100] page 13). NASA-STD-3001 itself was not read; the revision and adoption date of the standard are not verified. National Academies, Space Radiation and Astronaut Health (2021): https://www.nationalacademies.org/read/26155/chapter/5

## 2. Typical daily doses (context, not used as measurements)
- ISS astronauts: roughly 0.4 to 1.0 mSv per day on average (Hassler, Curiosity RAD team, quoted by SwRI).
- Mars cruise: Curiosity's RAD instrument measured an average galactic cosmic ray dose equivalent of about 1.8 mSv per day in cruise (about 660 mSv for a round trip with current propulsion). Solar particles were about 5% of the detected dose. Source: Zeitlin et al., Science 2013 and the SwRI press release: https://www.swri.org/newsroom/press-releases/swri-led-team-calculates-the-radiation-exposure-associated-trip-mars
- NASA's brief uses about 0.5 mSv per day for a surface mission in its analysis. ASTRA's default background rate is 0.5 mSv/day, an assumption that can be changed on the page.

## 3. What the Radiation page does with it
- **Status** comes from NOAA's GOES proton flux (at or above 10 MeV) and the NOAA S-scale (S1 10, S2 100, S3 1,000, S4 10,000, S5 100,000 pfu). Alert levels (elevated, high, severe) are ASTRA demonstration states, not NASA flight rules.
- **Daily exposure** is an estimate: the assumed background rate plus event doses. In the demo the event doses are made-up values (S1 0.1, S2 1, S3 5, S4 20, S5 60 mSv). For real data, an event dose appears only if someone types in a dosimeter reading.
- **Career limit:** 600 mSv. The dose received so far is a setting the user can change; the demo default is 36.5 mSv (assumed mission day 73 at 0.5 mSv/day). ASTRA cannot know a real person's dose.

## 4. Articles and pages

| Title | Link | Note |
|---|---|---|
| NASA OCHMO: Radiation protection technical brief (career limit 600 mSv, [V1 4030], [V1 4031]) | https://www.nasa.gov/wp-content/uploads/2023/03/radiation-protection-technical-brief-ochmo.pdf | NASA |
| NOAA SWPC: GOES proton flux and the Space Radiation Storm scale | https://www.spaceweather.gov/products/goes-proton-flux | NOAA, source of the live data |
| National Academies: Space Radiation and Astronaut Health (2021) | https://www.nationalacademies.org/read/26155/chapter/5 | review of the 600 mSv proposal |
| SwRI: radiation exposure of a trip to Mars (Curiosity RAD) | https://www.swri.org/newsroom/press-releases/swri-led-team-calculates-the-radiation-exposure-associated-trip-mars | 1.8 mSv per day cruise |
| OSD-435 and OSD-591: low-dose oxygen ions and protons and cardiac function in mice | https://osdr.nasa.gov/bio/repo/data/studies/OSD-435 | dataset, status needs_review |
| OSD-720 and OSD-881: long-term heart changes after gamma and simulated galactic cosmic ray radiation in mice | https://osdr.nasa.gov/bio/repo/data/studies/OSD-720 | dataset, status needs_review |
| OSD-896, OSD-897, OSD-939: sustained attention in rats after proton radiation | https://osdr.nasa.gov/bio/repo/data/studies/OSD-896 | dataset, status needs_review |
| OSD-1018: social isolation and space radiation, behaviour and motor learning in rats | https://osdr.nasa.gov/bio/repo/data/studies/OSD-1018 | dataset, status needs_review |
| OSD-964: BioSentinel, validating yeast biosensors for deep space radiation | https://osdr.nasa.gov/bio/repo/data/studies/OSD-964 | dataset, status needs_review |
| OSD-776, OSD-777, OSD-778: deep space radiation and cognitive performance in mice | https://osdr.nasa.gov/bio/repo/data/studies/OSD-776 | dataset, status needs_review |

The NASA OSDR study entries were read at description level only (not the papers). See `docs/OSDR_RESOURCES.md` and `data/reference.json`.

## Shelter and early warning (added 16 Nov 2026)

Fact check of "astronauts build a shelter from food and water":
- True for NASA's Orion capsule: the crew would build a temporary shelter from materials already aboard (stowage bags, storage units, food and water). NASA: https://science.nasa.gov/science-research/heliophysics/how-nasa-will-protect-astronauts-from-space-radiation-at-the-moon . Water and food are hydrogen-rich, which is why they shield well against protons (NASA technical report: https://ntrs.nasa.gov/archive/nasa/casi.ntrs.nasa.gov/20160006051.pdf).
- Not "usual practice": it is a planned procedure for deep-space vehicles, started on an instruction from NASA's radiation group (or dose-rate thresholds, per news reports).
- Not in NASA text, only in news articles (marked as such on screen): building takes about 30 to 60 minutes, the crew may stay up to about 24 hours, Artemis II rehearses the build. Examples: https://www.space.com/space-exploration/artemis/how-the-artemis-2-astronauts-could-weather-a-solar-storm-during-their-moon-mission , https://www.ansto.gov.au/news/artemis-ii-and-invisible-hazard-on-way-to-moon-part-1 .
- The ISS "Zvezda shelter" claim was found only on a blog and is not used.

Prediction: NASA says solar particle storms are hard to predict and the forecast models are early. A flare-based tool (ESPERTA) was reported to give a median warning of about 2 hours (0.4 to 36 h) with about 59% detection and 30% false alarms (Space Weather review, Bain et al. 2021, https://doaj.org/article/9783aaa9109d4630902773feb13e25c4; numbers read from the abstract summary, check the paper before quoting). NOAA early-sign feeds used by ASTRA: `products/noaa-scales.json`, `products/alerts.json`, `json/goes/primary/xrays-6-hour.json` on services.swpc.noaa.gov.
