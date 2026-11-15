# Dashboard redesign around NASA's five human spaceflight hazards (RIDGE)

Branch `feat/ridge-dashboard-redesign`. Reference: https://www.nasa.gov/humans-in-space/the-human-body-in-space/ . Every item answers three questions: what is happening, why it matters, what to do. No new data are invented; recommendations come from documented rules on real data or are labelled **general NASA-based guidance**.

## 1. RIDGE and what ASTRA can do about each
| Hazard | What ASTRA can use | Where |
|---|---|---|
| **R**adiation | NOAA GOES proton flux (external), simulated scenarios, illustrative exposure budget, illustrative body map. The sensors do **not** measure radiation. | Radiation page, Overview card, Timeline alerts |
| **I**solation and confinement | Self-reported sleep, mood, energy, stress, fatigue and notes; suggestions from the latest check-in; rest regularity from movement | Journal (well-being suggestions), Activity |
| **D**istance from Earth | Last successful update time, "external data unavailable" state, last known values kept on screen. Works offline except the NOAA and OSDR parts | Radiation page, Overview |
| **G**ravity fields | Movement from the ICM-20948 (activity level, a 30-second steadiness check), exercise guidance. No measurement of muscle, bone, fluid shifts or balance | Activity |
| **H**ostile and closed environments | Self-reported discomfort notes only (temperature, noise, sleeping conditions). No air, microbe or immune data exist | Journal ("Spacecraft environment", future development) |

## 2. What changed (frontend)
- **Overview** (`index.html`, `overview.js`): six cards: Radiation status (prominent, replaces the signal card), Heart rate, SpO2, Activity status, Sleep and recovery (only when last night has reliable rest data), Sensors and data. Heart rate and SpO2 values are shown only when the signal is good and the data are current; otherwise `--` with the reason. Radiation shows NORMAL, ELEVATED, HIGH, SEVERE or DATA UNAVAILABLE, never NORMAL without current data.
- **Sensors** (new `sensors.html`, `sensors.js`): "Can I trust the readings?", MAX30102 and ICM-20948 status, last successful measurement, missing data for 7 days, steps for POOR SENSOR SIGNAL, NO FINGER DETECTED and SENSOR UNAVAILABLE. Connection and signal-quality notifications now route here.
- **Timeline** (the panel and `events.js` were removed on 16 Nov 2026 because it was too much text; the notifications above the page keep the advice): panel "Events and what to do" with Information, Recommendation, Warning and Critical alert items, each as What happened, Why it matters, What to do, plus the radiation alert history (7 days).
- **Activity** (`guidance.js`): physical activity message (yesterday vs the earlier days; needs 3 earlier days), sleep and body clock guidance (8 cards, shown as general guidance when sleep data are missing), and a 30-second steadiness check from the motion sensor compared only with the user's own earlier checks (saved in the browser).
- **Radiation** (`radiation.html`, `radiation.js`): redesigned: status card, "What should I do?" (the largest element), notifications, source switch and simulation controls, flux history with S-scale lines and shaded event periods, event history with severity, duration, source and recommended action, simplified exposure budget (details, forms and table folded away), the body map, and a folded "More information" (alert log, OLED preview, NASA research, how to read).
- **Journal** (`wellbeing.js`): well-being suggestions from the latest check-in (sleep difficulties, low motivation, isolation, fatigue, stress), quick environment notes added to the note, and the future-development note on environment sensors.
- **Shared** (`core.js`, `ui.css`): one status vocabulary and color set (green normal, yellow elevated, orange high, red severe, grey unavailable; always text plus a shape), `radState()`, `stateBadge()`, Sensors added to the navigation.

## 3. Backend changes (small)
- `radiation.notice_item` now also returns **Radiation data unavailable** (warning, "do not assume that conditions are normal"; for stale or missing data), **Radiation event ended** (ok, for 6 hours after a recovery alert), and marks a level message as "last known" when the data are not current. Ids: `radiation`, `radiation_data`, `radiation_recovery`; one id per situation, so an unchanged event is never repeated.
- `notices.py`: connection and signal-quality notifications point to `sensors.html` (target `alert-h`).
- Tests: 3 new radiation tests, 2 notice tests adjusted. No schema or endpoint changes.

## 4. Works with the existing hardware
Heart rate and SpO2 status and signal quality (MAX30102), activity status, rest and steadiness check (ICM-20948), sensor reliability, wear time, journal suggestions, NOAA radiation status. The OLED and buzzer parts of the radiation alert need hardware that is not confirmed.

## 5. Needs more data or hardware (not implemented, not faked)
Sleep stages or quality, fatigue or alertness tests (a vigilance test would need a new self-test), balance or vestibular assessment, muscle, bone or fluid measurements, organ-level radiation dose (needs validated transport and phantom models), air quality, temperature, contaminants, microbes, immune response, offline mission guidance packs.

## 6. Limitations
- The "what to do" messages for radiation levels are illustrative interface text, not NASA flight rules. ASTRA cannot authorize or cancel an EVA. Mission procedures and medical personnel are authoritative.
- Thresholds (low activity below 0.6 and high above 1.6 times the usual, sleep shorter than 6 h for the Overview colour, steadiness check rule) are team choices and need review.
- The steadiness check and activity message use movement of the sensor only. They are not medical findings.
- The NOAA S class is space weather, not astronaut dose.

## 7. Timeline guidance and active time (second round)
- **Summary tile:** "Average active time per day" replaces the experimental movement index (`activetime.js`). The day is cut into 30-minute blocks; a block is active when its mean movement index is above 0.05 g (the stillness threshold of the rest analysis). Only days with at least 80% wear time (`GET /api/wear`) count; a day with gaps is left out, never counted as 0.
- **Specific warnings and event recommendations** (`advice.js`, used by the Timeline warnings and "Events and what to do"): what happened (with the real numbers), why it matters, what to do, when to get medical help, and sources. Covered: heart rate higher or lower than baseline (two severities), rest start, reported sleep, connection lost, poor signal, wear time, radiation alerts. Frontend only; the rules that raise a warning are unchanged.
- **NASA guidance is kept apart from ASTRA suggestions** with a label on every step. NASA publishes no heart rate, SpO2 or movement alert thresholds for crews, so none were invented; the limits are each person's own baseline.
- **Research read:** NASA Evidence Report on cardiac rhythm problems (evidence mostly case reports; heart rate sensors encouraged for exercise logs; confirming an arrhythmia needs an ECG), NASA OCHMO TB-031 exercise (aerobic capacity at least 80% of pre-mission, ISS aerobic training at 70 to 100% of maximum heart rate), NASA sleep countermeasures, NASA OCHMO TB-044 medical operations (flight surgeon support). Not read in full: NASA flight rules (not public) and TB-044 beyond its overview.

## 8. Activity, rest strip and text cleanup (third round, branch `feat/activity-sleep-cleanup`)
- **IMU activity** (`imu.js`): active time, light, moderate and high minutes, and still periods of 60 minutes or more, all from the stored acceleration readings (5-minute blocks, existing `GET /api/activity`). The intensity bands are approximate, rounded from adult wrist ENMO cut-points (Hildebrand et al. 2014); the 60-minute inactivity limit is ASTRA's own. Replaces the "experimental movement index" on the Activity and Timeline pages.
- **Today's recommendations** (`today.js`): exercise, movement break, recovery and sleep schedule, adapted to today's activity, last night's rest and the time of day. NASA context (ISS about 2.5 h a day, 6 days a week, individualized by NASA specialists, aerobic capacity at or above 80% of pre-mission) is labelled as context, not as a prescription for every astronaut. Not read in full: the NASA exercise specialist protocols (not public).
- **Rest graph:** one row per night of half-hour cells colored by movement, with the estimated rest period marked. Deep, light sleep and REM are not shown and never inferred from the motion sensor; the graph can draw them, with their own colors and legend, only if a night carries stage data from a compatible source.
- **Text cleanup:** the per-panel "educational prototype" line, the "experimental" chips and long explanatory notes are gone; every page ends with one short line. The generic "tell medical staff" advice is replaced by specific escalation (heart rate symptoms, schedule review through mission channels, hardware faults to the person responsible). Data-source chips and the simulated/live line stay.
- No backend, API or database change.

## 9. Radiation rework (branch `feat/radiation-rework`)
The Radiation page was reduced to three panels (status with what to do and alerts, exposure against NASA's 600 mSv career limit, event history). Removed: the source switch, the flux chart, the body map, the spallation panel (and `GET /api/radiation`), the OLED preview, the NASA research list. Sources and the fact check of the 600 mSv limit are in `docs/RADIATION_REFERENCES.md`. Details: `docs/DASHBOARD.md` section 7c.
