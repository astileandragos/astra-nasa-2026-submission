# firmware/esp32/

ESP32 code for the ASTRA sensor rig. Owner: Râpan Andrei. Never commit the Wi-Fi password (`secrets.h` is git-ignored). The payload follows `docs/api_contract.md`.

## What was done, and what was not (read this first)
| Level | Status on 15 Nov 2026 |
|---|---|
| Written | The sketch below reads the sensors, drives the displays and the buzzer, and sends data over USB serial and, optionally, Wi-Fi |
| Compiles | **Yes.** Compiled with `arduino-cli` against the real Arduino core for the ESP32 3.3.12 and the real libraries (board `esp32:esp32:esp32`, 24% of flash), in USB mode (`ENABLE_NETWORK 0`). The Wi-Fi mode (`ENABLE_NETWORK 1`) was only checked with stand-in headers, not with ArduinoJson installed |
| Run on a real board | **Partly.** The sketch was uploaded to an ESP32 over COM14 and run on 15 Nov 2026. The serial log showed the MAX30102 and the ICM-20948 detected and initialised, the OLED **not found**, and a measurement line every 2 seconds. The LCD was reported working by the team |
| End to end over USB | **Observed once on 15 Nov 2026:** with `tools/serial_bridge.py` running, measurements reached the backend (HTTP 201), the dashboard switched to `TODAY: LIVE SENSOR`, the still board read about 1 g, and a heart-rate notification and its LCD message appeared (confirmed by the team). This was a demonstration run, **not a formal test**: no run length, no repeat count and no failure log were recorded |
| Heart-rate accuracy | **Not measured.** No comparison with a reference device. Do not quote an accuracy |
| SpO2 | **Not calculated.** The sketch sends `spo2_percent: null` |
| Wi-Fi mode | **Not tested on the real board** |
| Microgravity or environmental testing | **None** |

## The sketch (`esp_cod_copy_20261114125516/esp_cod_copy_20261114125516.ino`)
- **Sensors:** a MAX30102 gives the heart rate (beats averaged over the last readings; sent only when a finger is on the sensor and a rate has been computed, otherwise `null`). An ICM-20948 gives acceleration (sent in g) and rotation (dps), or `null` until the first reading and when the sensor is missing.
- **Signal quality sent:** `good` (finger present and a heart rate computed), `poor` (finger present, no rate yet) or `no_finger`. This is all the firmware knows; nothing else is claimed.
- **Displays and buzzer:** the 16x2 LCD shows sensor values, a local alert, or the dashboard notification received from the laptop; the OLED (SSD1306) is supported by the code but was not detected on the board used; the buzzer sounds on a local alert (below 50 or above 160 bpm, or above 2.5 g). These local thresholds belong to this demo device only: they are not NASA values and not the dashboard's rules. The buzzer is active-low (`BUZZER_ON_LEVEL`); change it to `HIGH` for an active-high module.
- **Libraries:** SparkFun MAX3010x, SparkFun ICM-20948, Adafruit SSD1306, Adafruit GFX, LiquidCrystal and, for Wi-Fi mode only, ArduinoJson 7. Licences: `THIRD_PARTY_NOTICES.md`.
- **Pins:** see `hardware/README.md` (taken from the code, not a verified wiring diagram).

## Live demo over USB (board plugged into the laptop, no Wi-Fi)
This is the default mode of the sketch (`ENABLE_NETWORK 0`, `USB_STREAM 1`). Every 2 seconds the board prints one line
`ASTRA_JSON {...}` on the serial port (same fields as `docs/api_contract.md`, `source: live_hardware`, unknown values `null`).
`tools/serial_bridge.py` reads those lines and POSTs them to the dashboard unchanged; it neither invents nor changes a value.

1. Upload the sketch (Arduino IDE or `arduino-cli`; hold BOOT during the upload if the board does not connect). Close the Serial Monitor: only one program can use the port.
2. Start the dashboard server. Stop `simulator.py` (it would add simulated readings). The simulated baseline week stays.
3. Clear today: Sensors page, Live demo, reset button (or `POST /api/demo/reset-today`).
4. Start the bridge: `python tools/serial_bridge.py` (it finds the board by itself; or `--port COM14`; `--list` shows the ports). It needs `pip install pyserial requests`. Each measurement prints one line: time, heart rate, signal, motion, HTTP code (201 = accepted).
5. The Overview shows `TODAY: LIVE SENSOR` after the first reading. Leave the board flat and still: Activity says STILL. Put a finger on the heart sensor. After about 20 good readings (about 40 seconds) the heart-rate rule can raise a notification.

### Notifications on the LCD
While the bridge runs it asks the dashboard for the current notifications every 3 seconds and sends one back to the board as `ASTRA_MSG <line 1>|<line 2>`. The 16x2 LCD shows it: while any notification is red only red ones are shown; otherwise each is shown for 4 seconds in turn. Examples: `HEART RATE HIGH` / `Sit down, rest` (orange), `HEART RATE HIGH` / `Rest, tell crew` (red), `NO MOVEMENT` / `Stand up, move`, `WEAK SIGNAL` / `Refit the sensor`, `RADIATION WATCH` / `Stay informed`.
- The board's own pulse and impact alerts come first on the LCD, then the dashboard message, then the normal sensor screens. If the bridge stops, the message disappears after 8 seconds.
- The "Data has gaps today" notice is not shown on the LCD. `--no-lcd` turns the feature off. The wording is in `lcd_message()` in `tools/serial_bridge.py`.

## Wi-Fi mode (optional, not tested on the board)
Set `ENABLE_NETWORK 1`. Copy `secrets_example/secrets.example.h` to `secrets.h` in the sketch folder and fill in the Wi-Fi name, password, laptop IP and device id (`secrets.h` is git-ignored; never commit it). The board then POSTs one measurement every 2 seconds to `SERVER_URL`; a failed POST waits 6 seconds, and a lost connection is retried every 10 seconds without restarting. The OLED line `Net:OK Srv:201` (when an OLED is present) means the server accepted the last measurement.

Bench mode without any link: `ENABLE_NETWORK 0` and `USB_STREAM 0`.
