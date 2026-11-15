# firmware/esp32/

ESP32 code (MAX30102, ICM-20948, Wi-Fi POST). Owner: Yellow (Răpan). Never commit the Wi-Fi password (`secrets.h` is git-ignored). Must send exactly the payload in `docs/api_contract.md`.

## The sketch (`esp_cod_copy_20261114125516/esp_cod_copy_20261114125516.ino`)
One sketch does everything: it reads the MAX30102 (heart rate) and the ICM-20948 (motion), shows them on the OLED, the 16x2 LCD and the serial monitor, sounds the buzzer on a local alert, and POSTS one measurement every 2 seconds to `SERVER_URL` (payload of `docs/api_contract.md`).

Setup: copy `sectrets/secrets.example.h` to `secrets.h` in the sketch folder and fill in the Wi-Fi name, password, laptop IP and device id (`secrets.h` is git-ignored). Libraries: SparkFun MAX3010x, SparkFun ICM-20948, Adafruit SSD1306, Adafruit GFX, LiquidCrystal, ArduinoJson 7.

What is sent: `heart_rate_bpm` only when a finger is on the sensor and a heart rate was computed (otherwise `null`); acceleration in g and rotation in dps (null if the ICM-20948 is missing); `spo2_percent` is always `null` because this sketch does not compute SpO2; `signal_quality` is `good` (finger and heart rate), `poor` (finger, no heart rate yet) or `no_finger`; `source` is `live_hardware`. A failed POST waits 6 seconds before the next try, and a lost Wi-Fi connection is retried every 10 seconds without restarting the board, so the sensors and displays keep working.

Bench test without a network: set `ENABLE_NETWORK` to `0` at the top of the sketch (nothing is sent; the OLED shows `Net: off (bench)`).

The OLED third line shows the network state: `Net:OK Srv:201` means the server accepted the last measurement.

The buzzer thresholds (below 50 or above 160 bpm, or above 2.5 g) belong to this demo device only. They are not NASA values and not the dashboard's rules. The buzzer is active-low (`BUZZER_ON_LEVEL`); change it to `HIGH` for an active-high module.

Checked so far: the sketch compiles against stand-in headers (syntax and types only). It has NOT been compiled with the real libraries or run on the board.


## Live demo over USB (board plugged into the laptop, no Wi-Fi)

The sketch is set to this mode by default (`ENABLE_NETWORK 0`, `USB_STREAM 1`). Every 2 seconds the board prints one line
`ASTRA_JSON {...}` on the serial port (same fields as `docs/api_contract.md`, `source: live_hardware`, unknown values `null`).
`tools/serial_bridge.py` reads those lines and POSTs them to the dashboard. Nothing is changed or invented on the way.

1. Upload the sketch. Close the Arduino Serial Monitor (only one program can use the port).
2. Start the dashboard server. Stop `simulator.py` (it would add simulated readings). The simulated baseline week stays.
3. Clear today: Sensors page, Live demo, reset button (or `POST /api/demo/reset-today`).
4. Start the bridge: `python tools/serial_bridge.py` (finds the board by itself; or `--port COM14`; `--list` shows the ports).
   Needs `pip install pyserial requests`. Each measurement prints one line: time, HR, signal, motion, HTTP code (201 = accepted).
5. Overview shows `TODAY: LIVE SENSOR` after the first reading. Leave the board flat and still: Activity says STILL.
   Put a finger on the heart sensor. After about 20 good readings (about 40 seconds) the heart rate rule can raise a notification.

For Wi-Fi instead, set `ENABLE_NETWORK 1` and follow the setup section above. This path was checked with stand-in headers
and the dashboard rules were rehearsed with the same payload; the serial path itself still needs a test on the real board.

### Notifications on the LCD

While the bridge runs it asks the dashboard for the current notifications every 3 seconds and sends the most important one
back to the board as `ASTRA_MSG <line 1>|<line 2>`. The 16x2 LCD shows it (while any notification is red, only red ones are shown; otherwise each is shown
for 4 seconds in turn). Examples: `HEART RATE HIGH` / `Sit down, rest` (orange), `HEART RATE HIGH` / `Rest, tell crew` (red),
`NO MOVEMENT` / `Stand up, move`, `WEAK SIGNAL` / `Refit the sensor`, `RADIATION WATCH` / `Stay informed`.
- The board's own pulse (below 50 or above 160 bpm) and impact alerts still come first on the LCD, then the dashboard message,
  then the normal sensor screens. If the bridge stops, the message disappears after 8 seconds.
- The heart-rate rule needs about 20 good readings (about 40 seconds). The "Data has gaps today" notice is not shown on the LCD.
- `--no-lcd` turns this off. The wording lives in `lcd_message()` in `tools/serial_bridge.py`.
