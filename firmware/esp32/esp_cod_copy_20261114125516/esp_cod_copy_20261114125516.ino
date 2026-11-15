// ASTRA ESP32 sketch: reads the MAX30102 (heart rate) and the ICM-20948 (motion), shows them on the OLED, the LCD and the
// serial monitor, sounds the buzzer on a local alert, and POSTS one measurement every 2 seconds to the ASTRA backend
// (payload: docs/api_contract.md). Wi-Fi name, password, server URL and device id live in secrets.h (copy
// secrets.example.h to secrets.h; secrets.h is git-ignored and must never be committed).
//
// USB mode (live demo with the board plugged into the laptop): ENABLE_NETWORK 0 and USB_STREAM 1. No Wi-Fi is needed. Every
// 2 seconds the sketch prints one line "ASTRA_JSON {...}" on the serial port; backend/serial_bridge.py reads it and POSTs it
// to the dashboard. Close the Arduino Serial Monitor first: only one program can use the port.
// Notifications on the LCD: the bridge also sends back one line "ASTRA_MSG <line 1>|<line 2>" (16 characters each) with the
// current dashboard notification. The LCD shows it (local pulse/impact alerts still come first). If no message arrives for
// HOST_MSG_HOLD_MS the LCD goes back to the sensor screens.
// Wi-Fi mode: ENABLE_NETWORK 1 (the board sends by itself). Both can be on at the same time.
// The blood oxygen (SpO2) is NOT computed by this sketch, so it is sent as null (never 0).

#define ENABLE_NETWORK 0   // 0 = USB demo / bench (no Wi-Fi, no secrets.h needed), 1 = send over Wi-Fi
#define USB_STREAM 1       // 1 = print one "ASTRA_JSON {...}" line every SEND_INTERVAL_MS on the serial port
#define USB_DEVICE_ID "ASTRA-01"
#define HOST_MSG_HOLD_MS 8000   // a dashboard message stays on the LCD this long without a refresh from the bridge

#include <Wire.h>
#include <math.h>
#if ENABLE_NETWORK
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>   // Library Manager: "ArduinoJson" version 7
#include "secrets.h"
#endif
#include "MAX30105.h"
#include "heartRate.h"
#include "ICM_20948.h"
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <LiquidCrystal.h>

#define SDA_PIN 21
#define SCL_PIN 22
#define BUZZER_PIN 32

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1

const int rs = 23, en = 25, d4 = 26, d5 = 27, d6 = 18, d7 = 19;
LiquidCrystal lcd(rs, en, d4, d5, d6, d7);

#define PRAG_DEGET_ON 20000
#define PRAG_DEGET_OFF 12000

#define OLED_INTERVAL 3000     
#define SERIAL_INTERVAL 3000   
#define LCD_INTERVAL 5000
#define IMU_INTERVAL 40
#define OLED_START_DURATION 2000

// ---- network (only used when ENABLE_NETWORK is 1) ----
#define SEND_INTERVAL_MS 2000          // one measurement every 2 seconds (the dashboard expects about this rate)
#define WIFI_CONNECT_TIMEOUT_MS 15000  // how long setup() waits for Wi-Fi; sensors keep working without it
#define WIFI_RETRY_MS 10000            // while disconnected, try again this often (no restart)
#define HTTP_TIMEOUT_MS 1500           // short, so a missing server does not stall the sensor FIFO for long
#define FAIL_BACKOFF_MS 6000           // after a failed POST, wait this long before the next try

// ---- local alert (buzzer). These thresholds belong to this demo device only. They are NOT NASA values and are NOT the
// ---- dashboard's rules (the dashboard compares you with your own baseline and raises its own notifications).
#define BUZZER_ON_LEVEL LOW            // LOW = sounds when the pin is LOW (active-low module). Use HIGH for an active-high one.
#define ALERT_BPM_LOW 50.0f
#define ALERT_BPM_HIGH 160.0f
#define ALERT_IMPACT_G 2.5f

MAX30105 particleSensor;
ICM_20948_I2C imu;

Adafruit_SSD1306 display(
  SCREEN_WIDTH,
  SCREEN_HEIGHT,
  &Wire,
  OLED_RESET
);

bool maxOK = false;
bool imuOK = false;
bool oledOK = false;

uint8_t oledAddress = 0;
uint8_t imuAddress = 0;

const byte RATE_SIZE = 4;
float rates[RATE_SIZE] = {0};
byte rateSpot = 0;
byte rateCount = 0;

unsigned long lastBeat = 0;
unsigned long fingerStart = 0;

float beatsPerMinute = 0;
float beatAverage = 0;

uint32_t irValue = 0;
uint32_t redValue = 0;

bool fingerPresent = false;

float ax = 0;
float ay = 0;
float az = 0;

float gx = 0;
float gy = 0;
float gz = 0;

float acceleratieTotala = 0;
float rotatieTotala = 0;

unsigned long lastOLED = 0;
unsigned long lastSerial = 0;
unsigned long lastLCD = 0;
unsigned long lastIMU = 0;

unsigned long oledStartMillis = 0;
bool oledSplashFinished = false;

int lcdScreenState = 0;

// network state (for the displays and the serial monitor)
unsigned long lastSend = 0;
unsigned long lastWifiTry = 0;
unsigned long nextSendAllowed = 0;
int lastHttpCode = 0;              // 0 = nothing sent yet, negative = network error, otherwise the HTTP code
bool networkEnabled = (ENABLE_NETWORK != 0);

// message from the dashboard for the LCD (see "Notifications on the LCD" at the top)
char hostLine1[17] = "";
char hostLine2[17] = "";
unsigned long hostMsgUntil = 0;
bool hostMsgActive() {
  return hostMsgUntil != 0 && (long)(hostMsgUntil - millis()) > 0 && hostLine1[0] != '\0';
}

void netText(char* out, size_t size);   // defined below (used by the OLED and the serial output)

bool existaI2C(uint8_t adresa) {
  Wire.beginTransmission(adresa);
  return Wire.endTransmission() == 0;
}

void scanI2C() {
  Serial.println("[I2C] Scanning devices...");

  for (uint8_t a = 1; a < 127; a++) {
    if (existaI2C(a)) {
      Serial.print("Found: 0x");

      if (a < 16) {
        Serial.print("0");
      }

      Serial.println(a, HEX);
    }
  }
}

void resetPuls() {
  lastBeat = 0;
  beatsPerMinute = 0;
  beatAverage = 0;

  rateSpot = 0;
  rateCount = 0;

  for (byte i = 0; i < RATE_SIZE; i++) {
    rates[i] = 0;
  }
}

void initMAX() {
  Serial.println("[MAX30102] Initializing...");

  if (!existaI2C(0x57)) {
    Serial.println("[ERROR] MAX30102 missing!");
    return;
  }

  if (!particleSensor.begin(Wire, I2C_SPEED_FAST)) {
    Serial.println("[ERROR] MAX initialization failed!");
    return;
  }

  particleSensor.setup(
    0x1F,
    4,
    2,
    400,
    411,
    4096
  );

  particleSensor.setPulseAmplitudeRed(0x0A);
  particleSensor.setPulseAmplitudeIR(0x1F);
  particleSensor.setPulseAmplitudeGreen(0);

  maxOK = true;

  Serial.println("[OK] MAX30102 functional!");
}

void initIMU() {
  Serial.println("[ICM] Initializing...");

  if (existaI2C(0x68)) {
    imuAddress = 0x68;
  }
  else if (existaI2C(0x69)) {
    imuAddress = 0x69;
  }
  else {
    Serial.println("[ERROR] ICM not found!");
    return;
  }

  imu.begin(Wire, imuAddress == 0x69);

  if (imu.status == ICM_20948_Stat_Ok) {
    imuOK = true;
    Serial.println("[OK] ICM-20948 functional!");
  }
  else {
    Serial.print("[ERROR] ICM: ");
    Serial.println(imu.statusString());
  }
}

void initOLED() {
  Serial.println("[OLED] Initializing...");

  if (existaI2C(0x3C)) {
    oledAddress = 0x3C;
  }
  else if (existaI2C(0x3D)) {
    oledAddress = 0x3D;
  }
  else {
    Serial.println("[ERROR] OLED not found!");
    return;
  }

  if (!display.begin(
    SSD1306_SWITCHCAPVCC,
    oledAddress,
    true,
    false
  )) {
    Serial.println("[ERROR] OLED initialization failed!");
    return;
  }

  oledOK = true;

  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);

  display.setCursor(0, 8);
  display.println("ESP32 MONITOR");

  display.setCursor(0, 28);
  display.println("MAX + ICM + OLED");

  display.setCursor(0, 48);
  display.println("Initializing:");

  display.print("MAX ");
  display.print(maxOK ? "OK " : "ERR ");
  display.print("ICM ");
  display.print(imuOK ? "OK" : "ERR");

  display.display();

  oledStartMillis = millis();
  oledSplashFinished = false;

  Serial.println("[OK] OLED functional!");
}

void citestePuls() {
  if (!maxOK) return;

  particleSensor.check();

  while (particleSensor.available()) {

    irValue = particleSensor.getFIFOIR();
    redValue = particleSensor.getFIFORed();

    particleSensor.nextSample();

    if (!fingerPresent &&
        irValue > PRAG_DEGET_ON) {

      fingerPresent = true;
      fingerStart = millis();

      resetPuls();

      Serial.println("[MAX] Finger detected!");
    }

    else if (fingerPresent &&
             irValue < PRAG_DEGET_OFF) {

      fingerPresent = false;
      resetPuls();

      Serial.println("[MAX] Finger removed!");
    }

    if (!fingerPresent) {
      continue;
    }

    bool beatDetected = checkForBeat(irValue);

    if (millis() - fingerStart < 1500) {
      continue;
    }

    if (beatDetected) {

      unsigned long acum = millis();

      if (lastBeat != 0) {

        unsigned long delta = acum - lastBeat;

        if (delta > 0) {

          float bpmNou = 60000.0f / delta;

          if (bpmNou >= 40 && bpmNou <= 220) {

            beatsPerMinute = bpmNou;

            rates[rateSpot] = bpmNou;

            rateSpot =
              (rateSpot + 1) % RATE_SIZE;

            if (rateCount < RATE_SIZE) {
              rateCount++;
            }

            float suma = 0;

            for (byte i = 0; i < rateCount; i++) {
              suma += rates[i];
            }

            beatAverage = suma / rateCount;

            Serial.print("[PULSE] BPM: ");
            Serial.print(beatsPerMinute, 1);

            Serial.print(" | Average: ");
            Serial.println(beatAverage, 1);
          }
        }
      }

      lastBeat = acum;
    }

    if (lastBeat != 0 &&
        millis() - lastBeat > 3000) {

      resetPuls();
    }
  }
}

void citesteIMU() {
  if (!imuOK) return;

  if (millis() - lastIMU < IMU_INTERVAL) {
    return;
  }

  lastIMU = millis();

  if (imu.dataReady()) {

    imu.getAGMT();

    ax = imu.accX();
    ay = imu.accY();
    az = imu.accZ();

    gx = imu.gyrX();
    gy = imu.gyrY();
    gz = imu.gyrZ();

    acceleratieTotala = sqrtf(
      (ax/1000.0f) * (ax/1000.0f) +
      (ay/1000.0f) * (ay/1000.0f) +
      (az/1000.0f) * (az/1000.0f)
    );

    rotatieTotala = sqrtf(
      gx * gx +
      gy * gy +
      gz * gz
    );
  }
}

void gestioneazaAlertaBuzzer() {
  bool hazardDetected = false;

  if (fingerPresent && rateCount > 0 && (beatAverage < ALERT_BPM_LOW || beatAverage > ALERT_BPM_HIGH)) {
    hazardDetected = true;
  }

  if (imuOK && acceleratieTotala > ALERT_IMPACT_G) {
    hazardDetected = true;
  }

  digitalWrite(BUZZER_PIN, hazardDetected ? BUZZER_ON_LEVEL : !BUZZER_ON_LEVEL);   // silent unless there is an alert
}

void actualizeazaOLED() {
  if (!oledOK) return;

  if (!oledSplashFinished) {

    if (millis() - oledStartMillis <
        OLED_START_DURATION) {

      return;
    }

    oledSplashFinished = true;
  }

  if (millis() - lastOLED < OLED_INTERVAL) {
    return;
  }

  lastOLED = millis();

  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);

  display.setTextSize(1);
  display.setCursor(0, 0);

  display.print("MAX:");
  display.print(maxOK ? "OK" : "ERR");

  display.print("  ICM:");
  display.print(imuOK ? "OK" : "ERR");

  display.setTextSize(2);
  display.setCursor(0, 13);

  if (!maxOK) {
    display.print("MAX OFF");
  }
  else if (!fingerPresent) {
    display.print("NO FINGER");
  }
  else if (rateCount == 0) {
    display.print("BPM: --");
  }
  else {
    display.print("BPM:");
    display.print((int)(beatAverage + 0.5f));
  }

  display.setTextSize(1);
  display.setCursor(0, 34);
  char net[24];
  netText(net, sizeof(net));
  display.print(net);

  display.setCursor(0, 45);

  if (imuOK) {
    display.print("Acc:");
    display.print(acceleratieTotala, 2);
    display.print(" g");
  }
  else {
    display.print("IMU unavailable");
  }

  display.setCursor(0, 55);

  if (imuOK) {
    display.print("Gyro:");
    display.print(rotatieTotala, 1);
    display.print(" dps");
  }

  display.display();
}

void actualizeazaLCD() {
  if (millis() - lastLCD < LCD_INTERVAL) {
    return;
  }
  lastLCD = millis();

  lcd.clear();

  bool hrWarning = (fingerPresent && rateCount > 0 && (beatAverage < ALERT_BPM_LOW || beatAverage > ALERT_BPM_HIGH));
  bool impactWarning = (imuOK && acceleratieTotala > ALERT_IMPACT_G);

  if (hrWarning) {
    lcd.setCursor(0, 0);
    lcd.print("WARNING: PULSE!");
    lcd.setCursor(0, 1);
    lcd.print("BPM: ");
    lcd.print((int)(beatAverage + 0.5f));
  } 
  else if (impactWarning) {
    lcd.setCursor(0, 0);
    lcd.print("WARNING: IMPACT!");
    lcd.setCursor(0, 1);
    lcd.print("Acc: ");
    lcd.print(acceleratieTotala, 2);
    lcd.print(" g");
  }
  else if (hostMsgActive()) {
    lcd.setCursor(0, 0);
    lcd.print(hostLine1);
    lcd.setCursor(0, 1);
    lcd.print(hostLine2);
  }
  else {
    if (lcdScreenState == 0) {
      lcd.setCursor(0, 0);
      lcd.print("IR: ");
      lcd.print(irValue);

      lcd.setCursor(0, 1);
      if (!fingerPresent) {
        lcd.print("Finger: NO");
      } else if (rateCount == 0) {
        lcd.print("BPM: --");
      } else {
        lcd.print("BPM: ");
        lcd.print((int)(beatAverage + 0.5f));
      }

      lcdScreenState = 1;
    } 
    else if (lcdScreenState == 1) {
      lcd.setCursor(0, 0);
      lcd.print("ACC X/Y/Z (mg):");

      lcd.setCursor(0, 1);
      lcd.print((int)ax);
      lcd.print("/");
      lcd.print((int)ay);
      lcd.print("/");
      lcd.print((int)az);

      lcdScreenState = 2;
    } 
    else {
      lcd.setCursor(0, 0);
      lcd.print("GYRO (dps):");

      lcd.setCursor(0, 1);
      lcd.print((int)gx);
      lcd.print("/");
      lcd.print((int)gy);
      lcd.print("/");
      lcd.print((int)gz);

      lcdScreenState = 0;
    }
  }
}

void afiseazaSerial() {

  if (millis() - lastSerial < SERIAL_INTERVAL) {
    return;
  }

  lastSerial = millis();

  Serial.println("------------------------");
  Serial.println("------ ASTRA ------");

  (void)redValue; // read but not used: SpO2 is not computed in this sketch
  char net[24];
  netText(net, sizeof(net));
  Serial.println(net);

  if (maxOK) {
    Serial.print("IR: ");
    Serial.println(irValue);

    Serial.print("Finger: ");
    Serial.println(fingerPresent ? "YES" : "NO");
  }
  else {
    Serial.println("MAX30102 unavailable");
  }

  if (imuOK) {
    Serial.print("ICM: OK\n");
    Serial.print("ACC X/Y/Z (mg): ");
    Serial.print(ax, 1);
    Serial.print(" / ");
    Serial.print(ay, 1);
    Serial.print(" / ");
    Serial.println(az, 1);

    Serial.print("GYRO X/Y/Z (dps): ");
    Serial.print(gx, 1);
    Serial.print(" / ");
    Serial.print(gy, 1);
    Serial.print(" / ");
    Serial.println(gz, 1);
  }
  else {
    Serial.println("IMU unavailable");
  }
}

// false until the IMU has delivered its first reading (the variables start at 0, which must not be sent as a measurement)
bool imuHasData() {
  return !(ax == 0 && ay == 0 && az == 0);
}

// "good" only when a finger is on the sensor AND a heart rate has been computed; "poor" when a finger is on but there is no
// heart rate yet; "no_finger" when no finger is detected. This is all the firmware really knows, so nothing else is claimed.
const char* signalQuality() {
  if (!maxOK || !fingerPresent) return "no_finger";
  return rateCount > 0 ? "good" : "poor";
}

#if ENABLE_NETWORK
bool wifiUp() {
  return WiFi.status() == WL_CONNECTED;
}

void connectWifi(unsigned long timeoutMs) {
  Serial.print("[WIFI] Connecting");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  unsigned long start = millis();
  while (!wifiUp() && millis() - start < timeoutMs) {
    delay(500);
    Serial.print(".");
  }
  lastWifiTry = millis();
  if (wifiUp()) {
    Serial.print("\n[WIFI] Connected, IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\n[WIFI] Not connected yet. Sensors keep working; retrying in the background.");
  }
}

void maintainWifi() {
  if (wifiUp() || millis() - lastWifiTry < WIFI_RETRY_MS) return;
  lastWifiTry = millis();
  Serial.println("[WIFI] Lost connection, reconnecting...");
  WiFi.disconnect();
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
}

float round3(float value) {
  return roundf(value * 1000.0f) / 1000.0f;
}

// Builds the payload of docs/api_contract.md. A value the sensors cannot give is sent as null, never as 0.
void sendMeasurement() {
  if (millis() - lastSend < SEND_INTERVAL_MS || millis() < nextSendAllowed) return;
  lastSend = millis();
  if (!wifiUp()) {
    lastHttpCode = -1;
    return;
  }

  JsonDocument doc;
  doc["device_id"] = DEVICE_ID;
  if (maxOK && fingerPresent && rateCount > 0) {
    doc["heart_rate_bpm"] = (int)(beatAverage + 0.5f);
  } else {
    doc["heart_rate_bpm"] = nullptr;
  }
  doc["spo2_percent"] = nullptr;                       // not computed by this sketch
  if (imuOK && imuHasData() && isfinite(ax) && isfinite(ay) && isfinite(az) && isfinite(gx) && isfinite(gy) && isfinite(gz)) {
    doc["accel_x_g"] = round3(ax / 1000.0f);           // the ICM library gives milli-g
    doc["accel_y_g"] = round3(ay / 1000.0f);
    doc["accel_z_g"] = round3(az / 1000.0f);
    doc["gyro_x_dps"] = round3(gx);
    doc["gyro_y_dps"] = round3(gy);
    doc["gyro_z_dps"] = round3(gz);
  } else {
    doc["accel_x_g"] = nullptr;
    doc["accel_y_g"] = nullptr;
    doc["accel_z_g"] = nullptr;
    doc["gyro_x_dps"] = nullptr;
    doc["gyro_y_dps"] = nullptr;
    doc["gyro_z_dps"] = nullptr;
  }
  doc["signal_quality"] = signalQuality();
  doc["source"] = "live_hardware";
  doc["uptime_ms"] = millis();                         // the backend records the time it received the measurement

  String body;
  serializeJson(doc, body);

  WiFiClient client;
  HTTPClient http;
  http.begin(client, SERVER_URL);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(HTTP_TIMEOUT_MS);
  int code = http.POST(body);
  http.end();
  lastHttpCode = code;

  Serial.print("[SEND] ");
  Serial.print(body);
  Serial.print(" -> HTTP ");
  Serial.println(code);
  if (code != 201) {
    nextSendAllowed = millis() + FAIL_BACKOFF_MS;      // do not hammer a missing or unhappy server
  }
}
#else
bool wifiUp() { return false; }
void connectWifi(unsigned long) {}
void maintainWifi() {}
void sendMeasurement() {}
#endif

// short text for the OLED: "Net:OK Srv:201", "Net:OK Srv:ERR", "Net:--" ...
void netText(char* out, size_t size) {
  if (!networkEnabled) {
    snprintf(out, size, USB_STREAM ? "USB -> laptop" : "Net: off (bench)");
  } else if (!wifiUp()) {
    snprintf(out, size, "Net:NO WIFI");
  } else if (lastHttpCode == 0) {
    snprintf(out, size, "Net:OK Srv:--");
  } else if (lastHttpCode == 201) {
    snprintf(out, size, "Net:OK Srv:201");
  } else {
    snprintf(out, size, "Net:OK Srv:ERR");
  }
}

// Reads "ASTRA_MSG line1|line2" lines from the laptop without blocking. Only printable ASCII is kept, 16 characters per line.
void readHostMessage() {
  static char buf[48];
  static byte n = 0;
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c != '\n') {
      if (n < sizeof(buf) - 1) buf[n++] = c;
      continue;
    }
    buf[n] = '\0';
    n = 0;
    if (strncmp(buf, "ASTRA_MSG ", 10) != 0) continue;
    char* sep = strchr(buf + 10, '|');
    if (sep == NULL) continue;
    *sep = '\0';
    strncpy(hostLine1, buf + 10, 16);
    hostLine1[16] = '\0';
    strncpy(hostLine2, sep + 1, 16);
    hostLine2[16] = '\0';
    hostMsgUntil = millis() + HOST_MSG_HOLD_MS;      // an empty line 1 means "no notification": the LCD shows the sensor screens
  }
}

#if USB_STREAM
unsigned long lastUsbLine = 0;

// One JSON line for the laptop (same fields as docs/api_contract.md). A value the sensors cannot give is null, never 0.
void usbStream() {
  if (millis() - lastUsbLine < SEND_INTERVAL_MS) return;
  lastUsbLine = millis();

  char hr[8];
  if (maxOK && fingerPresent && rateCount > 0) snprintf(hr, sizeof(hr), "%d", (int)(beatAverage + 0.5f));
  else snprintf(hr, sizeof(hr), "null");

  char motion[160];
  if (imuOK && imuHasData() && isfinite(ax) && isfinite(ay) && isfinite(az) && isfinite(gx) && isfinite(gy) && isfinite(gz)) {
    snprintf(motion, sizeof(motion), "\"accel_x_g\":%.3f,\"accel_y_g\":%.3f,\"accel_z_g\":%.3f,\"gyro_x_dps\":%.3f,\"gyro_y_dps\":%.3f,\"gyro_z_dps\":%.3f",
             ax / 1000.0f, ay / 1000.0f, az / 1000.0f, gx, gy, gz);   // the ICM library gives milli-g
  } else {
    snprintf(motion, sizeof(motion), "\"accel_x_g\":null,\"accel_y_g\":null,\"accel_z_g\":null,\"gyro_x_dps\":null,\"gyro_y_dps\":null,\"gyro_z_dps\":null");
  }

  Serial.printf("ASTRA_JSON {\"device_id\":\"%s\",\"heart_rate_bpm\":%s,\"spo2_percent\":null,%s,\"signal_quality\":\"%s\",\"source\":\"live_hardware\",\"uptime_ms\":%lu}\n",
                USB_DEVICE_ID, hr, motion, signalQuality(), (unsigned long)millis());
}
#else
void usbStream() {}
#endif

void setup() {

  Serial.begin(115200);
  delay(1000);

  // Set the pin to the "silent" level before pinMode so the buzzer does not chirp at boot
  digitalWrite(BUZZER_PIN, !BUZZER_ON_LEVEL);
  pinMode(BUZZER_PIN, OUTPUT);

  Serial.println();
  Serial.println("========================");
  Serial.println("ASTRA ESP32: sensors + displays + send");
  Serial.println("MAX30102 + ICM-20948 + OLED + LCD");
  Serial.println("========================");

  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(400000);

  scanI2C();

  lcd.begin(16, 2);
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("ASTRA SYSTEM");
  lcd.setCursor(0, 1);
  lcd.print("Starting...");
  delay(1500);

  initMAX();
  initIMU();
  initOLED();

  if (networkEnabled) {
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("WiFi...");
    connectWifi(WIFI_CONNECT_TIMEOUT_MS);
  }

  Serial.println("[INFO] Monitoring started!");
}

void loop() {
  citestePuls();
  citesteIMU();
  maintainWifi();
  sendMeasurement();
  usbStream();
  readHostMessage();
  gestioneazaAlertaBuzzer();
  actualizeazaOLED();
  actualizeazaLCD();
  afiseazaSerial();
}