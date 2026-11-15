# frontend/

The ASTRA dashboard: plain HTML, CSS and JavaScript, Chart.js stored locally (`chart.js`). Owner: Black (Dănuț), shared with Blue. Served by the Flask backend at `http://<LAPTOP_IP>:5000/`. The design and its reasons are in `docs/UI_DESIGN.md`.

## Pages
| File | Page | What it shows |
|---|---|---|
| `index.html` + `overview.js` | Overview | Now (heart rate, SpO2, signal), personal baseline ribbon and trend, color-coded notifications (green, orange, red) and daily suggestions side by side. Each one opens the page it belongs to (`?from=<id>`) |
| `timeline.html` + `timeline.js` | Timeline | Summary (averages, highs, lows), baseline ribbon, heart rate chart (median, low to high, baseline band) with tooltips, movement and reported sleep chart, the daily log table with exact numbers and CSV, selected-day detail. Range 7, 14 or 30 days; click a chart day to select it |
| `activity.html` + `rest.js` + `activity.js` | Activity | Rest per night from movement (start, end, wake-ups, resting heart rate, regularity) and movement index per hour for a chosen day (both experimental) |
| `journal.html` + `journal.js` | Journal | Daily check-in form (skip any question) and the last 7 check-ins |
| `sensors.html` + `sensors.js` | Sensors | Can the readings be trusted: MAX30102 and ICM-20948 status, signal quality, last good measurement, missing data, what to do (see `docs/RIDGE_REDESIGN.md`) |
| `radiation.html` + `radiation.js` | Radiation | Radiation status with what to do and the latest alerts, the daily exposure estimate against NASA's 600 mSv career limit, the event history. Real NOAA data by default; a labelled demo mode for simulated storms |

Shared: `core.js` (top bar, connection status, source chips, and `showPageNotices`: every measurement page shows its own notifications with advice, always), `ui.css` (the whole design system).

## Run
Start the backend (`backend/README.md`), then open `http://<LAPTOP_IP>:5000/?source=simulated`. For the demo without hardware run `python seed_demo.py` and `python simulator.py` in `backend/` first. `?source=live_hardware` shows the ESP32 data. The source is kept when you change page.

## Rules
- One data source per page. Every page says which one (the sentence under the title and the chip). Live, simulated, self-reported and external look different (text plus shape).
- `null` is shown as `--` or a gap, never `0`. Text from the API is written with `textContent`, never `innerHTML`.
- No external files: system font, local Chart.js, so the page looks the same without internet.
- Accessibility: skip link, visible focus ring, labelled form controls, real table headers, live regions for status messages, 44 px touch targets, no information by color alone.
- Colors and spacing are variables at the top of `ui.css`. Change them there, not in the pages.

Also: `guidance.js` (Activity guidance and steadiness check), `wellbeing.js` (Journal suggestions). Overview now has six status cards.
