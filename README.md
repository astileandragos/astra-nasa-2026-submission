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

## NASA data and resources used (and the notification each one feeds)
NASA publishes no heart-rate, blood-oxygen or movement thresholds for crew alerts, so none are invented: the triggers are ASTRA's own rules, and the NASA documents shape the advice. Every advice step is tagged `NASA GUIDANCE` or `ASTRA SUGGESTION` on screen. **Full list with links: [`docs/RESOURCES.md`](docs/RESOURCES.md).**

| Notification | NASA and other resources |
|---|---|
| Heart rate higher or lower than usual | [NASA HRP Arrhythmia evidence report](https://humanresearchroadmap.nasa.gov/evidence/other/Arrhythmia.pdf) ([exact use](docs/NASA_ARRHYTHMIA_REPORT_USE.md)), [NASA OCHMO TB-031 Exercise](https://www.nasa.gov/wp-content/uploads/2023/12/ochmo-tb-031-exercise-overview.pdf), [NASA OCHMO TB-044 Medical Operations](https://www.nasa.gov/wp-content/uploads/2025/08/ochmo-tb-044-medical-operations.pdf) |
| Blood oxygen different from usual | No NASA numbers exist; safe steps only |
| Rest started late, rest too short or long | [NASA: Seven ways astronauts improve sleep](https://www.nasa.gov/missions/station/seven-ways-astronauts-improve-sleep-may-help-you-snooze-better-on-earth/), NASA HRP hazards and risks |
| No movement | NASA HRP Arrhythmia report (exercise), NASA OCHMO TB-031, [NASA HRP Reduced Physical Performance report](https://humanresearchroadmap.nasa.gov/evidence/reports/Aerobic.pdf) |
| Weak signal, data gaps, device stopped | ASTRA technical rules (no NASA source) |
| Radiation level S1 to S4 | NOAA SWPC GOES proton flux and S-scale (NOAA, not NASA), [NASA OCHMO radiation brief TB-020](https://www.nasa.gov/wp-content/uploads/2023/03/radiation-protection-technical-brief-ochmo.pdf) (600 mSv career limit) |
| Radiation watch / prepare | NOAA SWPC flare, radio-burst and storm-chance feeds, [NASA: protecting astronauts from space radiation at the Moon](https://science.nasa.gov/science-research/heliophysics/how-nasa-will-protect-astronauts-from-space-radiation-at-the-moon) (shelter from stowage, food and water) |
| Three levels of care in every notification | NASA OCHMO TB-044 Medical Operations; ASTRA's own simple version |
| NASA reference panel | [NASA OSDR](https://osdr.nasa.gov) studies (read-only, labelled `external`; `docs/OSDR_RESOURCES.md`) |

Also listed in `docs/RESOURCES.md`: Canadian Space Agency pages, National Academies, SwRI, hardware datasheets, libraries (Flask, SQLite, pytest, Chart.js 4.6.1, SparkFun, Adafruit, Arduino ESP32 core) and the AI assistant.

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
| `docs/` | `RESOURCES.md` (every source), `nasa_requirements_mapping.md`, `DASHBOARD.md` (rules), `api_contract.md`, `RADIATION_MONITOR.md`, `RADIATION_REFERENCES.md`, `NASA_ARRHYTHMIA_REPORT_USE.md`, `OSDR_RESOURCES.md` |

## Team
Red – Ciolea (product, integration, pitch) · Blue – Dragoș (tech lead, backend) · Green – Roșca (hardware) · Yellow – Răpan (firmware) · Black – Dănuț (frontend and dashboard).
