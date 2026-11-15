# hardware/

Wiring, pinouts, photos and inventory. Owner: Green (Roșca). Board: ESP32 DevKit-style (ESP-WROOM-32, USB-C, CP2102). Sensors: MAX30102, ICM-20948. Wiring proposal and warnings: `docs/PROJECT_BRIEF.md`. Never guess a module's voltage tolerance or pinout; check the datasheet.
## Hardware Assembly Status

- MAX30102: SMD capacitor detached during soldering.
  Repair in progress. Sensor must not be powered
  until repaired and electrically checked.
- ICM-20948: headers already soldered.
- Electrical compatibility: not yet fully verified.
- I2C detection: not yet tested.
- ESP32 connection: pending coordination with YELLOW.

Next step:
Verify MAX30102 electrical specifications,
then perform the first I2C test with YELLOW.

Safety:
Do not power the sensors until voltage
compatibility and wiring are confirmed.