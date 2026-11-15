# ASTRA team brief (13 Nov 2026 update)

English summary of the team brief of 13 Nov 2026 (the original is not included in this repository). This is the newest plan. Where it differs from the older documents, **this one wins**.

## What changed from the first plan
- **Sensors:** MAX30102 (heart rate, SpO2 estimate) and **ICM-20948** (9-axis IMU, replaces MPU6050). OLED is **not confirmed as available** (P2 only).
- **Board:** ESP32 DevKit-style with ESP-WROOM-32, USB-C and CP2102 USB-serial converter. Exact maker and variant not confirmed.
- **Firmware tooling:** Arduino IDE with C++ (Wire, SparkFun MAX3010x and ICM-20948 libraries, WiFi, HTTPClient).
- **People:** Red – Ciolea, Blue – Dragoș, Green – Roșca (hardware), Yellow – Răpan (firmware), Black – Dănuț (dashboard).
- **Product focus:** no diagnosis. ASTRA compares data with the user's own baseline and gives explainable observations: what changed, against which period, and which data contributed.

## Flow
1. Collect: MAX30102 estimates heart rate and SpO2; ICM-20948 measures motion and rotation; the astronaut can fill in a daily journal.
2. Transmit: ESP32 reads the sensors and sends data over local Wi-Fi (2.4 GHz). USB is for programming, power and debugging.
3. Store: Flask receives the data and saves it in SQLite.
4. Display: web dashboard with current values, history and the journal.
5. Interpret: simple rules compare data with a personal baseline and produce explainable observations.

## Priorities
**P0:** ESP32 recognised and programmable · MAX30102 detected with usable readings or a clear error · ICM-20948 detected with acceleration and gyro or a clear error · ESP32 builds the agreed JSON and sends it · Flask receives and confirms, SQLite is the minimum storage target · dashboard shows heart rate, SpO2 estimate, motion and data source · end-to-end demo hardware → backend → dashboard · fallback with data labelled SIMULATED.

**P1:** measurement history and latest/history endpoints · daily journal (sleep, mood, energy, stress, user-entered) · personal baseline with explained method · at least one rule-based observation naming the values and period used, no invented medical thresholds · error handling (weak signal, missing sensor, Wi-Fi down) · 2–3 verified NASA/CSA sources linked to features.

**P2:** AI rephrasing of an observation already computed by rules · CSV export · OLED · visual polish · magnetometer and advanced motion analysis.

## Connection proposal (not the final pinout)
Both sensors can share one I²C bus if their addresses differ. The board marks D21 and D22. Start with **GPIO 21 = SDA** and **GPIO 22 = SCL**, configurable in firmware and verified with an I²C scanner.

| ESP32 (proposal) | MAX30102 | ICM-20948 |
|---|---|---|
| 3V3 | VIN/VCC, only if the module accepts 3.3 V | VIN/VCC, only if the module accepts 3.3 V |
| GND | GND | GND |
| GPIO 21 (SDA) | SDA | SDA |
| GPIO 22 (SCL) | SCL | SCL |

Usual I²C addresses: MAX30102 = 0x57, ICM-20948 = 0x68 or 0x69 (depends on AD0). Confirm with a scanner; do not assume.

**Warning:** do not power the modules until the documentation and the markings on the breakouts are checked. Breakouts differ in regulators and logic-level shifting. Do not assume any VIN/VCC accepts 5 V. The ESP32 uses 3.3 V logic.

Hardware test order: identify the board and check the COM port (use a USB-C **data** cable; start with the generic "ESP32 Dev Module" profile) → check power, GND, SDA, SCL for each module → MAX30102 alone with an I²C scanner, then with its library → ICM-20948 alone → both together, check both addresses appear → only then periodic reads and Wi-Fi posting to Flask.

## Integration rules
- Blue fixes the JSON contract and endpoints with Yellow and Black (`docs/api_contract.md`).
- Field names and units do not change without telling the team.
- Black starts with demo JSON and swaps in the real API when it is ready.
- Yellow never commits Wi-Fi passwords.
- The dashboard shows the source clearly: LIVE – HARDWARE, SELF-REPORTED or SIMULATED.

## Demo scenario
1. Start Flask and the dashboard on the laptop. 2. Start the ESP32 and show it joining Wi-Fi. 3. Put a finger on the MAX30102 and show estimated heart rate and SpO2, plus signal quality if available. 4. Move the board gently and show acceleration and gyroscope changing. 5. Show the measurement reaching the backend and appearing in the dashboard. 6. If P1 is ready, fill in the journal and show an observation compared with the personal baseline. 7. Explain what is live, what is user-entered and what is simulated.

**Fallback:** if sensors, Wi-Fi or the server fail, continue with demo data clearly marked SIMULATED / DEMO DATA. Never present simulated data as real measurements.

## Limits we must state correctly
ASTRA is not a certified medical device and does not diagnose. MAX30102 gives estimates affected by motion, contact and signal quality. We do not claim the prototype is validated for use in space, we do not claim causality between indicators without evidence, and we do not claim integration with NASA systems or real space communications.

## Pre-demo checklist
- [ ] ESP32 identified and its pinout known
- [ ] Power and logic levels of both modules verified
- [ ] I²C scanner sees MAX30102 and ICM-20948 together
- [ ] MAX30102 gives estimates and signal quality is handled correctly
- [ ] ICM-20948 gives acceleration and gyroscope
- [ ] ESP32 sends JSON to Flask
- [ ] Backend receives and saves measurements
- [ ] Dashboard shows the data and the source
- [ ] Demo scenario and SIMULATED fallback exist
- [ ] Everyone can explain in 1–2 sentences what ASTRA does and what was actually built

## Rules for any AI assistant (from the brief's AI prompt)
1. Do not assume components, models, pins, installed libraries, implemented functions or unconfirmed results.
2. If critical information is missing, ask one clear question or ask for a relevant photo.
3. Give concrete ordered instructions with files, code, connections and checks.
4. Explain why each step is done and how we know it worked.
5. Before changing architecture, JSON, fields or units, explain the impact on the other modules.
6. Prioritise P0; do not recommend P2 while the main flow does not work.
7. For code, give a minimal separately testable version and say where it goes and how to run it.
8. Never present simulated data as real or MAX30102 estimates as certified measurements.
9. For NASA/CSA claims use official sources with verifiable links; separate facts from assumptions.
10. Do not overstate ASTRA: it is a prototype/concept.

Useful technical links: [Arduino-ESP32 I²C](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/i2c.html) · [ICM-20948 datasheet](https://invensense.tdk.com/wp-content/uploads/2021/10/DS-000189-ICM-20948-v1.5.pdf) · [SparkFun MAX3010x library](https://github.com/sparkfun/SparkFun_MAX3010x_Sensor_Library) · [SparkFun ICM-20948 library](https://github.com/sparkfun/SparkFun_ICM-20948_ArduinoLibrary)
