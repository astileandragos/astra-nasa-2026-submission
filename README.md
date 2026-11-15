# ASTRA: Astronaut Smart Health Monitoring Platform

NASA Space Apps Challenge 2026 · Cluj-Napoca · Challenge: **Create Health Monitoring Software for Astronauts on Space Missions**

ASTRA helps an astronaut understand their own health when help from Earth is delayed or unavailable. A wearable sensor rig measures heart rate and motion; a local dashboard compares today with the person's own usual values and raises plain-language notifications with practical advice. It is an educational proof of concept, **not a medical device**, not clinically validated, and not connected to NASA systems.

## What it does
- **Dashboard** (`frontend/`): Overview, Timeline, Radiation, Activity, Journal and Sensors pages.
- **Notifications from documented rules** (`backend/notices.py`): heart rate or blood oxygen different from usual, rest started or lasting differently, no movement for a long time, weak signal, gaps in wear time, lost connection, radiation. No hidden model: every rule and threshold is in the code and in `docs/DASHBOARD.md`.
- **Three levels of care** in the advice, because a long mission may have no doctor on board: self-care, tell the crew medical officer, emergency (call the crew for help and mission control at the same time, without waiting for a reply).
- **Radiation outlook** (`backend/outlook.py`): five stages (All clear, Watch, Prepare, Build the shelter, Shelter) from public space-weather alerts. ASTRA does not predict storms and says so.
- **Honest data labels**: every data point is `live_hardware`, `simulated`, `self_reported` or `external`, and they are never mixed. A missing value is `null`, never `0`.
- **Hardware** (`firmware/esp32/`): an ESP32 reads a MAX30102 (heart rate) and an ICM-20948 (motion), shows them on a 16x2 LCD, and sends one measurement every 2 seconds over Wi-Fi or over USB (`tools/serial_bridge.py`). The LCD also shows the current dashboard notification.

Data flow: **sensors → ESP32 → (Wi-Fi or USB) → Flask API → SQLite → dashboard**.

## Run it (about 2 minutes, no hardware needed)
```bash
cd backend
python -m venv .venv
.venv/Scripts/activate            # Windows. On Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python seed_demo.py --baseline-week --days 7   # a labelled, simulated 7-day baseline
python simulator.py &                          # simulated readings for today (device SIM-01)
python app.py                                  # then open http://127.0.0.1:5000
```
Tests: `cd backend && pytest` (254 tests). With the board plugged in over USB, see `firmware/esp32/README.md` for the live demo.

## Demo set-up and honesty
For the demo, the previous 7 days are a **simulated baseline week** and today comes from the live sensor; the dashboard labels both (`BASELINE: SIMULATED WEEK`, `TODAY: LIVE SENSOR`). A warning therefore means "different from the simulated baseline". The thresholds are team choices, not NASA flight rules. The blood-oxygen value is not computed by the current firmware. Low-cost sensors would not survive the noise of microgravity: controlled laboratory validation is the next step.

## NASA and other sources
- NASA Human Research Program, Human Research Roadmap: Arrhythmia evidence report. Used for the heart-rate exercise and rhythm guidance (exact use: `docs/NASA_ARRHYTHMIA_REPORT_USE.md`).
- NASA Human Research Program hazard and risk pages, NASA radiation and shelter guidance: `docs/nasa_references.md`, `docs/RADIATION_REFERENCES.md`.
- NOAA Space Weather Prediction Center public feeds (not NASA; labelled `external`) for the radiation outlook.
- Libraries: Flask, SQLite, pytest, Chart.js (bundled), Arduino ESP32 core, SparkFun MAX3010x and ICM-20948, Adafruit SSD1306/GFX, LiquidCrystal.

## Use of AI (Super Intelligence) tools
Claude Code (Anthropic) helped the team write and test code (backend, dashboard, firmware integration, tests), write documentation and draft the presentation. The team chose the idea, the approach, the rules and thresholds, and reviewed and tested the results. AI-assisted commits carry a `Co-Authored-By` line in the original working repository.

## Repo map
| Folder | What |
|---|---|
| `backend/` | Flask API, SQLite, rule-based health engine, simulator, tests |
| `frontend/` | Dashboard (HTML, CSS, JavaScript, Chart.js) |
| `firmware/esp32/` | ESP32 sketch and set-up guide (secrets stay in a git-ignored `secrets.h`) |
| `tools/` | `serial_bridge.py`: USB link between the board and the dashboard, with tests |
| `hardware/` | Hardware notes |
| `data/` | Sample payloads (always `simulated`) |
| `docs/` | Architecture, data contract (`api_contract.md`), dashboard rules, NASA references |

## Team
Red – Ciolea (product, integration, pitch) · Blue – Dragoș (tech lead, backend) · Green – Roșca (hardware) · Yellow – Răpan (firmware) · Black – Dănuț (frontend and dashboard).
