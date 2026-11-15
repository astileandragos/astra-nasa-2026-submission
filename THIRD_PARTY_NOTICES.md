# Third-party notices

ASTRA is built on open-source software written by others. This file lists what the project actually uses, where it comes from and under which licence. Licences were read from the installed packages and library folders on the build machine, or from the project's GitHub licence file (the GitHub licence API, 15 Nov 2026). Where something could not be verified, the text says so.

This file covers **software**. NASA and NOAA documents and data are cited in `docs/RESOURCES.md`; they are research sources, not software, and their terms of use are separate (see section 4).

## 1. Dependencies actually used

### Backend and tools (Python)
| Component | Version used | Licence | Official source | Copyright notice seen |
|---|---|---|---|---|
| Flask | 3.1.3 | BSD-3-Clause (licence file in the installed package) | https://github.com/pallets/flask , https://flask.palletsprojects.com | Copyright 2010 Pallets |
| Flask-CORS | 6.0.5 | MIT (package metadata; the upstream LICENSE on GitHub) | https://github.com/corydolphin/flask-cors | Copyright (C) 2025 Cory Dolphin (upstream LICENSE, read 15 Nov 2026) |
| Requests | 2.34.2 | Apache-2.0 (licence file in the installed package) | https://github.com/psf/requests , https://requests.readthedocs.io | The upstream LICENSE is the standard Apache-2.0 text with no separate copyright line |
| pySerial | 3.5 | BSD-3-Clause (the upstream LICENSE.txt contains the three conditions, including the no-endorsement clause; the licence file is not in the installed package) | https://github.com/pyserial/pyserial | Copyright (c) 2001-2020 Chris Liechti (upstream LICENSE.txt, read 15 Nov 2026) |
| pytest (development only) | 9.2.0 | MIT (licence file in the installed package) | https://github.com/pytest-dev/pytest , https://docs.pytest.org | Copyright (c) 2004 Holger Krekel and others |

SQLite and the Python standard library are not listed as separate dependencies.

### Dashboard (JavaScript, bundled in `frontend/chart.js`)
| Component | Version used | Licence | Official source | Copyright notice seen |
|---|---|---|---|---|
| Chart.js | 4.6.1 | MIT (stated in the file header; GitHub) | https://www.chartjs.org , https://github.com/chartjs/Chart.js | (c) 2026 Chart.js Contributors |
| @kurkle/color (bundled inside `chart.js`) | 0.3.2 | MIT (stated in the file header) | https://github.com/kurkle/color | (c) 2023 Jukka Kurkela |

The notices in the header comments of `frontend/chart.js` must stay in the file.

### Firmware (Arduino / ESP32)
| Component | Version used | Licence | Official source | Copyright notice seen |
|---|---|---|---|---|
| Arduino core for the ESP32 (arduino-esp32) | 3.3.12 | LGPL-2.1 (GitHub licence file). The core bundles other components with their own licences; they are listed in the upstream repository and are not reproduced here | https://github.com/espressif/arduino-esp32 | Free Software Foundation text; Espressif copyright lines not read |
| SparkFun MAX3010x Pulse and Proximity Sensor Library (`MAX30105.h`, `heartRate.h`) | 1.1.2 | Code: MIT (the library's `LICENSE.md`; its hardware files use CC BY-SA 4.0, which does not apply to ASTRA) | https://github.com/sparkfun/SparkFun_MAX3010x_Sensor_Library | Copyright (c) 2016 SparkFun Electronics |
| SparkFun ICM-20948 Arduino Library (`ICM_20948.h`) | 1.3.2 | Code: MIT (the library's `License.md`) | https://github.com/sparkfun/SparkFun_ICM-20948_ArduinoLibrary | Copyright (c) 2016 SparkFun Electronics |
| Adafruit SSD1306 | 2.5.17 | "Software License Agreement (BSD License)" in the library's `license.txt` | https://github.com/adafruit/Adafruit_SSD1306 | Copyright (c) 2012, Adafruit Industries |
| Adafruit GFX Library | 1.13.0 | "Software License Agreement (BSD License)" in the library's `license.txt` | https://github.com/adafruit/Adafruit-GFX-Library | Copyright (c) 2012 Adafruit Industries |
| Adafruit BusIO (installed as a dependency of the Adafruit libraries) | 1.17.4 | MIT (the library's `LICENSE`) | https://github.com/adafruit/Adafruit_BusIO | Copyright (c) 2017 Adafruit Industries |
| LiquidCrystal | 1.0.7 | LGPL-2.1 (the upstream repository has a `LICENSE.txt`, read via the GitHub licence API 15 Nov 2026; the installed library folder has no licence file, so include the upstream text if you ever redistribute the library) | https://github.com/arduino-libraries/LiquidCrystal | Not found locally |
| ArduinoJson (only when Wi-Fi mode `ENABLE_NETWORK 1` is built) | 7.x (the sketch comment asks for version 7; the library was not installed on the build machine, because only USB mode was built) | MIT (upstream LICENSE.txt) | https://arduinojson.org , https://github.com/bblanchon/ArduinoJson | Copyright 2014-2026 Benoit Blanchon (upstream file, read 15 Nov 2026) |

## 2. What must stay intact
- **MIT and BSD components:** keep the copyright notice and the licence text with any copy of the source, including the header comments inside `frontend/chart.js`. If this repository ever distributes the Python packages or the Arduino libraries themselves, include their LICENSE files; at the moment only references to them are in the repository.
- **Apache-2.0 (Requests):** keep the licence text and any NOTICE file when redistributing Requests.
- **LGPL-2.1 (Arduino ESP32 core, LiquidCrystal):** ASTRA's firmware is distributed here as **source code**. Handing out a compiled firmware image (a `.bin` or a flashed board that is passed on) would also bring LGPL obligations (the licence text, a notice and a way to relink). The repository distributes source only; if a compiled image is ever handed out, add the licence texts and the required notices first.
- **Adafruit BSD licences:** the redistribution conditions and the disclaimer in `license.txt` apply to source and binary copies.

## 3. ASTRA's own code
The team's original code and documentation are released under the **MIT License** (`LICENSE` at the repository root, copyright held by the team members). MIT is OSI-approved, permissive and compatible with the dependencies above. The licence covers only the team's own work (`backend/`, `frontend/` except `chart.js`, `firmware/`, `tools/`, `docs/`); it does not relicense the third-party components, which keep their own licences and notices (section 2). If the team prefers Apache-2.0 (which adds an explicit patent grant), replace the `LICENSE` file and this paragraph.

## 4. Research sources and data (not software licences)
- NASA documents and pages, NOAA Space Weather Prediction Center data, the Canadian Space Agency pages, the National Academies report and the articles in `docs/RESOURCES.md` are cited as sources. ASTRA does not copy or redistribute them, apart from short quotations and facts with the source named. Their terms of use differ and were **not** checked for this file; check them before reusing any figure or image.
- NASA images used in the presentation must be credited to NASA, and NASA's media usage guidelines apply.
- Images or text generated with AI tools must be acknowledged (see the README).
