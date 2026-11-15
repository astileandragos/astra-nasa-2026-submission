# ASTRA architecture and weekend plan

Summary of the team's original planning documents (not included in this repository). The newest plan is `docs/PROJECT_BRIEF.md` (13 Nov 2026); where they differ, it wins.

## Flow
Sensors (MAX30102, ICM-20948) → ESP32 (reads, timestamps, labels source and quality) → HTTP POST over local Wi-Fi → Flask API (validate, normalise) → SQLite (store) → Dashboard (latest values, history chart, data-source label).

Success = a real sensor reading reaches the dashboard with no manual editing. Fallback = clearly labelled `simulated` data.

## Stack
ESP32 (DevKit-style, ESP-WROOM-32) programmed in Arduino IDE (C++) · Python + Flask · SQLite · HTML/CSS/JS + Chart.js · Wi-Fi + HTTP (no MQTT unless justified).

## Priorities
- **P0 MUST**: end-to-end flow, dashboard with HR/SpO2/timestamp/source label, one chart, validated API and storage.
- **P1 SHOULD**: history endpoint, wellbeing form, one explainable rule-based insight, NASA/CSA context, firmware retry and status.
- **P2 COULD**: AI rephrasing of rule output, CSV export, OLED (not confirmed available), polish, magnetometer.

## Team
| Colour | Person | Focus |
|---|---|---|
| Red | Ciolea | Product, integration, NASA relevance, pitch |
| Blue | Dragoș | Tech lead, Flask/API/SQLite, health engine |
| Green | Roșca | Hardware and electronics |
| Yellow | Răpan | Firmware and sensor data |
| Black | Dănuț | Dashboard and visualization |

## Schedule
- **Fri 13 Nov**: remote meeting on Discord (roles, contract, hardware, demo laptop).
- **Sat 14 Nov**: on-site. First full slice. End of day: MVP works, architecture frozen.
- **Sun 15 Nov**: close P0, feature freeze before the afternoon, rehearse, submit before the deadline.

Checkpoints: start of day 15 min, midday 10 min, end of day 15 min. Stations: A hardware (Green + Yellow), B software (Blue + Black), Red moves between them.

## Working rules
- One owner per component. Helpers review; they do not edit the same files at the same time.
- Agree interfaces first. Any change to a JSON field, endpoint, shared filename or pinout is announced before it is made.
- One branch per task (`feat/...`), small commits, `main` always runnable for the demo. Red coordinates merges.
- Blocked for 15–20 minutes? Post: `BLOCKED – [name] / Expected / Actual / Tried / Need`.
- Tools: Google Sheets = status, GitHub = code, Drive = documents, Discord = communication.
- Done means demonstrable, run by the owner, and the integration still works. "AI wrote it" is not done.

## Demo plan and fallback
One laptop runs Flask and the dashboard. The ESP32 posts to that laptop's local IP (not localhost) on the same Wi-Fi or hotspot. Keep a clearly labelled `simulated` payload ready. Run everything locally if the internet fails. If a sensor fails, show the hardware data that was validated plus the separate software flow, and state the limitation.

## Limits to keep in the pitch
- MAX30102 gives experimental HR/SpO2 estimates (motion, contact and signal quality matter).
- ICM-20948 measures acceleration, angular rate (and magnetic field), not microgravity or clinical balance.
- Alerts come from documented rules, not an AI model.
- No invented accuracy or clinical validation.
