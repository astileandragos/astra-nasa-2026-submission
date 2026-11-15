# NASA challenge requirements mapping: ASTRA

**Challenge:** Create Health Monitoring Software for Astronauts on Space Missions
https://www.spaceappschallenge.org/2026/challenges/health-monitoring-software/

**Objective:** build health-monitoring software that gathers health indicators and enables astronauts to evaluate and act on the status of their health.

## Problem
Long missions expose astronauts to radiation, isolation and confinement, distance from Earth, altered gravity and hostile, closed environments (NASA's five human spaceflight hazards). When communication with Earth is delayed, a crew needs to understand its own health and know when to ask for help.

## Requirement to solution (status on 15 Nov 2026)

| Challenge requirement | ASTRA response | Status |
|---|---|---|
| Gather health indicators | Heart rate (MAX30102) and acceleration and rotation (ICM-20948) from an ESP32, sent every 2 seconds over Wi-Fi or USB; daily self-reported check-in; space-weather data from NOAA | Implemented. Heart rate and motion tested on the real board; blood oxygen is not computed by the current firmware (sent as `null`) |
| Help astronauts evaluate their health | Dashboard with Overview, Timeline, Radiation, Activity, Journal and Sensors pages; every value labelled `live_hardware`, `simulated`, `self_reported` or `external` | Implemented |
| Help identify changes over time | A baseline from the previous days; today compared with the person's own usual values | Implemented (the demo baseline is a labelled simulated week) |
| Support informed action | Notifications from documented rules with plain-language advice in three levels of care (self-care, tell the crew medical officer, emergency); a five-stage radiation outlook; notifications also shown on the board's LCD | Implemented. Advice steps are tagged NASA guidance or ASTRA suggestion; see `RESOURCES.md` |
| Use NASA data and resources | NASA HRP evidence reports, OCHMO technical briefs, NASA radiation and shelter guidance, NASA OSDR reference studies; NOAA live data (not NASA) | See `RESOURCES.md` |

## Data flow
Sensors → ESP32 → (Wi-Fi or USB) → Flask API → SQLite → dashboard (and the LCD on the board).

## Scope and limitations
- ASTRA is an educational prototype, not a medical device, and gives no diagnosis or medical advice.
- Heart rate and motion come from low-cost sensors and are experimental estimates, not clinically validated; they would not survive the noise of microgravity. The prototype has not been validated in space.
- NASA publishes no alert thresholds for heart rate, blood oxygen or movement, so ASTRA's thresholds are the team's own choices, not NASA flight rules.
- ASTRA does not measure radiation and does not predict solar storms. It shows NOAA's space-weather data and early signs, and says so.
- Simulated data is always labelled. A missing value is `null`, never `0`.
- ASTRA does not claim NASA integration or endorsement.
