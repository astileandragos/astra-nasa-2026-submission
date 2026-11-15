# ASTRA dashboard: what it looks like, what it shows, how it is built

Status: describes the final dashboard (15 Nov 2026). The pages are listed in section 1; sections 7b and 7c describe the Sensors and Radiation pages, and sections 7d to 7f the pitch set-up (a labelled simulated baseline week plus today from the live sensor), the notification rules and the radiation outlook. The API fields are in `docs/api_contract.md`; every NASA and other source is listed in `docs/RESOURCES.md`.

ASTRA is an educational prototype. The dashboard shows experimental estimates and observations from documented rules. It never diagnoses and never gives medical advice.

---

## 1. The big picture

The dashboard is six pages served by the Flask backend at `http://<LAPTOP_IP>:5000/`. It is plain HTML, CSS and JavaScript (no framework, no build step); the only library is Chart.js, stored locally in `frontend/chart.js`, so it works without internet.

```
 sensors (MAX30102, ICM-20948) -> ESP32 -> Wi-Fi 2.4 GHz -> Flask API -> SQLite -> dashboard
                                                              ^
                       simulator.py + seed_demo.py (simulated data, no hardware needed)
```

| Page | File | One-sentence purpose |
|---|---|---|
| **Overview** | `index.html` | What is happening now, what needs attention, what to do today |
| **Timeline** | `timeline.html` | Trends and exact numbers over 7, 14 or 30 days |
| **Activity** | `activity.html` | Physical activity message, rest at night (from movement), sleep guidance, steadiness check, movement by hour |
| **Sensors** | `sensors.html` | Can the readings be trusted: sensor status, signal quality, missing data |
| **Journal** | `journal.html` | The daily self-reported check-in, well-being suggestions |
| **Radiation** | `radiation.html` | Radiation status with what to do and alerts, daily exposure against NASA's 600 mSv limit, event history |

### The rules every page follows
1. **Every record keeps its own label; a view can combine labelled sources.** Stored records are always `live_hardware`, `simulated`, `external` or `self_reported` and are never relabelled. The dashboard pages use the view `source=dashboard`: earlier days come from the labelled simulated baseline, and today comes from the live sensor if at least one live reading arrived today, otherwise from the simulator. The chips `BASELINE: SIMULATED WEEK` and `TODAY: LIVE SENSOR` or `TODAY: SIMULATOR` say which is which. The simulated baseline is demonstration data: it does not represent real historical measurements of any astronaut. `source=simulated` and `source=live_hardware` (in the address, for example `?source=simulated`) still show a single source.
2. **The source is always visible** (a chip and a line under the page title, plus the switch in the top bar).
3. **Missing means missing.** A value that is not available is shown as `--` or as a gap in a chart, never as `0`.
4. **No medical claims.** Heart rate and SpO2 are labelled experimental estimates. Every observation names its values, its period and its rule.
5. **Self-reported data stays separate.** The check-in is labelled `SELF-REPORTED` wherever it appears, and is never blended into a sensor value.

---

## 2. What every page has: the frame

### 2.1 Top bar
```
 (o) ASTRA   Overview  Timeline  Radiation  Activity  Sensors  Journal   [ Simulated | Live ]  ( Receiving . 05:53:12 PM . every ~2 s )
```
- **Brand** (left): the ASTRA mark and name; selecting it opens the Overview.
- **Navigation:** the six pages (the Radiation page has its own radiation data source switch instead of the device switch and pill). The current page is highlighted (teal tint) and marked for screen readers.
- **No source switch (16 Nov 2026).** The dashboard has one combined view for the pitch: the earlier days are a pre-recorded **simulated baseline week**, today comes from the **live sensor** (or from the simulator if no live reading arrived today). Two chips under every page title say so: `BASELINE: SIMULATED WEEK` and `TODAY: LIVE SENSOR` (or `TODAY: SIMULATOR`). Each reading keeps its own label in the database; only the view combines them. A live reading is compared with a simulated week, so a notification means "different from the simulated baseline", not "measured on Earth". The Sensors page has a **Live demo** panel with the counts and a button that removes today's readings so the demo can start again from zero.
- **Connection pill:** updated every 2 seconds from `GET /api/status`.

| Pill text | Meaning | Style |
|---|---|---|
| `Connecting` | first request not answered yet | neutral |
| `No readings yet` | the server has no reading for this data source | neutral, plus a line "No readings from simulated data yet." |
| `Receiving . 05:53:12 PM . every ~2 s` | the last reading is recent; the interval is the median gap of the last readings | green dot |
| `No new readings . 25 s` | no reading for more than 10 seconds | orange, plus a banner "No new readings for 25 s (last reading at ... ). The values shown are not current." |
| `Server offline` | the server cannot be reached | red, plus a banner "Server not reachable. The values shown are not current." |

When the data is stale or the server is offline, the live values on the Overview are dimmed to 40% so nobody reads old numbers as current.

### 2.2 Page header
Under the top bar: the page title (large), and one **source line**:
- a **chip**: `SIMULATED` (grey, dashed border), `LIVE` (teal, filled dot), `SELF-REPORTED` (indigo, person mark) or `EXTERNAL` (olive, outlined square). The chip always carries a word and a shape, never only a color;
- on the **Overview**: the text "Data source: simulated" (or `live_hardware`);
- on the other pages: the full sentence "You are viewing simulated data. These are not real measurements." or "You are viewing live hardware data: experimental estimates from the sensors."

### 2.3 Notifications for this page (every page except the Overview)
Directly under the page header, every measurement page shows a panel **"Notifications and advice for this page"** at all times (also when you open the page from the top bar, not only after a click). It refreshes every 5 seconds and lists the notifications that belong to that page, then the suggestions for that page. Each item has:
- a status badge (see 3.3);
- a title and a one-line message with the numbers;
- *what it means* in a sentence or two;
- **What to do**: numbered steps. A green item says "No action needed";
- (no disclaimer line in each panel: every page ends with one short line, "ASTRA is an educational prototype, not a medical device. Mission procedures and medical staff are authoritative.")

On the **Timeline** the warnings carry the longer guidance of section 4.6 (what happened, why it matters, what to do, when to get medical help, sources). On the Radiation page this panel sits right under the status and the "What should I do?" box.

The panel the item refers to (for example the rest chart on Activity) gets a teal outline while its notification is orange or red. The panel is hidden when the page has nothing to say.

### 2.4 Layout and phone
- Content is centered, at most 1120 px wide, on an off-white page; content sits in white panels with a thin border.
- Under 840 px two-column layouts become one column. Under 640 px the navigation moves to a **bottom bar** (six items), the source switch and the pill stay at the top, panels get less padding.
- Checked at 375 px wide: no sideways scrolling on any page.

---

## 3. Overview

The page you land on. It answers three questions in order: *what is happening now, what needs my attention, what should I do today?*

```
+----------------------------------------------------------------------------------+
|  Overview                                                                        |
|  [SIMULATED] Data source: simulated                                              |
|                                                                                  |
|  RADIATION STATUS      | HEART RATE            | SPO2 (ESTIMATE)                 |
|  NORMAL                | 75 bpm                | 97 %                            |
|  NOAA S0 . 0.2 pfu     | Above personal        | Within normal range             |
|  Normal radiation act. |   baseline            |                                 |
|  ACTIVITY STATUS       | SLEEP AND RECOVERY    | SENSORS AND DATA                |
|  STILL                 | 4.5 h                 | RELIABLE                        |
|  Normal activity       | Different from usual  | Reliable signal                 |
|                        |   rest                |                                 |
|                                                                                  |
|  NOTIFICATIONS        1 action needed . 1 warning . 3 ok | DAILY SUGGESTIONS      |
|  [ACTION NEEDED] Heart rate higher...  > | Fill in today's check-in             >  |
|  ...                                     | ...                                     |
+----------------------------------------------------------------------------------+
```

### 3.1 The six status cards (refresh: cards every 2 s, radiation 10 s, baseline statuses 60 s)
All cards have the same size (three across; one column on a phone). Each card has a label, one large value and **one short status line** that says how the value compares with the person's own normal. A card is a link to the page that explains it (Radiation, Activity, Sensors). Colors follow section 8b: green normal, yellow caution, orange high, red severe, grey unavailable.

| Card | Value | Status line | Where the status comes from |
|---|---|---|---|
| **Radiation status** | `NORMAL`, `ELEVATED`, `HIGH`, `SEVERE` or `DATA UNAVAILABLE`, with the NOAA class and the flux (`NOAA S0 . 0.2 pfu`) | `Normal / Elevated / High / Severe radiation activity`, with `(simulated)` or `(last known)` when that applies, or `Insufficient data` | `GET /api/radiation/status`. Never NORMAL without current data. A live view reads only the real NOAA feed; a simulated view shows the higher of the two |
| **Heart rate** | the latest value in bpm (`--` unless the signal is good and the data current) | `Within normal range`, `Above personal baseline`, `Below personal baseline` or `Insufficient data` | the rule `hr_vs_baseline` of `GET /api/observation` (today's median against the baseline median, limit 2 x your own day-to-day variation, at least 1 bpm) |
| **SpO2 (estimate)** | the latest value in % (same reliability rule) | same three words or `Insufficient data` | the rule `spo2_vs_baseline` (same method, at least 1 percentage point; needs 3 earlier days and 10 good readings today) |
| **Activity status** | `MOVING` or `STILL` (mean movement of the last 30 readings against 0.05 g), `--` without data | `Normal activity`, `Low activity`, `High activity` or `Insufficient data` | yesterday's mean movement against the earlier days (low below 0.6 x, high above 1.6 x the usual; needs 3 earlier days with 6 hours of data) |
| **Sleep and recovery** (shown only when last night has reliable rest data) | last night's rest duration | `Usual rest pattern`, `Different from usual rest` or `Insufficient data` | the rule `rest_start_vs_usual` |
| **Sensors and data** | `RELIABLE`, `POOR SIGNAL`, `NO FINGER`, `NO NEW DATA` or `NO DATA` | `Reliable signal`, `Unreliable signal`, `Sensors not sending` or `Insufficient data` | the last reading and `GET /api/status` |

There is no graph on the Overview. A value that cannot be trusted shows `--` and "Insufficient data", never `0` and never "normal".

### 3.2 Notifications and Daily suggestions (side by side, equal width)
Both lists refresh every 5 seconds. **Every row is a link**: selecting it opens the page the item belongs to (see 3.4).

### 3.3 The traffic-light system
Color is always paired with a shape and a word, so it never relies on color alone.

| Level | Badge | Color | Meaning (what the person should do) |
|---|---|---|---|
| OK | `● OK` | green | Nothing to do |
| Warning | `▲ WARNING` | orange | Look at it when you can |
| Danger | `◆ ACTION NEEDED` | red | Needs action now |

The panel header summarizes: "1 action needed . 1 warning . 3 ok", or "Everything looks normal" when nothing is orange or red. Rows are sorted red, then orange, then green. The colors say what to do; they are not a medical judgement.

**The rules** (every one is deterministic and uses the data of the selected source only):

| Notification | Page it opens | Green | Orange | Red |
|---|---|---|---|---|
| **Connection** (only for today) | Sensors | last reading within 10 s: "Device is sending" | later than 10 s, or no reading ever: "No new readings" / "Waiting for the first reading" | later than 5 min: "Data stopped" |
| **Heart rate vs your baseline** | Timeline | today's median within your usual variation | outside it ("Heart rate higher/lower than your baseline") | difference more than twice the limit |
| **Rest start** | Activity | last night's rest started as usual | started much earlier or later than usual | not used |
| **Reported sleep** | Journal | within your usual variation | different from your average | not used |
| **Signal quality** | Sensors | 70% or more of today's readings are good | less than 70% (needs at least 10 readings) | not used |
| **Wear time** | Sensors | 80% or more of the day so far has data | less than 80% | not used |
| **Baseline** | Timeline | shown as green information while fewer than 3 days of data exist | not used | not used |

- *Your baseline* = the median of the good-quality heart rate readings of earlier days; a day needs at least 20 good readings and at least 3 days are needed. *The limit* = 2 x the standard deviation of your own daily medians (at least 1 bpm). The comparison with "usual" always uses **your own data**, never a population threshold.
- The red heart rate advice ends with a step telling the person to speak to a colleague or medical staff if they feel unwell; ASTRA cannot assess health.
- The numbers 10 s, 5 min, 70%, 80% and 0.05 g (stillness) are technical settings to be re-checked with real sensor data.

**Daily suggestions** (rows without a badge; a title and one line):

| Suggestion | Shown when | Opens |
|---|---|---|
| Fill in today's check-in | no check-in saved for today (for this source) | Journal |
| Add a note about what changed today | a heart rate, rest or sleep notification is not green | Journal (note field) |
| Review last night's rest | last night has a usable rest period | Activity |
| Wear the sensor tonight | there was not enough overnight motion data | Activity |
| Collect days for your baseline | the baseline is not ready | Timeline |
| Compare today with the last days | always | Timeline |

### 3.4 Routing: where a click goes
Selecting an item opens `page?source=<source>&from=<item id>`. The destination page:
1. shows the matching item in its **"Notifications and advice for this page"** panel with the meaning and the numbered steps;
2. outlines the panel that the item is about;
3. if the item is no longer true when the page loads (for example the check-in was just saved), says "The item you opened is no longer active: the situation it described has changed."

---

## 4. Timeline

Trends and exact numbers in one place: charts on top, the numbers behind them below.

```
+-----------------------------------------------------------------------------+
| [Notifications and advice for this page: detailed, sourced guidance]        |
| SUMMARY                                              [ 7 days | 14 | 30 ]   |
| 8 Nov to 14 Nov . 7 of 7 days with heart rate data . 6148 good readings     |
| [Average HR 74.8 bpm] [Highest 90 bpm, 14 Sat] [Lowest 55 bpm, 9 Mon]       |
| [Average SpO2 97 %]   [Active time 11 h 34 min] [Average reported sleep 7.1 h]|
|                                                                             |
| EVENTS AND WHAT TO DO  (Now / Radiation alerts, last 7 days)                |
|                                                                             |
| HEART RATE AND YOUR BASELINE                                   [SIMULATED]  |
|   baseline ribbon:  62 [=====|=======(Today 75)] 75   71 baseline          |
|   chart: grey bars = daily low to high, teal line = daily median,           |
|          dashed line = baseline, shaded band = your usual range             |
|                                                                             |
| MOVEMENT AND REPORTED SLEEP                                  [EXPERIMENTAL] |
|   chart: bars = movement index (sensor), line = reported sleep (self-rep.)  |
|                                                                             |
| DAILY LOG                                              [Download CSV]       |
|   Day | Readings | HR avg | Low | High | Median | SpO2 | Movement | Sleep ... |
|                                                                             |
| SELECTED DAY                                                                |
|   Saturday, November 14: sensor data and check-in                           |
+-----------------------------------------------------------------------------+
```

### 4.1 Summary
Six tiles over the chosen range (7, 14 or 30 days; the choice is kept while you stay on the page):
- **Average heart rate** over all good readings (weighted by the number of readings of each day);
- **Highest** and **Lowest heart rate**, each with the day it happened;
- **Average SpO2 (estimate)**;
- **Average active time per day** in hours and minutes, from the ICM-20948. The day is cut into 5-minute blocks; a block counts as active when its mean movement is above 0.05 g (light, moderate or high, see 5.1). Only days with at least 80% wear time are used (`GET /api/wear`); a day with gaps is left out. With no such day the tile says "Not enough data";
- **Average reported sleep** and how many check-ins it comes from (self-reported).

A line above the tiles states the period, how many days have heart rate data and how many good readings were used. Days without data are left out, never counted as 0.

### 4.2 Heart rate and your baseline
- **Baseline ribbon:** one horizontal scale. A teal-outlined box is your usual range (the middle half of your own readings on earlier days), a dark tick is the baseline median, a large teal dot is today's median heart rate, with the numbers as text. Under it a sentence says the same in words ("Today's median heart rate is 75 bpm. Your usual range is 62 to 75 bpm, baseline 71 bpm."). Before the baseline exists it says "Your baseline is not ready yet. ASTRA needs 3 days with enough good readings to learn what is usual for you."
- **Chart:** one value per day on the horizontal axis.
  - teal line with dots: the **daily median** heart rate;
  - grey bars: the day's **lowest to highest** good reading;
  - dashed dark line: the **baseline**;
  - pale teal band: **your usual range**;
  - vertical axis: beats per minute, scaled to the data.
- **Tooltip:** hovering or tapping a day shows its date and: median, average, low and high, and the number of good readings.
- **Click:** selecting a day on the chart shows that day in the *Selected day* panel.

### 4.3 Active time and reported sleep
Bars: the **active time** of each day in hours (empty when the day has too little data). Dashed indigo line with diamond marks: the **sleep hours you typed** in the check-in, on the same hours axis. The legend names the two sources; the tooltip shows both values for the day.

### 4.4 Daily log
A table of the exact numbers behind the charts, newest day first, with today highlighted:
`Day`, `Readings`, `Heart rate average`, `Low`, `High`, `Median`, `SpO2 average`, `Active time`, `Sleep (reported)`, `Mood`, `Energy`, `Stress`, `Fatigue`. The day is a button that opens the day in *Selected day*. A button downloads the same range as a CSV file (empty cell = missing). The table scrolls sideways on a phone; the page does not.

### 4.5 Selected day
Two blocks for one day. **Sensor data** (with the source chip): number of readings; heart rate average, median, low, high and the number of good readings; SpO2 average, low and high; active time. **Check-in** (with the SELF-REPORTED chip): sleep, mood, energy, stress, fatigue, or "No check-in for this day." A note repeats that sensor values are estimates and the check-in is what the person typed.

### 4.6 Events and what to do, and the warnings at the top
Both the **"Notifications and advice for this page"** panel and the **"Events and what to do"** panel use the same guidance (`advice.js`), based on the real numbers behind each warning. Every warning has four parts:
1. **What happened**, with the numbers ("Your median heart rate today is 75 bpm, 4 bpm above your own baseline of 71 bpm (usual variation +/-1.8 bpm, so 2.2 times the usual variation).");
2. **Why it matters**, in plain words and with what NASA's documents say;
3. **What to do**, as numbered steps. Each step carries a chip: **NASA GUIDANCE** (something a NASA document says, linked under the text) or **ASTRA SUGGESTION** (a prototype idea of the team, not a NASA procedure and not medical advice);
4. **When to get medical help**, for example chest pain or pressure, a pounding or irregular heartbeat, fainting or shortness of breath at rest, and the instruction to contact the crew medical officer or flight surgeon through the mission medical procedures.

Covered: heart rate above or below baseline (two severities), rest started at an unusual time, reported sleep different from average, connection lost, poor signal, short wear time, and the radiation alerts. The "Events" panel lists the current items (Critical alert, Warning, Recommendation, Information) and the radiation alerts of the last 7 days. NASA publishes no heart rate, SpO2 or movement alert thresholds, so the limits that raise a warning stay each person's own baseline.

The page reloads its numbers every 15 seconds (events every 10 s) and keeps the selected day and range.

---

## 5. Activity

From top to bottom: **Activity today**, **Today's recommendations**, **Rest, last 7 nights**, **Active minutes by hour**, **Sleep and body clock**, **Steadiness check**.

### 5.1 Activity today (ICM-20948)
Calculated from the stored acceleration readings (`GET /api/activity` with 5-minute blocks): the mean distance of the acceleration magnitude from 1 g in each block. Nothing is hardcoded. A block without readings is "no data", never still and never 0.
- **Tiles:** *Active time* (light + moderate + high, and its share of the time with data), *Light*, *Moderate*, *High*, in hours and minutes.
- **Intensity bands (approximate):** still below 0.05 g, light 0.05 to 0.10 g, moderate 0.10 to 0.42 g, high 0.42 g and above. The light, moderate and high limits are rounded from published adult wrist accelerometer cut-points (Hildebrand et al. 2014: about 45, 93 to 101 and 418 to 429 mg). They were made for other devices and shorter epochs, so the page calls them approximate and not validated for this sensor.
- **Still periods:** unbroken runs of still blocks of 60 minutes or more while awake (from the end of last night's rest to now or to the next rest). The 60 minutes is ASTRA's own choice. Needs last night's rest; otherwise the page says so.
- Needs at least 2 hours of data today, otherwise "not enough data".

### 5.2 Today's recommendations
Cards that adapt to today's activity, the last rest and the time of day, each tagged **NASA GUIDANCE** (a NASA document says it) or **ASTRA SUGGESTION** (our idea):
- *Exercise*: what the sensor recorded against the person's own plan; the ISS schedule (about 2.5 h a day, 6 days a week, individualized by NASA specialists; aerobic capacity kept at or above 80% of pre-mission) is shown as context, not as a prescription;
- *Movement break* when still for 60 minutes or more;
- *Recovery* after a day with much more moderate or high movement than usual, or a rest that started much later than usual;
- *Sleep schedule*: a wind-down reminder in the 90 minutes before the usual rest start, otherwise a reminder of the usual rest times; before 3 nights exist it says so;
- *Wear the device* when there is too little data.
Sources are linked under the cards. Recommendations never invent data: with too little data they say so.

### 5.3 Rest, last 7 nights
ASTRA estimates **rest** from the movement of the ICM-20948. It is not sleep staging.
- **Summary sentence:** "Last night you rested from 01:30 to 06:00 (4.5 h)." When there is not enough data: "No rest period found for last night." and the reason.
- **Facts:** *Wake-ups*, *Resting heart rate* (median of the good readings inside the still part), *Night covered by data*.
- **Graph:** one row per night. Each cell is half an hour from 18:00 to 12:00, colored by movement intensity (still, light, moderate, high, no data), with the estimated rest period marked under the cells. A legend names every color.
- **Sleep stages:** deep sleep, light sleep and REM are **not** shown, because the motion sensor cannot measure them and they are never inferred from movement. If a night ever carries stage data from a compatible source (for example a smartwatch), the stages are drawn as colored segments (deep, light and REM have their own colors and legend entries). The current hardware provides none.
- **Your usual times** after 3 earlier usable nights, and the table (`Night ending`, `Rest start`, `Rest end`, `Duration`, `Wake-ups`, `Resting heart rate`).
- **How it is found** (folded away): 30-minute windows from 18:00 to 12:00; a window is "still" when at least 80% of its motion readings are within 0.05 g of 1 g; the rest is the longest still stretch of at least 2 hours; one moving window inside it counts as one wake-up; a night needs motion readings in at least 75% of its windows.

### 5.4 Active minutes by hour
A day selector (today and the 6 days before) and a stacked bar chart: minutes of light, moderate and high movement in each hour (0 to 60). An hour without readings is empty, not zero. One sentence gives the day's active time and the most active hour. It replaces the old "movement index" chart.

### 5.5 Sleep and body clock, and the steadiness check
- **Sleep and body clock:** eight cards of NASA-based guidance (consistent schedule, lighting, sleeping environment, physical activity, recovery, relaxation, fatigue and alertness, journal and support), with a sentence on last night's rest.
- **Steadiness check:** hold still for 30 seconds; the movement is compared only with the person's own earlier checks (saved in the browser).

---

## 6. Journal

The only page where the user types. Two panels.

**Daily check-in** (chip `SELF-REPORTED`; "Typed by you. It is never mixed with sensor data and you can skip any question."):
- **Day:** a date picker; choosing a day with an existing entry fills the form with it.
- **Sleep:** hours, 0 to 24, in steps of 0.5.
- **Mood, Energy, Stress, Fatigue:** five numbered buttons each, 1 to 5, with "1 lowest" and "5 highest" under the scale.
- **Note:** optional, up to 500 characters.
- **Save check-in:** sends the entry. Skipped questions are sent as `null`, never `0`; at least one answer is needed. Saving a day that already has an entry replaces it. A check-in typed here is always stored as `self_reported`; the demo entries seeded without hardware are labelled `simulated`.
- A message under the button confirms the save or explains what to fix.

**Environment (in the form):** quick buttons add "Uncomfortable temperature", "Noise disturbance", "Poor sleeping conditions" or "Environmental discomfort" to the note.

**Well-being suggestions** (chip `SELF-REPORTED`, above the form): from the latest check-in only: sleep difficulties, low motivation or mood, isolation, fatigue, stress, each with one suggested action. Not a diagnosis.

**Spacecraft environment** (chip `FUTURE DEVELOPMENT`): a note that no air, temperature or microbe sensor exists, so no such values are shown.

**Last 7 check-ins:** a table with `Day`, `Sleep`, `Mood`, `Energy`, `Stress`, `Fatigue` and the `Source` chip of each entry.

---

## 7b. Sensors

Answers "can I trust the readings?" (the signal quality is no longer on the Overview).
- **Can I trust the readings?**: one status (`READINGS RELIABLE`, `POOR SENSOR SIGNAL`, `NO FINGER DETECTED`, `SENSOR UNAVAILABLE` or `NO READINGS YET`) with the text and the steps to take (finger position, still hand, sensor contact, wait and measure again).
- **MAX30102** card (heart rate and SpO2) and **ICM-20948** card (motion): status, current signal quality, last reading, last successful measurement, and "Measurements reliable: Yes or No".
- **Missing or unavailable data, last 7 days:** readings, good signal share, poor or no finger, and how many readings lack heart rate, SpO2 or motion.
- The connection and signal-quality notifications open this page. Refreshes every 3 seconds.

## 7c. Radiation

Reworked on 15 Nov 2026 into three panels. The page shows real NOAA space weather (EXTERNAL) by default; there is no source switch. Made-up data appears only after pressing a demo button, and then a yellow **SIMULATED DEMO** banner with an "Exit the demo" link is on top of the page.
1. **Radiation status** (one panel for the status, what to do and the notifications): `NORMAL`, `ELEVATED`, `HIGH`, `SEVERE` or `DATA UNAVAILABLE`, NOAA S class, proton flux and last update. If the NOAA feed is lost it says so and shows the last information received with its time. Inside the panel, **What should I do?** gives one illustrative message per status, the steps of the active alert and the Acknowledge button (illustrative messages, not NASA flight rules; ASTRA cannot authorize or cancel an EVA). Under it, **Latest alerts** lists the three newest alerts (event started, escalated, eased, ended) with time; one alert per change, never repeated for an unchanged event. A folded **Demo** menu starts a simulated storm (quiet, S1 to S4, sample week).
2. **Radiation exposure** (one panel, estimates): **Daily exposure** in mSv/day (the assumed background rate, 0.5 by default, plus event doses of the last 24 hours) and the **career limit of 600 mSv** (NASA-STD-3001 Vol 1 [V1 4030]) with a meter, the share used, what is left and the days left at the background rate. Three **mission** tiles (a demo mission, assumed: 180 days long, today is day 73): mission day, days left and the projected dose at the end against the limit. A 7-day bar chart shows the estimated dose per day: background in grey (it varies by up to 35% from day to day around the average, a simulated variation) and solar events in red. The daily value stays near the background level and jumps only when an event adds dose. For real NOAA data no event dose is estimated (flux is never turned into a dose); a dosimeter reading can be added under "Adjust values", where the mission length, the mission day, the dose received so far (demo default 36.5 mSv) and the background rate can also be set. The demo adds made-up event doses (S1 0.1, S2 1, S3 5, S4 20, S5 60 mSv).
3. **Radiation event history, last 7 days:** severity, start, end, duration, peak flux and the recommended action. The demo button "Sample week" fills it with three simulated past events (S1, S2, S1).

Removed in this rework: the data source switch, the proton flux history chart, the human body exposure map, the simulated spallation panel, the OLED preview and alert log, the NASA research list and the "how to read" text. The sources are saved in `docs/RADIATION_REFERENCES.md`, which also holds the fact check of the 600 mSv limit.

---

## 7e. Changes of 16 Nov 2026 (second part)

- **Navigation order:** Overview, Timeline, Radiation, Activity, **Journal, Sensors**.
- **New notifications:** *No movement for N hours* (still for 60 minutes or more between 07:00 and 22:00, from the ICM-20948; ASTRA's own rule), *Blood oxygen lower/higher than usual* (the existing SpO2 rule, now shown) and *Rest was shorter/longer than usual* (rest length estimated from movement).
- **Sleep hours removed from the check-in.** Rest is estimated from movement and heart rate; nothing about sleep is typed in any more. The backend still accepts an optional `sleep_hours` for old data, but the dashboard does not use it.
- **Plain language:** notifications, advice and the Radiation page were rewritten for readers without medical training (for example "usual" instead of "baseline", "solar storm" instead of "proton flux").
- **Activity advice from NASA's Arrhythmia report:** see `docs/NASA_ARRHYTHMIA_REPORT_USE.md` for exactly what is used.
- **Speed:** the heavy analysis answers are reused for 3 seconds while the data have not changed.

---

## 7f. Radiation outlook (the staged heads-up)

The Radiation page starts with **Get ready: is a solar storm coming?**: five stages (All clear, Watch, Prepare, Build the shelter, Shelter), the one that applies now, what to do (each step labelled FROM NASA or ASTRA EXAMPLE) and the signs ASTRA is watching.

| Stage | When (ASTRA's own thresholds, not NASA rules) |
|---|---|
| Watch | a strong flare (M or X class) in the last 6 h, or a NOAA solar radio burst (type II or IV) in the last 6 h, or NOAA's chance of a radiation storm today is 20% or more |
| Prepare | the particle level is rising (at least 1 pfu and 1.5 times the level 30 minutes ago), or an X-class flare in the last 3 h, or S1 is reached, or NOAA issued a proton warning or watch |
| Build the shelter | S2 or S3 (ASTRA alert level 2) |
| Shelter | S4 or S5 (ASTRA alert level 3) |

**What is true and what is not.** NASA's plan for the Orion capsule is to build a temporary shelter from stowage bags, food and water already on board (NASA science page, see `docs/RADIATION_REFERENCES.md`). NASA also says solar particle storms are hard to predict and the forecast models are early, so ASTRA says on screen that it **cannot predict** a storm: it shows early signs (flares, radio bursts, NOAA's own probability) and the particle level. Reports that building takes 30 to 60 minutes come from news articles on Orion's plan, not from NASA text, and are marked as such. Real missions are decided by mission control and NASA's radiation group.

Data: NOAA GOES X-ray flux (`xrays-6-hour.json`), `noaa-scales.json` (three-day S-scale probability) and `alerts.json`, downloaded at most every 5 minutes. If they are unavailable the page says so and still uses the particle level. The demo menu has **Watch** and **Prepare** buttons (simulated, labelled). The Overview radiation card and the notifications show the Watch and Prepare stages.

---

## 7d. Preparing the pitch

1. `python seed_demo.py --baseline-week --days 7` fills seven earlier days (simulated, device `SEED-SIM`) and leaves today empty.
2. Start the server. Start the ESP32; the first `live_hardware` reading of today switches the page to `TODAY: LIVE SENSOR`. Without hardware, `python simulator.py` fills today instead (labelled simulated).
3. After about a minute (20 good readings) the heart rate and SpO2 rules can fire. Sensors page, Live demo, "Start the live demo again" clears today for another run.

---

## 8. The four data labels on screen

| Label | Where it appears | Chip |
|---|---|---|
| `live_hardware` | readings from the ESP32 (`?source=live_hardware`) | `LIVE` |
| `simulated` | readings from `simulator.py` and `seed_demo.py` (`?source=simulated`) | `SIMULATED` |
| `self_reported` | the check-in typed in the Journal | `SELF-REPORTED` |
| `external` | NASA reference list | `EXTERNAL` |

A view shows one measurement source. The check-in of the matching family appears next to it (self-reported entries beside live data, `simulated` demo entries beside simulated data), always with its own chip.

---

## 8b. The status colors (one vocabulary on every page)
| Status | Color | Used for |
|---|---|---|
| Normal | green | radiation NORMAL, reliable sensor, normal activity |
| Elevated / caution | yellow | radiation ELEVATED, unreliable signal, outside the personal baseline |
| High | orange | radiation HIGH, shelter recommended (simulated exposure) |
| Severe / critical | red | radiation SEVERE |
| Unknown / unavailable | grey | no data, insufficient data |
Always a word and a shape with the color.

## 9. Visual design in short
- **Style:** "Clean Scientific Minimalism": calm, mostly white, type and spacing instead of many boxes.
- **Palette:** page `#F6F7F9`, panels `#FFFFFF`, ink `#0B1B33`, body text `#44546A`, muted text `#5B6B80`, one teal accent `#0E7C86`. Orange (`#8A4B08` on `#FEF3E2`) and red (`#A12116` on `#FDECEA`) are used for the traffic light and connection problems; green (`#17603A` on `#E8F5EC`) for OK. Text colors meet the WCAG AA contrast ratio.
- **Type:** system font (Inter first if installed), tabular figures so numbers do not jump when they update; large 44 px reading numbers, 28 px page titles, 12 px uppercase labels.
- **Spacing:** 4 px unit, 24 px between panels (16 px on a phone), 8 px corner radius, almost no shadow, no animation except a short hover color change.
- **Charts:** heart rate teal, baseline dark dashed, usual range pale teal, movement grey-blue, self-reported sleep indigo.

## 10. Accessibility
- "Skip to content" link, visible 2 px focus ring on every control, 44 px touch targets on a phone.
- Real table headers, labelled form fields and fieldsets, status messages in live regions.
- Every chart has its numbers in a table or a sentence next to it; the baseline ribbon has a text description.
- Status never relies on color alone (word plus shape on every badge and chip).
- Motion is reduced when the visitor's system asks for it.
- Not yet checked: a real screen reader and a real phone.

---

## 11. How it is built

### 11.1 Files (`frontend/`)
| File | Role |
|---|---|
| `index.html`, `overview.js` | Overview |
| `timeline.html`, `timeline.js` | Timeline (charts, ribbon, summary, log, selected day) |
| `activity.html`, `rest.js`, `activity.js` | Activity (`rest.js` = the rest panel, `activity.js` = movement by hour) |
| `journal.html`, `journal.js` | Journal |
| `sensors.html`, `sensors.js` | Sensors |
| `radiation.html`, `radiation.js` | Radiation (status, exposure, event history) |
| `imu.js`, `today.js`, `advice.js`, `activetime.js`, `guidance.js`, `wellbeing.js` | IMU activity metrics (intensity, still periods), Activity today and recommendations, Timeline events and sourced guidance, active time, sleep guidance and steadiness check, Journal suggestions |
| `core.js` | shared: source from the address, `api()` helper, source chips, the top bar and page header, connection status, notification badges, the "for this page" notification panel |
| `ui.css` | the whole design system (colors and spacing are variables at the top) |
| `chart.js` | Chart.js 4.6.1, stored locally |

### 11.2 Data the pages read (backend endpoints)
| Page / panel | Endpoints |
|---|---|
| Top bar pill and banner | `GET /api/status` |
| Overview cards | `GET /api/measurements/latest`, `GET /api/measurements?limit=30`, `GET /api/status`, `GET /api/observation`, `GET /api/activity`, `GET /api/rest`, `GET /api/radiation/status` |
| Overview, notifications and suggestions; "for this page" panels | `GET /api/notifications` |
| Timeline | `GET /api/timeline`, `GET /api/stats/daily`, `GET /api/export.csv`, `GET /api/wear`, `GET /api/activity`, `GET /api/observation`, `GET /api/radiation/events` |
| Sensors | `GET /api/measurements/latest`, `GET /api/measurements`, `GET /api/status`, `GET /api/quality` |
| Radiation | `GET /api/radiation/status|flux|events|body|budget|alert`, `POST /api/radiation/ack|simulate|dose|budget`, `GET /api/radiation` (simulated exposure), `GET /api/reference?topic=radiation` |
| Activity | `GET /api/rest`, `GET /api/activity` |
| Journal | `POST /api/journal`, `GET /api/journal` |

All of them take `?source=` (`simulated` or `live_hardware`) and, where it makes sense, `?date=`, `?days=` or `?nights=`. The fields are in `docs/api_contract.md` (sections 6.1 to 6.17).

### 11.3 Refresh rhythm
| What | Every |
|---|---|
| connection pill, banner, Overview cards | 2 s |
| Radiation status (Overview 10 s, Radiation page 5 s), exposure 15 s | 5 to 15 s |
| Sensors page | 3 s |
| notifications (Overview and "for this page") | 5 s |
| Activity pages | 20 to 30 s |
| Timeline | 15 s |
| Activity rest panel | 30 s |

### 11.4 Safety in the code
- Text that comes from the API is written with `textContent`, never `innerHTML`.
- External links from the reference list open only if they start with `https://`, with `rel="noopener noreferrer"`.
- No external files are loaded: no web font, no CDN.

### 11.5 Where the logic lives
The dashboard only **shows**; the rules live in the backend, so they can be tested and explained:
- `backend/analysis.py`: data quality, daily statistics, baseline, observations (heart rate vs baseline, sleep vs average), movement index, timeline;
- `backend/rest.py`: rest from movement, usual rest times, wear time, the rest observation;
- `backend/notices.py`: notifications, suggestions and advice;
- `backend/radiation.py`, `backend/osdr.py`: radiation status, alerts, the exposure estimate against the 600 mSv limit, the OSDR search;
- `frontend/advice.js` holds the wording of the Timeline guidance (frontend only);
- tests: `backend/test_*.py` (265 tests).

## 12. How to see it
```bash
cd backend
python seed_demo.py --late-bed     # 6 earlier days + today of simulated data (last night starts about 2 h late)
python simulator.py                # a simulated reading every 2 s (second terminal)
python app.py                      # the server (third terminal)
```
Open `http://<LAPTOP_IP>:5000/?source=simulated`. To see the offline and stale states, stop `simulator.py` (orange after 10 s, red notification after 5 min) or stop the server. `?source=live_hardware` shows the empty live view until the ESP32 posts.

## 13. Known limits
- No real ESP32 data has been shown yet; everything above was checked on simulated data.
- Rest is estimated from movement only and its thresholds (30-minute windows, 0.05 g) must be checked with real ICM-20948 data.
- The notification thresholds and the advice wording are the team's choices, not sourced guidance; Ioja Dănuț and Ciolea Daniel review them.
- The NASA reference entries are not yet reviewed against their sources.
- The wording of the Timeline guidance (rest times, symptom lists, re-measure intervals) is ASTRA's own where it is tagged ASTRA SUGGESTION; Ciolea Daniel should check it against NASA's crew medical procedures.
- The radiation alert levels, the daily exposure estimate (assumed background rate, demo event doses) is illustrative; the OLED and buzzer are not confirmed in hardware.
- The Overview statuses reuse the baseline rules; SpO2 and activity thresholds (1 percentage point, 0.6 x and 1.6 x) are team choices.
- Not checked: a real phone, a screen reader, dark mode (not planned).
