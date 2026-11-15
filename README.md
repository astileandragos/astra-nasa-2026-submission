# ASTRA: Astronaut Smart Health Monitoring Platform

NASA Space Apps Challenge 2026 · Cluj-Napoca · Challenge: **Create Health Monitoring Software for Astronauts on Space Missions**

**Demo / presentation (7 slides):** [PDF](https://github.com/astileandragos/astra-nasa-2026-submission/blob/main/presentation/ASTRA_pitch.pdf) · [PowerPoint with the two demo videos](https://github.com/astileandragos/astra-nasa-2026-submission/blob/main/presentation/ASTRA_pitch.pptx) (download the file to play the videos). Both are in `presentation/` in this repository.

ASTRA is an **experimental educational prototype**. It is **not a medical device**, it is **not certified or clinically validated**, it gives no diagnosis or medical advice, and it is **not a NASA-approved system** and is not connected to NASA systems.

## The problem
On a long mission, for example to Mars, a message to Earth can take many minutes each way (up to about 22 minutes one way for a crewed Mars mission, according to a [NASA analysis](https://ntrs.nasa.gov/citations/20220013418)), so a crew cannot always wait for ground support. Astronauts need to understand changes in their own health, and to know when to look after themselves, when to tell a crew member with medical training, and when to call for emergency help. NASA lists distance from Earth, isolation, radiation, altered gravity and closed environments among the hazards of human spaceflight (see `docs/RESOURCES.md`).

## What ASTRA is, and why it is relevant to long-duration missions
ASTRA brings a few health indicators and the radiation situation together in one local dashboard that runs on the crew's own computer and does not need a connection to Earth for its health rules (the live space-weather feed does need a data link). It compares each person with their own usual values, explains changes in plain words, and gives practical first steps in three levels of care: self-care, tell the crew medical officer, and emergency (call the crew for help and mission control at the same time, without waiting for a reply).

## Implemented capabilities
| Capability | Status on 15 Nov 2026 |
|---|---|
| Dashboard with Overview, Timeline, Radiation, Activity, Journal and Sensors pages (`frontend/`) | Implemented and tested with simulated data; used with the live sensor in the demo |
| Rule-based notifications (`backend/notices.py`): heart rate against the person's own baseline, blood oxygen against baseline, rest start and length, no movement, weak signal, gaps in wear time, lost connection, radiation | Implemented. **The rules and thresholds are the team's own experimental choices.** NASA publishes no validated thresholds for these; they are not NASA-approved |
| Advice in plain language with three levels of care, each step tagged `NASA GUIDANCE` or `ASTRA SUGGESTION` | Implemented. The advice is general information written by the team; no clinical review of the wording is recorded in this repository |
| Radiation page: NOAA GOES proton flux, NOAA S-scale, ASTRA alert levels 0 to 3 and a five-stage outlook (All clear, Watch, Prepare, Build the shelter, Shelter) | Implemented. See "Radiation" below for what it can and cannot do |
| ESP32 sketch reading a MAX30102 (heart rate) and an ICM-20948 (motion), with a 16x2 LCD, a buzzer and an OLED driver (`firmware/esp32/`) | Compiles with the real ESP32 core and libraries. Run on a real board on 15 Nov 2026 (see `firmware/esp32/README.md` for exactly what was and was not tested) |
| USB link from the board to the dashboard (`tools/serial_bridge.py`), which also sends the current notification to the board's LCD | Implemented; 9 unit tests; observed working on the real board on 15 Nov 2026 |
| Wi-Fi sending from the board | Implemented in the sketch (`ENABLE_NETWORK 1`); **not tested on the real board** |
| Journal (daily self-reported check-in) | Implemented |

## Hardware and software architecture
**Sensors (MAX30102, ICM-20948) → ESP32 → USB serial (bridge) or Wi-Fi → Flask API → SQLite → dashboard.** Radiation: NOAA SWPC JSON feeds → Flask → Radiation page. Details: `docs/api_contract.md`, `docs/DASHBOARD.md`, `firmware/esp32/README.md`, `hardware/README.md`.

## Install and run (about 2 minutes, no hardware needed)
```bash
cd backend
python -m venv .venv
.venv/Scripts/activate            # Windows. On Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python seed_demo.py --baseline-week --days 7   # a labelled, SIMULATED 7-day baseline
python simulator.py &                          # simulated readings for today (device SIM-01)
python app.py                                  # then open http://127.0.0.1:5000
```
Tests: `cd backend && pytest` (254 tests passed on 15 Nov 2026), and `pytest tools/test_serial_bridge.py` (9 tests). With a board plugged in over USB, follow `firmware/esp32/README.md` ("Live demo over USB").

## NASA data and resources used
NASA publishes no heart-rate, blood-oxygen, inactivity or radiation-alert thresholds for this prototype, so none are invented: the triggers are ASTRA's own rules, and the NASA documents shape the advice, the wording and the context. **Every source, with the exact feature it informs and what it does NOT validate, is in [`docs/RESOURCES.md`](docs/RESOURCES.md).** Summary:

| Notification | NASA and other resources |
|---|---|
| Heart rate higher or lower than usual | [NASA HRP Arrhythmia evidence report](https://humanresearchroadmap.nasa.gov/evidence/other/Arrhythmia.pdf) ([exact use](docs/NASA_ARRHYTHMIA_REPORT_USE.md)), [NASA OCHMO-TB-031 Exercise](https://www.nasa.gov/wp-content/uploads/2023/12/ochmo-tb-031-exercise-overview.pdf), [NASA OCHMO-TB-044 Medical Operations](https://www.nasa.gov/wp-content/uploads/2025/08/ochmo-tb-044-medical-operations.pdf) |
| Blood oxygen different from usual | No NASA numbers exist; safe steps only |
| Rest started late, rest too short or long | [NASA: Seven ways astronauts improve sleep](https://www.nasa.gov/missions/station/seven-ways-astronauts-improve-sleep-may-help-you-snooze-better-on-earth/), NASA HRP hazards and risks |
| No movement | NASA HRP Arrhythmia report (exercise), NASA OCHMO-TB-031, [NASA HRP Reduced Physical Performance report](https://humanresearchroadmap.nasa.gov/evidence/reports/Aerobic.pdf) |
| Weak signal, data gaps, device stopped | ASTRA technical rules (no NASA source) |
| Radiation level S1 and above | NOAA SWPC GOES proton flux and S-scale (NOAA, not NASA), [NASA OCHMO-TB-020 Rev E](https://www.nasa.gov/wp-content/uploads/2023/03/radiation-protection-technical-brief-ochmo.pdf) (600 mSv career limit) |
| Radiation watch / prepare | NOAA SWPC flare, radio-burst and storm-chance feeds, [NASA: protecting astronauts from space radiation at the Moon](https://science.nasa.gov/science-research/heliophysics/how-nasa-will-protect-astronauts-from-space-radiation-at-the-moon) (shelter from stowage, food and water) |
| Three levels of care in every notification | NASA OCHMO-TB-044 Medical Operations (context); the three levels are ASTRA's own simplification |
| NASA reference panel | [NASA OSDR](https://osdr.nasa.gov) study entries (read-only, labelled `external`; `docs/OSDR_RESOURCES.md`). OSDR holds no wearable data, so ASTRA is not validated against it |

## Data-source labelling
Every stored record keeps its own label and is never relabelled: `live_hardware` (the sensor board), `simulated`, `self_reported` (the journal) or `external` (NOAA and NASA OSDR). A missing value is `null`, never `0`.

The demo view of the dashboard **combines** a clearly labelled **simulated baseline** of the earlier days with **today's live sensor data** (or today's simulator data when no live reading has arrived today). The chips `BASELINE: SIMULATED WEEK` and `TODAY: LIVE SENSOR` or `TODAY: SIMULATOR` say which is which. **The baseline is demonstration data. It does not represent real historical measurements of any astronaut or any person.** A warning in the demo therefore means "different from the simulated baseline".

## Radiation: what ASTRA does and does not do
- NASA's career effective-dose limit of 600 mSv (NASA-STD-3001 [V1 4030], quoted in OCHMO-TB-020 Rev E) is the limit in an **illustrative** exposure budget. The dose received so far, the background rate (0.5 mSv/day) and the event doses are settings or demo values, not measurements.
- The live data is NOAA's GOES proton flux at 10 MeV or more, classified on NOAA's S1 to S5 scale. **Proton flux cannot be converted directly into an astronaut's radiation dose**, and ASTRA does not do so.
- ASTRA's alert levels 0 to 3 and its five-stage outlook are its own experimental rules, not NASA flight rules.
- **ASTRA has no onboard ionizing-radiation detector** and **cannot reliably predict solar storms**. It shows NOAA's early signs and says so.
- The Radiation page can run **simulated scenarios** for testing; they are labelled `simulated`.
Details and the consistent definitions: `docs/RADIATION_REFERENCES.md` (section 0) and `docs/RADIATION_MONITOR.md`.

## Technical and medical limitations
- Experimental prototype, not a medical device, not clinically validated, no diagnosis, not NASA-approved. The advice is general and is not medical advice.
- **The sensors have not been validated in microgravity. Further environmental testing, calibration, and reliability studies would be required before any spaceflight use.** Heart rate comes from a low-cost optical sensor that has not been compared with a reference device; its accuracy is unknown.
- **Live SpO2 is not calculated by the current firmware.** It is sent as empty (`null`), so blood-oxygen notifications cannot fire from live data.
- Radiation data comes from NOAA over the internet, not from a sensor on the ESP32.
- The personal baseline used in the demo is simulated.
- Alerts are rule-based and experimental. Thresholds are the team's choices.
- Wi-Fi sending has not been tested on the real board.

## Use of AI (Super Intelligence) tools
Claude Code (Anthropic), an AI coding assistant, helped the team write and test code (backend, dashboard, firmware integration, tests), write documentation and draft the presentation. The idea, the approach, the rules and the thresholds are the team's, and the team reviewed and tested the results. AI-assisted commits in the original working repository carry a `Co-Authored-By` line. No AI-generated image is recorded in this repository; the sources of the images in the presentation are listed in `docs/RESOURCES.md` (section 5).

## Repo map
| Folder | What |
|---|---|
| `backend/` | Flask API, SQLite, rule-based health engine, simulator, tests |
| `frontend/` | Dashboard (HTML, CSS, JavaScript, Chart.js) |
| `firmware/esp32/` | ESP32 sketch and set-up guide (the Wi-Fi password stays in a git-ignored `secrets.h`) |
| `tools/` | `serial_bridge.py`: USB link between the board and the dashboard, with tests |
| `hardware/` | Hardware notes and verification checklist |
| `data/` | Sample payloads (always `simulated`) and the curated reference list |
| `docs/` | `RESOURCES.md` (every source), `nasa_requirements_mapping.md`, `DASHBOARD.md` (rules), `api_contract.md`, `RADIATION_MONITOR.md`, `RADIATION_REFERENCES.md`, `NASA_ARRHYTHMIA_REPORT_USE.md`, `OSDR_RESOURCES.md` |
| `THIRD_PARTY_NOTICES.md` | Third-party software and its licences |

## Licence
The team's original code and documentation are released under the [MIT License](LICENSE). Third-party components keep their own licences (`THIRD_PARTY_NOTICES.md`). NASA and NOAA documents and data and the presentation images are not covered by this licence.

## Team
**Team name: Mon**

| Name | Role |
|---|---|
| Ciolea Daniel | Product, integration, pitch |
| Aștilean Dragoș | Tech lead, backend, health rules |
| Ioja Dănuț | Frontend and dashboard |
| Râpan Andrei | Firmware |
| Roșca Cristian | Hardware and electronics |
