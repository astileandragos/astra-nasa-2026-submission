# NASA / CSA Scientific References

**Project:** ASTRA – Astronaut Smart Health Monitoring Platform  
**Purpose:** Scientific background and motivation  
**Status:** NASA sources are used as reference text, not as data feeds. The NASA Human Research Roadmap Arrhythmia report shapes the heart-rate advice (see `NASA_ARRHYTHMIA_REPORT_USE.md`) and NASA's published shelter guidance shapes the radiation steps (see `RADIATION_REFERENCES.md`). No NASA dataset is downloaded by ASTRA; the live space-weather feed is NOAA's.

## 1. Official references

### NASA – Human Spaceflight Hazards
https://www.nasa.gov/hrp/hazards/

Provides background on the main hazards of human spaceflight, including radiation, isolation and confinement, distance from Earth, altered gravity, and hostile or closed environments.

**ASTRA relevance:** Establishes the broader context for monitoring astronaut health during space missions.

### NASA – Risks of Human Spaceflight
https://www.nasa.gov/hrp/risks/

Describes health and performance risks associated with human spaceflight, including cardiovascular adaptations, sleep-related issues, and behavioral risks.

**ASTRA relevance:** Supports the motivation for exploring physiological indicators and daily self-reported well-being.

### NASA – Ongoing HRP Research in Space
https://www.nasa.gov/hrp/ongoing-hrp-research/

Describes ongoing NASA Human Research Program activities investigating human health and performance in space.

**ASTRA relevance:** Provides research context for monitoring health-related indicators and astronaut well-being.

### Canadian Space Agency – Monitoring Radiation for Astronaut Health
https://www.asc-csa.gc.ca/eng/news/articles/2026/2026-02-26-monitoring-radiation-astronaut-health.asp

Describes radiation monitoring research and instrumentation for astronaut health.

**ASTRA relevance:** Illustrates the importance of monitoring multiple environmental and physiological risks. ASTRA does not measure radiation.

### Canadian Space Agency – Why Do We Conduct Science Experiments in Space?
https://www.asc-csa.gc.ca/eng/iss/science/why-do-we-conduct-science-experiments-in-space.asp

Explains why scientific experiments are conducted aboard the International Space Station and how they contribute to future exploration and life on Earth.

**ASTRA relevance:** Provides context for developing and testing technologies that could support astronaut health monitoring.

## 2. Connection to ASTRA

ASTRA explores a small-scale health-monitoring prototype using:

- MAX30102: experimental heart-rate and SpO₂ estimates.
- ICM-20948: acceleration and gyroscope measurements.
- ESP32: sensor data acquisition and transmission.
- Flask and SQLite: data reception and storage.
- Dashboard: visualization of measurements and trends.
- Daily journal: self-reported sleep, mood, energy, and stress, if implemented.

The NASA and CSA references motivate the project. They are not data feeds for the current prototype.

## 3. Data-source clarification

The current ASTRA prototype does not import NASA or CSA measurements or external datasets.

The following sources must remain clearly distinguished:

- `live_hardware`: readings received from the physical prototype.
- `self_reported`: information entered manually by the user.
- `simulated`: generated demonstration data.

`external` may be reserved for future integration, but must not be presented as an active data source unless a real external dataset is acquired and integrated.

## 4. Scientific and technical limitations

- ASTRA is an educational prototype, not a medical device.
- MAX30102 values are experimental estimates, not clinically validated measurements.
- ASTRA does not diagnose medical conditions or detect medical emergencies.
- ASTRA does not measure radiation.
- The project does not claim NASA integration, NASA endorsement, or validation for use in space.
- Any feature described as planned must not be presented as implemented.

