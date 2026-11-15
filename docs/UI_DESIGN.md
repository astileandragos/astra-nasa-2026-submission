# ASTRA UI design proposal: "Clean Scientific Minimalism"

Status: proposal and first implementation on branch `design/clean-scientific-ui`, for review. Nothing here changes data, endpoints or medical wording. It changes how the data is shown.

References used: *Refactoring UI* (chapter headings: hierarchy, start with too much white space, a spacing and sizing system, fewer borders, do not rely on color alone, limit your choices), WCAG 2.2 success criteria 1.4.3 and 1.4.11 (text contrast 4.5:1, large text 3:1, non-text 3:1), and the Material 3 ideas of a fixed type scale, a small set of color roles and one navigation pattern. The Material 3 type page did not load for me (it needs JavaScript), so I used the standard M3 role names from memory, not their numbers. The Figma Community link is a gallery, not a specification, so it was not used.

## 1. Visual direction: a quiet instrument
ASTRA should feel like a calm instrument panel, not a game and not a generic SaaS template. Four decisions follow from that:
1. **One idea per screen.** The Overview answers four questions in order: is it connected, what is it reading now, how does today compare with my own normal, and what did ASTRA notice and why. Everything else lives one click away.
2. **Type before boxes.** Structure comes from size, weight and spacing, not from many bordered cards (Refactoring UI: use fewer borders). Surfaces are white on an off-white page, with one hairline border and almost no shadow.
3. **One accent.** Muted teal marks what is interactive and what is "ASTRA's own" (the baseline, the observation). Amber and red are kept for connectivity problems only, so they keep their meaning.
4. **Honest data labels are part of the design.** Every value carries a source tag, and the tags differ by shape and text, not only by color.

## 2. Palette (exact HEX, contrast checked against WCAG AA)
| Role | HEX | Use |
|---|---|---|
| Page | `#F6F7F9` | background |
| Surface | `#FFFFFF` | panels |
| Surface subtle | `#EEF1F5` | chips, table stripes |
| Hairline | `#E3E7EC` | panel borders |
| Control border | `#77879C` | inputs, buttons (3.66:1 on white, meets 3:1 for UI parts) |
| Ink (navy) | `#0B1B33` | headings, numbers (17.2:1 on white) |
| Text 2 | `#44546A` | body text (7.7:1) |
| Muted | `#5B6B80` | labels, captions (5.4:1 on white, 5.1:1 on the page) |
| Accent | `#0E7C86` | links, focus ring, HR line (4.95:1 on white, 4.61:1 on the page) |
| Accent strong | `#0A5F67` | accent text on tint, hover (6.5:1 on tint) |
| Accent tint | `#E4F3F4` | baseline band, selected nav, LIVE chip |
| Warning | text `#8A4B08` on `#FEF3E2`, border `#F2D9AE` | no new readings (6.2:1) |
| Error | text `#A12116` on `#FDECEA`, border `#F3C2BD` | server not reachable (6.7:1) |

**Source tags** (always text plus a shape):
| Source | Chip | Colors |
|---|---|---|
| Live | `LIVE` with a filled dot | `#0A5F67` on `#E4F3F4` |
| Simulated | `SIMULATED` with a dashed border | `#44546A` on `#EEF1F5`, border `#77879C` dashed |
| Self-reported | `SELF-REPORTED` with a person mark | `#3B4590` on `#ECEEF8` |
| External | `EXTERNAL` with an outlined square | `#6A5624` on `#F4EFE2` |

Chart colors: heart rate `#0E7C86`, baseline median `#0B1B33` dashed, baseline usual range `#E4F3F4`, movement `#6F819A` (3.98:1, meets 3:1 for graphics).
Why teal and not blue: a NASA-blue palette would look like every other space project and would clash with our own source colors. Muted teal is calm, reads as "instrument", and stays distinct from amber and red. Why not neon: it fails contrast on white and tires the eyes.

## 3. Typography
- **Family:** `Inter` if it is installed, otherwise the system UI font (`Segoe UI Variable`, `Segoe UI`, `system-ui`, Roboto). We do **not** load a web font: the earlier decision to make the page work without internet stays. If you want Inter exactly, add the font file to `frontend/` yourself (the page already lists it first) and tell me.
- **Numbers:** tabular figures everywhere (`font-variant-numeric: tabular-nums`), so values do not jitter when they update every 2 seconds.
- **Scale (px):** 12 label, 14 small, 16 body, 20 section title, 28 page title, 44 hero number. Weights 400, 500, 600. Line height 1.5 for text, 1.1 for numbers. Labels are 12 px uppercase with 0.06 em spacing in Muted. Text stays under about 70 characters per line.

## 4. Spacing and layout
- **Base unit 4 px,** scale 4, 8, 12, 16, 24, 32, 48, 72. Panel padding 24. Gap between panels 24 (16 on a phone). Section spacing 48.
- **Content width 1120 px,** centered. Two columns on the Overview (7/5 split), one column under 840 px. The page is allowed to leave empty space (Refactoring UI: you do not have to fill the whole screen).
- **Radius 8 px.** Shadow only `0 1px 2px rgba(11,27,51,0.05)`. No gradients, no blur, no animation except a 120 ms color change on hover. `prefers-reduced-motion` is respected.
- **Accessibility:** visible 2 px accent focus ring, a "Skip to content" link, 44 px touch targets on a phone, tables with real headers, status messages in a live region, and every chart has a text summary next to it.

## 5. Navigation concept
Five pages, one bar. **Overview, Timeline, Activity, Journal, Data.**
- Desktop: a slim top bar. Brand on the left, the five pages next to it, on the right the **data source switch** (Simulated / Live) and a **connection pill** ("Live, updated 15:18:07" or "No new readings for 25 s").
- Phone: the same five items as a bottom bar. The source switch and the pill stay at the top.
- Below the bar, every page shows one sentence in the source's style: "You are viewing SIMULATED data. These are not real measurements." (or LIVE). This is the single place a viewer learns which kind of data they see.
- **Data** holds what the jury may ask about but a user rarely needs: data quality, CSV export and the NASA reference list (always EXTERNAL).

## 6. Overview wireframe
```
+--------------------------------------------------------------------------------+
| ASTRA   Overview  Timeline  Activity  Journal  Data      [Simulated|Live] (o)  |
+--------------------------------------------------------------------------------+
|  (strip, only when something is wrong)  No new readings for 25 s ...           |
|                                                                                |
|  Overview                                              SIMULATED  Updated 15:18|
|  You are viewing simulated data. These are not real measurements.              |
|                                                                                |
|  NOW                                                                           |
|  Heart rate         SpO2 (estimate)        Signal                               |
|  75 bpm             98 %                   Good                                 |
|  ~~~ sparkline ~~~  last reading 15:18:07  motion index 0.02                    |
|                                                                                |
|  YOUR BASELINE (7/12)                       LATEST OBSERVATION (5/12)           |
|  Today 75 bpm, usual 63 to 74               "Today's median heart rate is       |
|  [----|=======o=====]-----(*)  +5           higher than your baseline."         |
|   baseline range / median / today           WHY: today 75 | baseline 70 |       |
|  7-day trend (line + band)                  difference +5 vs limit 1.6          |
|                                             RULE: ...    LIMITS: not a diagnosis|
|                                                                                |
|  TODAY AND THE LAST DAYS  (unified timeline, 7 days)            Open timeline > |
|  Heart rate   o   o   o   o   o   o   (o)                                       |
|  Movement     |   |   |   |   |   |   |                                         |
|  Check-in     7h  7h  7.5 7   7.5 7   7                                         |
+--------------------------------------------------------------------------------+
```
Order follows the brief: connectivity (bar and strip), current readings, trend and baseline, the explainable observation, then a compact timeline. Activity detail, history, the journal and data quality are on their own pages.

## 7. Three distinctive components
1. **Baseline ribbon (Personal Baseline).** One horizontal scale: the person's usual range (middle half of their own readings) as a soft teal band, the baseline median as a tick, today as a filled marker, and the difference as text. It turns "am I different from my normal?" into one glance and replaces a generic chart. It reads as text too ("Today 75 bpm, your usual range is 63 to 74"), and the marker is never the only carrier of the message.
2. **Insight card (Explainable Insights).** Four short parts in a fixed order: the **statement**, **why it appeared** (the numbers it used, the period, the difference against the limit), the **rule** in plain words, and the **limits** (educational prototype, not a diagnosis). The order never changes, so the user learns where to look. It is teal, not amber: an observation is information, not an alarm.
3. **Day strip (Unified Timeline).** One column per day and three aligned lanes: heart rate median against the baseline band, movement, and the self-reported check-in. Sensor lanes and the check-in lane look different (the check-in carries the SELF-REPORTED mark), so combining them never blurs where a value came from. Days with no data show a dash, never a zero.

## 8. What is deliberately not here
No neon, glass, gradients, animation or dark "mission control" theme. No new measurements, no medical scores, no predictions, no integrations. Mood, energy, stress and fatigue stay labelled self-reported. The only new backend code is a read-only `GET /api/timeline` that combines data the server already has.

## 9. Questions for the review
- Teal accent: keep, or try a deeper navy accent?
- Five pages and the names (Overview, Timeline, Activity, Journal, Data): clear for a jury that sees it for two minutes?
- Should the source switch stay in the top bar, or only on the Data page for the final demo?
- Inter: do you want the exact font added to the repo?

## 10. What is on the review branch
Branch `design/clean-scientific-ui` implements this proposal so it can be reviewed in the browser. Open `http://<LAPTOP_IP>:5000/?source=simulated` (after `python seed_demo.py` in `backend/`).
- New pages: Overview, Timeline, Activity, Journal, Data (`frontend/*.html`), one shared `core.js` and one `ui.css`. The earlier single-page dashboard (`app.js`, `analysis.js`, `extras.js`, `style.css`, `analysis.css`) is removed on this branch; it stays in git history on `main`.
- Backend: one small read-only addition, `GET /api/timeline` (contract section 6.11), with tests (100 tests pass in total). No other endpoint changed.
- Checked in the browser: all five pages with simulated data, the empty live state, the stale and offline states, the journal save (with skipped questions sent as `null`), keyboard-visible focus styles, and a 375 px phone width with no sideways scrolling on any page.
- Not done or not checked: a real phone, a screen reader, the exact Inter font (the system font is used), dark mode (not planned), and a review by Black of the wording.

## 11. Change after the first review: Overview
Requested after the review, built on branch `feat/rest-regularity-wear`:
- **Removed from the Overview:** the 7-day strip (it lives on the Timeline page), the "Latest observation" panel, and the sentence saying the values are not real. The data source stays visible: the `SIMULATED` or `LIVE` chip and the line "Data source: simulated" (or `live_hardware`) under the title, plus the Simulated / Live switch in the top bar. The other pages keep the full sentence.
- **Notifications:** a traffic-light list. Green (OK, nothing to do), orange (warning), red (action needed). The color is always paired with a shape and a word (`●` OK, `▲` Warning, `◆` Action needed) so it never relies on color alone. The rules are in contract section 6.14; red is used for data that stopped for 5 minutes or a heart rate far outside the person's own usual range, never as a diagnosis.
- **Daily suggestions:** a short list (check-in, note, rest, baseline, compare days), based on what is missing or notable today.
- **Routing and advice:** selecting an item opens the related page with `?from=<id>`. That page shows a "What to do" or "Today's suggestion" panel with the meaning and numbered steps, and highlights the related panel.

## 12. Second review round: Overview, Timeline, measurement pages
- **Overview:** now only "Now", then Notifications and Daily suggestions side by side (stacked on a phone). The baseline graphics moved to the Timeline.
- **Timeline:** a summary (average, highest and lowest heart rate with the day, average SpO2, movement and reported sleep), the baseline ribbon, a heart rate chart (daily median, low to high, baseline band) and a movement and reported sleep chart, both with tooltips that show the exact numbers, a daily log table with the same numbers (plus CSV), and the selected-day detail. Range buttons: 7, 14, 30 days. Selecting a chart day or a table row shows that day. The old day strip is replaced by the charts and the table.
- **Measurement pages (Timeline, Activity, Journal, Data):** each shows "Notifications and advice for this page" at the top at all times: the traffic-light status, what it means and numbered steps. Green items say "No action needed". The panel a notification refers to is outlined while it is orange or red.
