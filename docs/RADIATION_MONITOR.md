# ASTRA Radiation Risk Monitor: science, design and implementation

Status: written during the 14-15 Nov 2026 hackathon; the first design and the final implementation differ in places, and where they do, `docs/RADIATION_REFERENCES.md` section 0 and `backend/radiation.py` are authoritative (see the notes marked SUPERSEDED below). Educational prototype for NASA Space Apps Challenge 2026. **It does not replace NASA's radiation monitoring and gives no certified medical or flight-safety decisions.**

What we read for this document (so the team knows what is verified and what is not):
- **Read in full:** NASA OCHMO-TB-020 Rev E "Design for Ionizing Radiation Protection" (27 Dec 2022, derived from NASA-STD-3001 Vol 1 Rev B and Vol 2 Rev C), the NOAA SWPC Space Weather Scales page (S-scale), the NOAA SWPC GOES proton flux product page, and the real NOAA JSON files (downloaded and inspected on 14 Nov 2026).
- **Not read directly:** NASA-STD-3001 itself (Volume 1 and 2), the NASA Space Radiation Analysis Group pages, and NASA's other space radiation research pages. What we say about the standard comes from the technical brief, which quotes it. The text of the Volume 2 requirements on space weather monitoring, alerting and dose monitoring (V2 6099 to 6101) was **not** read; only their titles appear in the brief. Ciolea Daniel should read them before the pitch.
- No files were attached to the request; the "uploaded materials" were looked up online.

Everything marked *illustrative* is a team decision for the demo, not a NASA value.

---

## 1. The science in one page

**Three sources of ionizing radiation for astronauts**
| Source | What it is | Behaviour |
|---|---|---|
| **Galactic cosmic rays (GCR)** | high-energy nuclei from outside the Solar System | always present; a slow, continuous contribution to cumulative dose; shielding helps little (TB-020: about 7% average reduction); stronger when the Sun is quiet, because GCR dose and SPE probability are anti-correlated over the 11-year cycle |
| **Solar particle events (SPE)** | bursts of protons accelerated by the Sun | rare and episodic, over hours to days; can give a large dose in a short time; shielding works well (about 50% average reduction for aluminum or polyethylene); most events are small (about 95% only need ALARA) but a few can threaten the crew without a shelter |
| **Trapped radiation** | particles held by a planet's magnetic field (Earth's Van Allen belts) | matters in specific orbits and when crossing the belts; not what the NOAA proton flux describes |

**Quantities that must not be mixed up**
| Quantity | Unit | What it says |
|---|---|---|
| **Particle flux** | particles per cm² per second per steradian; for NOAA protons 1 pfu = 1 proton/(cm² s sr) | how many particles pass through a spot per second, above an energy threshold |
| **Particle fluence** | particles per cm² | flux added up over time |
| **Absorbed dose** | gray (Gy) | energy deposited per kilogram of matter |
| **Equivalent dose** | sievert (Sv) | absorbed dose weighted by how damaging that radiation type is |
| **Effective dose** | sievert (mSv here) | equivalent dose weighted by how sensitive each organ is; the number NASA's limits are written in |
| **Dose rate** | mSv per day | effective dose accumulated per unit time |

**Why proton flux is not dose.** Going from NOAA's flux to an astronaut's effective dose needs the particle energy spectrum, the direction, the spacecraft's shielding around each point, the secondary particles made in the walls and in tissue, and the body model. NASA does this with radiation transport codes and ray tracing (TB-020: dose differs by location inside a capsule, for example 214, 210, 259 and 231 mSv for four crew positions in one example). ASTRA has none of this, so **it never converts flux to dose**.

**Where NOAA's data comes from.** GOES satellites orbit at geostationary altitude. They measure the protons there, which is a good picture of what the Sun is sending out, but it is not the dose inside a spacecraft and not even at the same place as an astronaut. In low Earth orbit the geomagnetic field shields much of the lower-latitude path; beyond it (Moon, deep space) the geostationary picture is closer to reality. The honest statement for the pitch: *GOES tells us a solar radiation storm is happening; it does not tell us how many mSv a crew member received.*

---

## 2. NASA requirements that matter here (as read in TB-020)

| ID | What it says (TB-020 wording, shortened) | How ASTRA treats it |
|---|---|---|
| V1 4029 | ALARA principle | named in the docs; no implementation |
| V1 4030 | Career effective dose from spaceflight radiation **below 600 mSv**, universal for all ages and sexes, calculated with the NASA cancer model of 2012 and 35-year-old female parameters | quoted as context only; the demo budget is **not** this limit |
| V1 4031 | Protect crew from the **design reference SPE** (sum of the October 1989 events) to below a **NASA effective dose of 250 mSv** | quoted as context only; it is a *design requirement for protection against a reference event*, per event, not an alert threshold |
| V1 4032 | Nuclear technologies: below 20 mSv per mission year | out of scope |
| V2 6095 to 6101 | titles only in TB-020: Ionizing Radiation Protection Limit; Crew Radiation Exposure Limits; Radiation Environments; **Space Weather Monitoring**; **Ionizing Radiation Alerting**; **Ionizing Radiation Dose Monitoring** | the last three are what this feature demonstrates; their text must still be read |

Other statements in TB-020 that shape the design:
- "Radiation alerting provides an additional layer of protection to limit exposure to SPEs (early warning allows for crew to safe vehicle and configure shelter)."
- "Timelines of SPEs allow sufficient time for re-configuration."
- "Real-time alert dosimetry also provides a very high level of protection for EVAs if termination occurs within 2 hours and there is access to shielding."
- Shelter guidance: a storm shelter with about 10 cm water equivalent protects against a centennial event; the large majority of SPEs need only ALARA.
- The brief notes the GCR limit "has not been formally adopted but is under consideration".

**How these values must be read (and how the original request was slightly off)**
- 600 mSv is a **career** effective dose limit. It is not a mission length, not a budget for one mission and not "days in space". Dividing 600 mSv by a daily rate gives a meaningless number of days.
- 250 mSv is the **per-event design protection requirement** for the reference SPE. It is not an alarm level and it is not a limit that applies to every event.
- Neither is something a flux number can be compared to.
- **Official NASA requirements** (above) and **our illustrative demo values** (exposure budget, background 0.5 mSv/day, scenario doses, alert levels; the current defaults are in `docs/RADIATION_REFERENCES.md` section 0) are shown separately everywhere in the product. The 0.5 mSv/day default comes from the figure TB-020 uses for a surface mission analysis; it is an assumption, and real rates vary with location, shielding and the solar cycle (TB-020 also uses 1.5 mSv/day for a Mars transit example).

---

## 3. NOAA GOES proton data and how we use it

**Files** (public, no key): `https://services.swpc.noaa.gov/json/goes/primary/integral-protons-{6-hour|1-day|3-day|7-day}.json`. Also `secondary/`, `integral-proton-fluence`, `differential-protons`, and `instrument-sources.json`.

**Record format** (checked on the live file): a JSON list of `{"time_tag": "2026-11-14T15:55:00Z", "satellite": 18, "flux": 0.2438, "energy": ">=10 MeV"}`. Eight energy channels per timestamp: `>=1, >=5, >=10, >=30, >=50, >=60, >=100, >=500 MeV`. Units are pfu. The 1-day file had 285 timestamps for 24 hours (288 would be complete): **gaps happen**.

**Cadence and latency** (measured): 5-minute averages. The HTTP header says `Cache-Control: max-age=60`. The newest sample was about 10 minutes old when fetched. So this is **early warning on a 10 to 15 minute delay, not real-time dosimetry**. NASA's own brief says real-time alert dosimetry onboard is what protects an EVA.

**The S-scale** (NOAA Space Radiation Storms, based on flux of protons at or above 10 MeV):
| Class | Flux | NOAA average frequency per solar cycle | NOAA's wording for astronauts on EVA |
|---|---|---|---|
| S1 Minor | 10 pfu | 50 | none listed |
| S2 Moderate | 100 | 25 | none listed |
| S3 Strong | 1,000 | 10 | "radiation hazard avoidance recommended" |
| S4 Severe | 10,000 | 3 | "unavoidable radiation hazard" |
| S5 Extreme | 100,000 | fewer than 1 | "unavoidable high radiation hazard" |

**What the scale is and is not.** It classifies the *space weather event* from one channel. It is not a dose, has no mSv equivalent and does not describe the inside of a spacecraft. Note that NOAA lists **no EVA hazard for S1 and S2**.

**What ASTRA does with it**
1. A backend refresh reads the 1-day file once, then the small 6-hour file, at most once a minute, in a background thread so a slow or missing network never blocks the dashboard.
2. Only the `>=10 MeV` channel is stored (the one the scale uses). Missing, negative, non-numeric or non-finite values are **skipped, never turned into 0**.
3. Samples are stored in SQLite (`radiation_samples`, source `external`, UTC) and never mixed with simulated samples (source `simulated`).
4. If NOAA cannot be reached, the last data stays, the page says "NOAA could not be reached" and shows how old the data is. The level is **held**, never cleared by missing data.
5. P1: also store `>=100 MeV`. Higher-energy protons penetrate shielding, so the ratio between the two channels says whether the event is "hard" (more worrying). Not built yet.

---

## 4. Architecture

```
A (built)   NOAA GOES JSON --> Flask (fetch, validate, store) --> event detection --> dashboard
                                         |                                      \--> GET /api/radiation/alert --> ESP32 OLED
                                         |
            simulated scenario ---------/   (same code path, source label "simulated")

B (future)  radiation detector --> ESP32 --> Flask --> SQLite --> dashboard   (needs a confirmed sensor)
```

| | A. External data (NOAA) | B. Onboard detector |
|---|---|---|
| Hardware needed | none beyond what we have | a dedicated detector; **not confirmed** |
| Is it a real measurement? | real, but of space weather at GOES, not at the crew | would measure where the crew is |
| Dose | cannot be derived from it | still needs calibration and a conversion; a hobby Geiger tube does not measure space radiation dose credibly |
| Hackathon risk | low; works today | high: parts, calibration, no ground truth in Cluj |
| Failure mode | internet down at the venue | sensor not working |

MAX30102 and ICM-20948 do **not** measure ionizing radiation and are not used here.

**Recommendation: architecture A, plus a clearly labelled simulated scenario.** NOAA is usually quiet (S0), so a live demo needs the simulator to show an event. The simulator uses the same detection code, so the demo shows the real logic. Architecture B stays in the roadmap as the honest answer to "what would a flight system add".

Where the pieces live: `backend/radiation.py` (detection, budget, simulation), `backend/app.py` (endpoints), `backend/notices.py` (Overview notification), `frontend/radiation.html` and `radiation.js`.

---

## 5. Mathematical model: the educational exposure budget

Per data source (`external` or `simulated`), all values in effective dose terms (mSv), all **illustrative**:

```
D_accumulated = D_initial + R_baseline x t_since_start + sum(event and operator doses)
D_remaining   = D_budget - D_accumulated
T_estimated   = D_remaining / R_projected        (days; R_projected = R_baseline)
```
- `D_budget`: configurable budget. **SUPERSEDED:** the first design used 100 mSv ("not 600 mSv"); the implemented default is NASA's 600 mSv career limit (`CAREER_LIMIT_MSV`), still an illustrative budget, not a safe mission duration.
- `D_initial`: dose already accumulated when the demonstration starts. **SUPERSEDED:** the first design used 20 mSv; the implemented default is 36.5 mSv (a demo mission of 180 days, day 73, at 0.5 mSv/day).
- `R_baseline`: assumed background effective dose rate (default 0.5 mSv/day).
- `t_since_start`: days since the budget was first read.
- Event doses: from a labelled **simulated event** (illustrative values 0.1, 1, 5, 20 and 60 mSv for S1 to S5, chosen by the team, **not derived from flux**) or entered by an operator (for example a dosimeter reading).
- If `R_baseline` is 0 the estimate is shown as unknown, not infinite. If `D_remaining` is 0 or less the days are 0 and the budget is marked used up.

**Example (first design, SUPERSEDED defaults; the arithmetic is unchanged):** budget 100, initial 20, rate 0.5 gives 80 mSv remaining and 160 days. A simulated S4 event adds 20 mSv: remaining 80 to 60 mSv, estimated days 160 to 120. With the implemented defaults (budget 600, initial 36.5, rate 0.5) the remaining budget starts at 563.5 mSv. The page says exactly that, in a sentence, so the change is explained: *"Simulated S4 event: +20 mSv. Remaining budget 80 -> 60 mSv; estimated remaining days 160 -> 120 at 0.5 mSv/day."*

**Why this is only a teaching model**
- A constant rate is a strong simplification. Real rates depend on location, shielding, EVA time and the solar cycle.
- A budget is not how NASA limits exposure (career risk with age and sex, per-event protection, ALARA).
- Therefore the output is worded "estimated days **at the assumed background rate, within the illustrative budget**", never "safe mission duration".

**What we deliberately do not do:** convert pfu to mSv, or let a NOAA event change the budget by itself. For real data the budget only changes when someone enters a dose; the page says so. If a valid conversion becomes available (P2: radiation transport with a shielding model, for example NASA's OLTARIS tool; named from memory, not checked), it would be added as a separate, labelled `model_estimate` input.

---

## 6. Alert state machine

**Levels** (ASTRA demonstration states, **not NASA flight rules**):
| Level | Name | NOAA class that triggers it | Colour and mark |
|---|---|---|---|
| 0 | NORMAL | below S1 | green, OK |
| 1 | ELEVATED | S1 | orange, warning |
| 2 | HIGH | S2 or S3 | red, action needed |
| 3 | SEVERE | S4 or S5 | red, heavy border, action needed |

*Deviation from the original proposal, with the reason:* the brief put "seek the shelter" at level 2. NOAA lists no EVA hazard at S1 and S2 and "avoidance recommended" at S3, and NASA says SPE timelines leave time to reconfigure. So level 2 says **avoid or postpone EVA and be ready for the shelter**; **"shelter now" is level 3** (S4 and above, where NOAA calls the EVA hazard unavoidable). Easy to change in `ALERT_TEXT` if the team prefers otherwise.

**Detection** (all counts are consecutive 5-minute samples of the `>=10 MeV` flux; a gap longer than 30 minutes restarts the counters):
| Transition | Rule |
|---|---|
| **onset** 0 to L | the last **3** samples are all at or above S1; L is the **lowest** level among them. The event starts at the first of those samples |
| **escalation** L to L' (higher) | the last **2** samples are all above L; L' is the lowest of them |
| **easing** L to L' (lower) | the last **6** samples (30 min) are all lower than L, judged with thresholds **x 0.5** (hysteresis) |
| **recovery** L to 0 | the same as easing with L' = 0; the event ends at the first sample of that quiet run |

```
            3 samples >= S1                 2 samples above L
  NORMAL(0) ----------------> L1..L3 --------------------------> higher level
      ^                         |  ^
      |   6 samples < L/2       |  |
      +-------------------------+  +---- 6 samples lower (x0.5): easing to a lower level
```
- **No duplicates by construction.** The state is computed by **replaying the stored samples**. An alert exists only at a transition and has a deterministic id (`source:event-start:sequence`), so the same samples always give the same alerts, a steady event gives exactly one alert, and recomputing cannot create a second one.
- **Acknowledgement.** Onset and escalation alerts ask for one. Acknowledging (dashboard button or ESP32 button) stops the repeating sound and the "BTN = ACKNOWLEDGE" prompt but **does not lower the level**. A new escalation asks again. Easing and recovery are information only.
- **Hysteresis.** A flux hovering around 10 pfu does not flip the level: it must fall below 5 pfu for 30 minutes to recover.
- **Missing or delayed data.** `data_status`: `ok` (newest sample up to 15 min old), `delayed` (15 min to 2 h), `stale` (older), `no_data`. The level is **held** when data is late and the OLED footer says DATA DELAYED or DATA STALE. Missing values are never read as zero flux.
- **Why these numbers:** 3 samples for onset mirrors how NOAA lists events (to be verified by Ciolea Daniel); 2 for escalation reacts faster once an event exists; 6 samples and a 0.5 factor are deliberately slow so the display does not flicker. They are illustrative parameters in `backend/radiation.py`.
- **Honest limit:** the 5-minute averages and about 10 minutes of delay mean the first alert comes roughly 20 to 30 minutes after the flux crosses a threshold. That is why NASA emphasises onboard real-time dosimetry for EVA.

---

## 7. OLED messages and the ESP32 contract

Display: SSD1306 128x64 text size 1 = **4 lines of 21 characters** plus a footer line. (The OLED model, address and library were **not confirmed**. On the board used for the final demo the OLED was **not detected**, and these radiation messages are **not sent to the board by an endpoint poll**: the board's 16x2 LCD shows the dashboard notifications, including radiation, through `tools/serial_bridge.py`. This section is the original design and is not a description of the final hardware.)

| Level | Line 1 | Line 2 | Line 3 | Line 4 | Sound |
|---|---|---|---|---|---|
| 0 | `RADIATION: NORMAL` | `S0 0.26 pfu >=10MeV` | `NOAA 16:05Z` | `No action needed` | none |
| 1 | `RAD 1 ELEVATED` | `S1 42 pfu >=10MeV` | `Monitor the situation` | `Review conditions` | one short beep |
| 2 | `RAD 2 HIGH` | `S3 1359 pfu >=10MeV` | `No EVA. Be ready for` | `shelter. Stand by.` | two beeps, repeated until acknowledged |
| 3 | `RAD 3 SEVERE` | `S4 38759 pfu >=10MeV` | `SHELTER NOW` | `Await mission ctrl` | continuous tone until acknowledged |

Footer: `BTN = ACKNOWLEDGE` while an alert waits for acknowledgement, `DATA DELAYED`, `DATA STALE`, or `NO DATA`. Once acknowledged the sound stops and the footer clears; the level stays.

**Escalation and return to normal on the display:** the screen shows the current level at all times; a higher level replaces it and asks again. When the machine recovers, the screen says NORMAL; it does not claim "all clear to resume EVA" (the dashboard alert text says to wait for mission control).

**Firmware contract** (for Râpan Andrei; this branch does not touch `firmware/`):
- Poll `GET /api/radiation/alert?source=external` every 10 to 30 s. The answer is already formatted for the display:
```json
{"source":"external","level":3,"s_class":4,"data_status":"ok","alert_id":"simulated:20261114T130000Z:3","ack_pending":true,
 "lines":["RAD 3 SEVERE","S4 38759 pfu >=10MeV","SHELTER NOW","Await mission ctrl"],"footer":"BTN = ACKNOWLEDGE",
 "beep":"continuous","repeat_until_ack":true,"updated_at":"2026-11-14T16:15:00+00:00"}
```
- On the button press: `POST /api/radiation/ack` with `{"alert_id": "<alert_id>"}`.
- If the server cannot be reached: keep showing the last answer and add `SERVER LOST` with its age; never clear an alert because the connection dropped.
- Do not poll NOAA from the ESP32: the backend does the fetching, validation and replay.

---

## 8. Backend changes (contract section 6.15)

| Endpoint | Purpose |
|---|---|
| `GET /api/radiation/status?source=` | level, S class, flux, data status, alert text, OLED preview, thresholds, what the data is |
| `GET /api/radiation/flux?source=&hours=` | flux history with the S-scale thresholds |
| `GET /api/radiation/events?source=&days=` | events and alerts, newest first |
| `GET /api/radiation/alert?source=` | compact answer for the ESP32 |
| `POST /api/radiation/ack` | acknowledge an alert |
| `POST /api/radiation/refresh` | fetch NOAA now |
| `POST /api/radiation/simulate` | `{"scenario": "quiet|s1|s2|s3|s4"}` or `{"flux_pfu": n}` (simulated data only) |
| `GET/POST /api/radiation/budget` | the illustrative budget and its settings |
| `POST /api/radiation/dose` | an operator-entered dose |

`source` is `external` (NOAA, the default) or `simulated`; the two are never mixed (separate samples, separate budgets). New tables: `radiation_samples`, `radiation_dose`, `radiation_ack`, `radiation_meta`. `/api/notifications` gains a `radiation` item for the Overview. Labels follow the project rules: NOAA flux is `external`; scenario samples and scenario doses are `simulated`; operator doses are `self_reported`; the budget is marked `kind: illustrative_model`.

---

## 9. Dashboard: the Radiation page (reworked 15 Nov 2026: see docs/DASHBOARD.md section 7c)

A sixth page, **Radiation** (`radiation.html`), minimalist like the others:
1. **Data source** switch: *NOAA GOES (real)* or *Simulated scenario*, with a sentence saying what each is. The page header carries the `EXTERNAL` or `SIMULATED` chip and "Data source: ...".
2. **Current radiation status:** a large level card (LEVEL 0 to 3 with the name, colour, shape and the NOAA class), the flux, the data age and status, the recommended actions as numbered steps, the *Acknowledge* button, and a **preview of the OLED** exactly as the ESP32 gets it.
3. **Proton flux history:** logarithmic chart (6 h, 24 h, 3 days) with the S1 to S5 thresholds as dashed lines and tooltips with exact values.
4. **Event timeline** and **latest alerts with recommended actions** (acknowledged or not).
5. **Remaining radiation exposure budget:** budget, accumulated, remaining, estimated days, a progress bar, the formula, *why it changed* in one sentence, a table of entries with their origin chip (simulated event, operator-entered), the assumptions, and the forms to enter a dose or change the settings.
6. **Simulation controls** (simulated source only): Quiet, S1 to S4 storm, add one sample.
7. **How to read this page:** the four kinds of data (EXTERNAL, SIMULATED, ILLUSTRATIVE MODEL, SELF-REPORTED), and the official NASA values kept apart from the demo values.

The Overview also shows a **Space radiation** notification (green when NOAA is quiet and current, orange or red during an event) that opens this page, which shows the advice. The page does not show the heart rate source switch or connection pill because it is about space weather, not the sensors.

Not built (ideas): an alert history chart over weeks, `>=100 MeV` hardness, Kp and X-ray flare context from other SWPC products, and a link to mission-planned EVA times.

---

## 10. Implementation status
The Radiation page, the endpoints, the alert state machine, the budget and the simulated scenarios are implemented and covered by `backend/test_radiation.py` and the other backend tests. The hackathon task table that stood here is not reproduced. Parts of the original design that depend on an OLED, a button or a firmware poll of the radiation endpoint were **not built** (see section 7); the board's LCD shows the dashboard notifications through `tools/serial_bridge.py`.

## 11. Critical review of the assumptions in the request
1. **"Estimated remaining mission duration"** is the most misleading phrase. Dividing a budget by a rate gives days only inside the assumptions. We show it as *days at an assumed background rate within an illustrative budget* and list the assumptions on the page.
2. **600 mSv and 250 mSv** are a career limit and a per-event design requirement. They are shown as official context, never as a budget or an alarm level.
3. **NOAA proton flux is not dose, and not at the crew's location.** The page says it in the status card and the "How to read" panel.
4. **Real-time claims.** 5-minute averages with about 10 minutes of delay are not real-time. The detection is a ground-based early warning; NASA stresses onboard dosimetry for EVA.
5. **Level 2 wording** was adjusted to match NOAA's EVA wording (see section 6).
6. **The single `>=10 MeV` channel** is what the S-scale uses but is a rough proxy; higher-energy protons matter for shielding. Planned for P1.
7. **A quiet Sun makes a boring demo.** The simulated scenario is the honest fix, clearly labelled.
8. **Alert levels invented for a prototype** must never be presented as NASA flight rules; the interface says so.

## 12. Open questions
The NOAA event definition (3 consecutive samples), the exact wording of NASA-STD-3001 Vol 2 [V2 6099] to [V2 6101] and the thresholds are the team's choices and have not been reviewed by a radiation specialist. Hardware questions (OLED, buzzer, button) are tracked in `hardware/README.md`.

---

## 13. Human Radiation Exposure Map: removed

The organ map was removed on 15 Nov 2026 (too much for the demo). The research notes (NASA estimates organ dose with transport codes and phantoms, ICRP weights, why a depth rule is only illustrative) are in the git history of this file before this commit. The Radiation page now shows a daily exposure estimate against NASA's 600 mSv career limit; see `docs/RADIATION_REFERENCES.md` for the fact check and the sources.
