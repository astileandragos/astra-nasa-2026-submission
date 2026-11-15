# NASA Challenge Requirements Mapping — ASTRA

## 1. Official challenge

**Challenge:** Create Health Monitoring Software for Astronauts on Space Missions

**Official objective:** Build health-monitoring software that gathers health indicators and enables astronauts to evaluate and act on the status of their health.

**Official challenge:**  
https://www.spaceappschallenge.org/2026/challenges/health-monitoring-software/

## 2. Problem ASTRA addresses

Long-duration space missions expose astronauts to conditions such as:

- Space radiation
- Isolation and confinement
- Altered gravity
- Hostile and closed environments

These conditions can contribute to physiological and behavioral health changes. Astronauts may need tools to recognize changes in their own health during missions.

Scientific background: see [NASA and CSA Scientific References](nasa_references.md).

## 3. Requirement-to-solution mapping

| Challenge requirement | ASTRA response | Implementation status |
|---|---|---|
| Gather health indicators | MAX30102 for experimental heart-rate and SpO₂ estimates; ICM-20948 for acceleration and gyroscope data | Hardware integration and readings must be verified |
| Help astronauts evaluate their health | Dashboard displaying measurements, timestamps and data sources | End-to-end data flow must be verified |
| Provide context beyond sensor readings | Daily self-reported journal for sleep, mood, energy and stress | Planned; implementation must be verified |
| Help identify changes over time | Measurement history and comparison against an individual's baseline | Planned; implementation must be verified |
| Support informed action | Simple, explainable observations based on available measurements and personal trends | Planned; implementation must be verified |

## 4. ASTRA system overview

ASTRA is designed as a local hardware-software prototype.

**Proposed data flow:**

Sensors → ESP32 → Wi-Fi → Flask backend → SQLite database → Dashboard

The planned platform includes:

- Experimental sensor measurements
- Self-reported daily information
- Historical measurements and personal trends
- Explainable, rule-based observations

Only features verified as functional should be presented as implemented.

## 5. What makes ASTRA relevant to space missions?

ASTRA explores how multiple indicators can be brought together in one monitoring interface.

Instead of showing isolated sensor values, the proposed platform combines physiological estimates, movement information and subjective daily reports. Historical data could provide context for changes over time.

This is relevant to long-duration missions, where astronauts may need to monitor their own condition.

## 6. Scope and limitations

ASTRA is an educational prototype, not a certified medical device.

- MAX30102 values are experimental estimates, not clinically validated measurements.
- The platform does not diagnose medical conditions.
- The prototype has not been validated in space or under microgravity.
- Rule-based observations must not be presented as medical advice.
- Simulated data must always be clearly labelled.
- Missing or invalid measurements must not be represented as zero.
- ASTRA does not measure radiation.
- NASA and CSA references provide scientific background; their measurements are not currently integrated into ASTRA.
- ASTRA does not claim NASA integration or endorsement.

## 7. Final validation checklist

Before presenting ASTRA, verify that:

- [ ] ESP32 communicates with the backend.
- [ ] MAX30102 provides readings or a clearly reported sensor error.
- [ ] ICM-20948 provides motion readings or a clearly reported sensor error.
- [ ] The dashboard displays incoming measurements.
- [ ] Every measurement has a timestamp and identifiable source.
- [ ] The journal works, if included in the final demo.
- [ ] Historical trends work, if included in the final demo.
- [ ] Any observations are explainable and do not make medical claims.
- [ ] Simulated data is visibly distinguished from live hardware data.
- [ ] The final presentation distinguishes implemented features from planned features.

