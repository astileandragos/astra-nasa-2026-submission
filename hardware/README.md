# hardware/

Wiring, pinouts, photos and inventory. Owner: Roșca Cristian. Board: ESP32 DevKit-style (ESP-WROOM-32, USB-C, CP2102). Sensors: MAX30102 (heart rate) and ICM-20948 (motion). The sketch and its settings are in `firmware/esp32/`. Never guess a module's voltage tolerance or pinout; check the datasheet.

## Pins and addresses used by the current sketch (read from the code on 15 Nov 2026)
From `firmware/esp32/esp_cod_copy_20261114125516/esp_cod_copy_20261114125516.ino`. These are what the code uses, **not** a verified wiring diagram. **[Roșca Cristian to confirm they match the physical wiring.]**
| Item | Value in the sketch |
|---|---|
| I2C (both sensors, OLED) | SDA = GPIO 21, SCL = GPIO 22, 400 kHz |
| Buzzer | GPIO 32, active-low (`BUZZER_ON_LEVEL LOW`) |
| 16x2 LCD (LiquidCrystal, 4-bit) | RS 23, EN 25, D4 26, D5 27, D6 18, D7 19 |
| OLED SSD1306 128x64 | I2C address 0x3C or 0x3D, found by scan |

## Status: the older notes below are out of date and need confirmation
The assembly note written earlier (preserved here) said the MAX30102 had a detached SMD capacitor and must not be powered. Newer information:

| Earlier note | What the newer files or observations show | Needs |
|---|---|---|
| MAX30102: SMD capacitor detached during soldering, repair in progress, do not power | On 15 Nov 2026 the sketch's serial log on the real board showed an I2C device at 0x57 and "MAX30102 functional", and heart-rate readings reached the dashboard. No document records the repair or an electrical check | **Roșca Cristian / Ciolea Daniel to confirm** whether the capacitor was repaired and the part was checked. Do not treat the sensor as validated |
| ICM-20948: headers soldered | The same log showed a device at 0x69 and "ICM-20948 functional"; acceleration read about 1 g with the board still | Roșca Cristian to confirm the wiring and address |
| Electrical compatibility not verified | **Still unresolved in the documents.** No record of the voltage and compatibility check | **Roșca Cristian / Ciolea Daniel to confirm and record** (see the checklist) |
| I2C detection not tested | The serial log on 15 Nov showed an I2C scan finding 0x57 and 0x69 (the OLED was **not** found on the board used) | Record it properly in the checklist |
| ESP32 connection pending with Râpan Andrei | The sketch runs on the ESP32 and sends over USB serial (and, untested, Wi-Fi) | Confirm |

**Safety warning (still open, kept from the original note):** do not power the sensors until voltage compatibility and wiring are confirmed. The sensors were in fact powered during the 15 Nov run, so this check should be completed and recorded now.

## Hardware verification checklist (the team fills this in with real results)
Tick a box only with an actual test result and write the date, the person and the evidence. An unticked box means "not verified".

- [ ] MAX30102 and ICM-20948 supply voltage and module compatibility with the ESP32 3.3 V I2C bus checked against the datasheets (record the values)
- [ ] The repaired MAX30102 inspected: capacitor in place, no short, module powers up
- [ ] I2C scan lists the MAX30102 (expected 0x57) and the ICM-20948 (0x68 or 0x69). Attach the serial log
- [ ] Wiring matches the pin table above (photo)
- [ ] MAX30102: finger placed, a stable heart rate appears. Compare with a reference (a finger pulse count or a certified device) and record the difference. **Accuracy not yet measured**
- [ ] MAX30102 SpO2: **not computed by the current firmware**, nothing to verify
- [ ] ICM-20948: acceleration is about 1 g on every axis combination at rest, and changes when the board is moved
- [ ] 16x2 LCD shows sensor screens and a dashboard notification
- [ ] OLED: **not detected on the board used on 15 Nov**; either fit and test it, or mark it as not used
- [ ] Buzzer polarity (active-low) and the alert thresholds (below 50 or above 160 bpm, above 2.5 g) checked
- [ ] USB serial run of at least 10 minutes without a reset (record the length)
- [ ] Wi-Fi mode (`ENABLE_NETWORK 1`) tested end to end **(not done)**
- [ ] No voltage, temperature or noise problems seen with the sensors in use (record what was seen)

## Original assembly note (kept as written; outdated, see above)
- MAX30102: SMD capacitor detached during soldering. Repair in progress. Sensor must not be powered until repaired and electrically checked.
- ICM-20948: headers already soldered.
- Electrical compatibility: not yet fully verified.
- I2C detection: not yet tested.
- ESP32 connection: pending coordination with Râpan Andrei.

Next step (original): verify MAX30102 electrical specifications, then perform the first I2C test with Râpan Andrei.
