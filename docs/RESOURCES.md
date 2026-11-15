# ASTRA: every resource we used, and which notification uses it

Checked 15 Nov 2026. Two rules apply to everything below:
- **NASA publishes no heart-rate, blood-oxygen or movement thresholds for crew alerts, so none are invented.** The limits that trigger a notification are ASTRA's own rules (compare today with the person's own baseline) and are marked "ASTRA rule". What a NASA document contributes is the advice, the wording and the context, and the dashboard tags each step `NASA GUIDANCE` or `ASTRA SUGGESTION`.
- ASTRA is an educational prototype, not a medical device. Alert levels and the radiation budget are demonstration models, not NASA flight rules.

## 1. Notification by notification

| Notification (id) | What triggers it | NASA and other resources it uses | What the resource contributes |
|---|---|---|---|
| **Heart rate higher or lower than usual** (`hr_vs_baseline`) | ASTRA rule: today's average heart rate against the person's own baseline; orange outside the usual day-to-day change, red beyond twice that | [NASA HRP Evidence Report, Risk of Cardiac Rhythm Problems during Spaceflight](https://humanresearchroadmap.nasa.gov/evidence/other/Arrhythmia.pdf) (sections IV.A.1, IV.A.4, IV.D, IV.E; exact use in `NASA_ARRHYTHMIA_REPORT_USE.md`). [NASA OCHMO TB-031, Exercise](https://www.nasa.gov/wp-content/uploads/2023/12/ochmo-tb-031-exercise-overview.pdf). [NASA OCHMO TB-044, Medical Operations](https://www.nasa.gov/wp-content/uploads/2025/08/ochmo-tb-044-medical-operations.pdf) | Fingertip pulse cannot show heart rhythm (so ASTRA says it is only a hint); log heart rate during exercise; people are slow to report symptoms, so do not wait; the emergency signs; crew medical support and contact with flight surgeons (the three levels of care) |
| **Blood oxygen higher or lower than usual** (`spo2_vs_baseline`) | ASTRA rule: today's average against the person's baseline | none for numbers: NASA gives no alert values that ASTRA could use, and the notification says so. The sensor is a low-cost estimate (current firmware sends `null`) | Plain safe steps only |
| **Rest started at an unusual time**, **Rest was longer or shorter than usual** (`rest_start_vs_usual`, `rest_length_vs_usual`) | ASTRA rule: rest found from heart rate and motion, compared with the usual start time and length (45 min minimum difference) | [NASA, Seven ways astronauts improve sleep](https://www.nasa.gov/missions/station/seven-ways-astronauts-improve-sleep-may-help-you-snooze-better-on-earth/); [NASA HRP hazards](https://www.nasa.gov/hrp/hazards/) and [risks](https://www.nasa.gov/hrp/risks/) | Fixed sleep and wake times, dim light, dark quiet sleeping area, hard exercise earlier in the day; sleep and workday length as part of crew protection |
| **No movement for N hours** (`inactivity`) | ASTRA rule: still for 60 minutes or more (5-minute blocks, mean acceleration change below 0.05 g), only 07:00 to 22:00 | [NASA HRP Arrhythmia report, Exercise (IV.A.4)](https://humanresearchroadmap.nasa.gov/evidence/other/Arrhythmia.pdf); [NASA OCHMO TB-031](https://www.nasa.gov/wp-content/uploads/2023/12/ochmo-tb-031-exercise-overview.pdf) (in-mission aerobic capacity kept at or above 80% of pre-mission); [NASA HRP Evidence Report, Risk of Reduced Physical Performance Capabilities](https://humanresearchroadmap.nasa.gov/evidence/reports/Aerobic.pdf) | Exercise examples and the reason to keep moving (cards on the Activity page, tagged "adapted from NASA") |
| **Signal quality is low**, **Data has gaps today**, **Device stopped sending** (`signal_quality`, `wear_time`, `connection`) | ASTRA technical rules (share of good readings, wear coverage, age of the last reading) | none (no NASA source: they check ASTRA's own data) | Practical steps to refit the sensor and check the link |
| **Radiation level 1 to 4** (`radiation`) | NOAA S-scale from the live GOES proton flux at or above 10 MeV (S1 at 10 pfu up to S5 at 100 000 pfu), then ASTRA's alert states | [NOAA SWPC GOES proton flux and Space Radiation Storm scale](https://www.spaceweather.gov/products/goes-proton-flux) with the data files `services.swpc.noaa.gov/json/goes/primary/integral-protons-1-day.json` and `-6-hour.json`; [NASA OCHMO radiation protection technical brief (TB-020)](https://www.nasa.gov/wp-content/uploads/2023/03/radiation-protection-technical-brief-ochmo.pdf), NASA-STD-3001 Vol 1 [V1 4030] career limit 600 mSv | The scale and the data (NOAA, not NASA); the career limit for the illustrative exposure budget. Dose is never computed from proton flux |
| **Radiation watch / Prepare** (`radiation_outlook`) | ASTRA rule on three early signs from NOAA: an M or X flare, a solar radio burst, NOAA's own chance of a radiation storm (20% or more), plus a rising particle level | NOAA SWPC files `xrays-6-hour.json`, `noaa-scales.json`, `alerts.json` (services.swpc.noaa.gov); [NASA, How NASA will protect astronauts from space radiation at the Moon](https://science.nasa.gov/science-research/heliophysics/how-nasa-will-protect-astronauts-from-space-radiation-at-the-moon) | Early signs (NOAA). NASA: a temporary shelter built from stowage bags, food and water on the Orion capsule; storm forecasting is hard. ASTRA says it cannot predict storms |
| **Three levels of care** in every notification (self-care, tell the crew medical officer, emergency) | ASTRA design for missions far from Earth | [NASA OCHMO TB-044 Medical Operations](https://www.nasa.gov/wp-content/uploads/2025/08/ochmo-tb-044-medical-operations.pdf); the NASA Arrhythmia report | Medical support comes from the crew and from flight surgeons on the ground; ASTRA's three levels are its own simple version |

## 2. NASA scientific sources (checked against the documents on 15 Nov 2026)

How to read this section:
- **None of these sources provides a validated threshold for ASTRA.** NASA publishes no heart-rate, SpO2, inactivity or radiation-alert values for this prototype. ASTRA's alert rules are the team's own experimental rules and are **not NASA-approved**. NASA guidance only shapes the advice text, the wording and the context.
- Page numbers are PDF page numbers of the files as downloaded on 15 Nov 2026 (for TB-020, TB-031 and TB-044 they equal the printed numbers). "Not verified" means we did not confirm it.
- "Does NOT validate" lists what a reader must not infer from the source.

### 2.1 NASA OCHMO-TB-020 Rev E: Design for Ionizing Radiation Protection
| | |
|---|---|
| Publisher | NASA Office of the Chief Health and Medical Officer (OCHMO), NASA-STD-3001 technical brief |
| Revision | Rev E, dated 12/27/2022 (page 2); covers NASA-STD-3001 Vol 1 Rev B and Vol 2 Rev C |
| URL | https://www.nasa.gov/wp-content/uploads/2023/03/radiation-protection-technical-brief-ochmo.pdf |
| Verified locations | [V1 4030] career limit "less than 600 mSv", universal for all ages and sexes: page 4 (repeated page 13). [V1 4031] design-reference solar particle event (October 1989 events) below 250 mSv: page 6. [V2 6099] Space Weather Monitoring and [V2 6100] Ionizing Radiation Alerting: page 13. GCR shielding gives only about a 7% average reduction: page 7 |
| ASTRA feature informed | The 600 mSv value in the Radiation page's illustrative exposure budget; the framing that space weather needs monitoring and alerting; the statement that ASTRA does not replace NASA's radiation monitoring (`backend/radiation.py`, `docs/RADIATION_MONITOR.md`) |
| Does NOT validate | ASTRA's alert levels 0 to 3, the five-stage outlook or any of its triggers; any conversion from proton flux to dose; the demo background rate and event doses; that ASTRA meets [V2 6099] or [V2 6100]. These are requirements on NASA programs, not on a student prototype |

### 2.2 NASA OCHMO-TB-031: Exercise Overview
| | |
|---|---|
| Publisher | NASA OCHMO, NASA-STD-3001 technical brief |
| Revision | dated 10/02/2023; covers NASA-STD-3001 Vol 1 Rev C and Vol 2 Rev D |
| URL | https://www.nasa.gov/wp-content/uploads/2023/12/ochmo-tb-031-exercise-overview.pdf |
| Verified locations | [V1 4003] In-Mission Aerobic Capacity, "maintained ... at or above 80% of the pre-mission capacity": page 2 |
| ASTRA feature informed | The reason given on the Activity page and in the "no movement" advice for keeping up regular exercise |
| Does NOT validate | The 60-minute stillness rule (`inactivity`), its movement threshold or the 07:00 to 22:00 window. TB-031 describes crew exercise countermeasures, not movement monitoring or alerts |

### 2.3 NASA OCHMO-TB-044: Medical Operations, Spaceflight Considerations
| | |
|---|---|
| Publisher | NASA OCHMO, NASA-STD-3001 technical brief |
| Revision | dated 08/13/2025; covers NASA-STD-3001 Vol 1 Rev C and Vol 2 Rev E |
| URL | https://www.nasa.gov/wp-content/uploads/2025/08/ochmo-tb-044-medical-operations.pdf |
| Verified locations | Flight surgeons and crew medical roles, including the Chief Medical Officer (CMO) who "receives additional medical training" (page 3); telemedicine and remote communication (page 4); Private Medical Conferences (page 5); top priority to communication between the flight surgeon and the crew in an emergency (page 6) |
| ASTRA feature informed | The idea behind ASTRA's three levels of care (self-care, tell the crew medical officer, emergency) |
| Does NOT validate | The three levels themselves, which are ASTRA's own simplification; any notification threshold. **Wording note:** NASA's term is "Chief Medical Officer (CMO)". ASTRA's "crew medical officer" is its own generic wording, not a NASA job title [team to confirm] |

### 2.4 NASA HRP Evidence Report: Risk of Cardiac Rhythm Problems During Spaceflight
| | |
|---|---|
| Publisher | NASA Human Research Program, Human Health Countermeasures Element, Johnson Space Center |
| Revision | Approved for public release June 12, 2017 |
| URL | https://humanresearchroadmap.nasa.gov/evidence/other/Arrhythmia.pdf |
| Verified locations | Section IV.A.4 "Exercise": high-intensity interval exercise has been prescribed (page 11); exercise testing limited to 85% of pre-flight maximal oxygen consumption except in controlled cases, ISS astronauts encouraged to wear heart-rate sensors and log sessions, heart-rate logs can only screen, post-flight reconditioning in the first 45 days (page 12); a crew member may not want to believe symptoms are cardiac because of the impact on the mission (page 27). Exact list of what ASTRA uses: `NASA_ARRHYTHMIA_REPORT_USE.md` |
| ASTRA feature informed | The heart-rate notification advice (why it matters, when to ask for help), the Activity page exercise cards (tagged "adapted from NASA") |
| Does NOT validate | ASTRA's heart-rate rule (today's average against the person's own baseline); any heart-rate or SpO2 threshold; that a fingertip pulse can detect an arrhythmia (the report says an ECG is needed to confirm one). It is not guidance for people who are not astronauts |

### 2.5 NASA HRP Evidence Report HRP-47072: Risk of Reduced Physical Performance Capabilities Due To Reduced Aerobic Capacity
| | |
|---|---|
| Publisher | NASA Human Research Program, Human Health Countermeasures Element, Johnson Space Center |
| Revision | Approved for public release March 9, 2015 |
| URL | https://humanresearchroadmap.nasa.gov/evidence/reports/Aerobic.pdf |
| Verified locations | Executive summary (page 5): maintaining aerobic capacity is a significant concern, and even a 10% fall may affect tolerance to extended work. Other pages not checked [team to confirm which page each Activity card relies on] |
| ASTRA feature informed | Background for the Activity advice |
| Does NOT validate | Any activity, movement or inactivity threshold in ASTRA |

### 2.6 NASA Open Science Data Repository (OSDR)
| | |
|---|---|
| Publisher | NASA (GeneLab and the Ames Life Sciences Data Archive inside OSDR) |
| Revision | live archive, searched on 14 and 15 Nov 2026 |
| URL | https://osdr.nasa.gov (search API: https://osdr.nasa.gov/osdr/data/search) |
| Verified locations | Study entries read at description level only. Studies listed in `OSDR_RESOURCES.md` and `data/reference.json` (OSD-435, 591, 720, 881, 334, 896, 897, 939, 1018, 776, 777, 778, 140, 964, 575, 484, 942, 51), status `needs_review` |
| ASTRA feature informed | The read-only NASA reference panel (`backend/osdr.py`, `backend/reference.py`), labelled `external` |
| Does NOT validate | Anything about ASTRA's readings: the OSDR studies are mostly omics, imaging and animal behaviour data and hold no wearable heart-rate, SpO2 or accelerometer time series, so ASTRA is not validated against them and never compares its readings with them |

### 2.7 Other NASA and agency pages (context only, not re-checked in this audit)
| Resource | Link | Used for |
|---|---|---|
| NASA: Seven ways astronauts improve sleep | https://www.nasa.gov/missions/station/seven-ways-astronauts-improve-sleep-may-help-you-snooze-better-on-earth/ | Rest advice [page content not re-checked on 15 Nov] |
| NASA: How NASA will protect astronauts from space radiation at the Moon | https://science.nasa.gov/science-research/heliophysics/how-nasa-will-protect-astronauts-from-space-radiation-at-the-moon | The Orion shelter idea (stowage bags, food and water) and the statement that forecasting is hard |
| NASA Human Research Program: hazards, risks, ongoing research | https://www.nasa.gov/hrp/hazards/ , https://www.nasa.gov/hrp/risks/ , https://www.nasa.gov/hrp/ongoing-hrp-research/ | Problem framing |
| NASA: The human body in space | https://www.nasa.gov/humans-in-space/the-human-body-in-space/ | Problem framing |
| Canadian Space Agency: monitoring radiation for astronaut health; why we do science in space | https://www.asc-csa.gc.ca/eng/news/articles/2026/2026-02-26-monitoring-radiation-astronaut-health.asp , https://www.asc-csa.gc.ca/eng/iss/science/why-do-we-conduct-science-experiments-in-space.asp | Context |

## 3. Other data and background reading
| Resource | Link | Used for |
|---|---|---|
| NOAA Space Weather Prediction Center: public JSON feeds (GOES proton flux, X-ray flux, scales, alerts). Not NASA data; labelled `external` | https://services.swpc.noaa.gov/ | Live radiation notifications and outlook |
| National Academies: Space Radiation and Astronaut Health (2021) | https://www.nationalacademies.org/read/26155/chapter/5 | Review of the 600 mSv proposal |
| SwRI: radiation exposure of a trip to Mars (Curiosity RAD) | https://www.swri.org/newsroom/press-releases/swri-led-team-calculates-the-radiation-exposure-associated-trip-mars | Daily dose context |
| ANSTO: Artemis II and the invisible hazard | https://www.ansto.gov.au/news/artemis-ii-and-invisible-hazard-on-way-to-moon-part-1 | Context |
| Space.com: how the Artemis II astronauts could weather a solar storm | https://www.space.com/space-exploration/artemis/how-the-artemis-2-astronauts-could-weather-a-solar-storm-during-their-moon-mission | Shelter timing (news report, marked as such on screen) |
| Bain et al. 2021, solar energetic particle forecasting review (Space Weather) | https://doaj.org/article/9783aaa9109d4630902773feb13e25c4 | Why ASTRA does not predict storms |

## 4. Hardware, code and tools
| Resource | Used for |
|---|---|
| ESP32 DevKit (ESP-WROOM-32), MAX30102 heart-rate sensor, ICM-20948 motion sensor, 16x2 LCD, buzzer | The sensor rig |
| [InvenSense ICM-20948 datasheet](https://invensense.tdk.com/wp-content/uploads/2021/10/DS-000189-ICM-20948-v1.5.pdf); [Espressif Arduino-ESP32 I2C API](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/i2c.html) | Wiring and I2C checks |
| [SparkFun MAX3010x library](https://github.com/sparkfun/SparkFun_MAX3010x_Sensor_Library), [SparkFun ICM-20948 library](https://github.com/sparkfun/SparkFun_ICM-20948_ArduinoLibrary), Adafruit SSD1306 and GFX, LiquidCrystal, ArduinoJson (Wi-Fi mode), Arduino ESP32 core 3.3.12 | Firmware |
| Python, Flask, Flask-CORS, SQLite, pytest, requests, pyserial | Backend, tests, USB bridge |
| Chart.js 4.6.1 (MIT, bundled in `frontend/chart.js`) | Charts |
| HTML, CSS, JavaScript | Dashboard |
| Claude Code (Anthropic), an AI coding assistant | Help writing and testing code, documentation and the presentation; see the AI section of the README |

Images and other media used in the presentation: see the credits in the presentation itself.

## 5. Verified NASA technical briefs

- **NASA OCHMO-TB-020, Rev E, page 4, requirement V1 4030:** NASA states a career effective radiation dose limit below 600 mSv. ASTRA uses this as scientific context for the Radiation page. ASTRA does not measure astronaut radiation dose or convert NOAA proton flux into dose.
- **NASA OCHMO-TB-031, page 2, requirement V1 4003:** NASA describes maintaining in-mission aerobic capacity at or above 80% of pre-mission capacity. ASTRA uses this as background for activity guidance. Our motion sensor does not measure aerobic capacity.
- **NASA OCHMO-TB-044, page 3:** NASA describes medical crew roles including Flight Surgeons and the Chief Medical Officer (CMO), as NASA calls the crew member with additional medical training. This informs ASTRA's crew-support concept. ASTRA's three levels of care are our own demonstration design, not official NASA medical procedures.

These sources provide scientific context and guidance, not validated thresholds for the ASTRA sensors. The linked NASA documents remain hosted by NASA.
