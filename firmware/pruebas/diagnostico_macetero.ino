/*
  DIAGNOSTICO MACETERO IOT - v1
  ------------------------------
  Objetivo: comprobar que cada componente soldado responde antes de
  pasar a integrar MQTT / plataforma. No riega solo: la bomba solo se
  activa si mandas 'b' por el Monitor Serie, para no encharcar nada
  mientras estás revisando el resto.

  Comandos por Serial (Monitor Serie, 115200 baud, con salto de linea):
    b  -> activa la bomba 3 segundos (test relé + bomba)
    s  -> fuerza una lectura inmediata de todos los sensores
*/

#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BMP280.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <RTClib.h>

// ---------- PINES (según tu hardware real) ----------
#define SDA_PIN 21
#define SCL_PIN 22
#define SOIL_PIN 34
#define BOMBA_PIN 26

// ---------- CALIBRACIÓN SUELO (de tu código actual) ----------
#define SOIL_DRY 2482
#define SOIL_WET 905

// ---------- OLED ----------
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_ADDR 0x3C

// ---------- OBJETOS ----------
Adafruit_BMP280 bmp;
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);
RTC_DS1307 rtc;

// ---------- ESTADO DE CADA COMPONENTE ----------
bool bmpOk = false;
bool oledOk = false;
bool rtcOk = false;
uint8_t bmpAddrUsada = 0;

unsigned long lastRead = 0;
const unsigned long INTERVALO = 3000; // ms

int soilMoisturePercent(int raw) {
  raw = constrain(raw, SOIL_WET, SOIL_DRY);
  return map(raw, SOIL_DRY, SOIL_WET, 0, 100);
}

void probarBMP280() {
  Serial.println(F("--- BMP280 ---"));
  if (bmp.begin(0x76)) {
    bmpOk = true;
    bmpAddrUsada = 0x76;
  } else if (bmp.begin(0x77)) {
    bmpOk = true;
    bmpAddrUsada = 0x77;
  } else {
    bmpOk = false;
  }

  if (bmpOk) {
    Serial.print(F("OK - detectado en 0x"));
    Serial.println(bmpAddrUsada, HEX);
  } else {
    Serial.println(F("FALLO - no responde en 0x76 ni 0x77. Revisa SDA/SCL y alimentacion."));
  }
}

void probarOLED() {
  Serial.println(F("--- OLED SSD1306 ---"));
  oledOk = display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR);
  if (oledOk) {
    Serial.println(F("OK - detectado en 0x3C"));
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(0, 0);
    display.println("DIAGNOSTICO");
    display.println("iniciando...");
    display.display();
  } else {
    Serial.println(F("FALLO - no responde en 0x3C. Revisa SDA/SCL y alimentacion."));
  }
}

void probarRTC() {
  Serial.println(F("--- RTC DS1307 ---"));
  rtcOk = rtc.begin();
  if (!rtcOk) {
    Serial.println(F("FALLO - RTC no detectado en el bus I2C."));
    return;
  }

  if (!rtc.isrunning()) {
    Serial.println(F("RTC detectado pero PARADO. Ajustando a la hora de compilacion..."));
    rtc.adjust(DateTime(F(__DATE__), F(__TIME__)));
  }

  DateTime now = rtc.now();
  Serial.print(F("OK - hora actual: "));
  Serial.print(now.day());
  Serial.print('/');
  Serial.print(now.month());
  Serial.print('/');
  Serial.print(now.year());
  Serial.print(' ');
  Serial.print(now.hour());
  Serial.print(':');
  Serial.println(now.minute());
}

void probarSuelo() {
  int raw = analogRead(SOIL_PIN);
  int pct = soilMoisturePercent(raw);
  Serial.print(F("--- Humedad suelo --- RAW: "));
  Serial.print(raw);
  Serial.print(F(" | %: "));
  Serial.println(pct);
}

void testBomba() {
  Serial.println(F(">>> TEST BOMBA: activando 3s <<<"));
  digitalWrite(BOMBA_PIN, HIGH);
  delay(3000);
  digitalWrite(BOMBA_PIN, LOW);
  Serial.println(F(">>> TEST BOMBA: completado <<<"));
}

void leerYMostrarTodo() {
  Serial.println(F("========================================"));

  probarSuelo();

  if (bmpOk) {
    float t = bmp.readTemperature();
    float p = bmp.readPressure() / 100.0F;
    Serial.print(F("--- BMP280 --- Temp: "));
    Serial.print(t, 1);
    Serial.print(F(" C | Presion: "));
    Serial.print(p, 1);
    Serial.println(F(" hPa"));

    if (oledOk) {
      display.clearDisplay();
      display.setTextSize(1);
      display.setCursor(0, 0);
      display.println("AMBIENTE");
      display.setTextSize(2);
      display.setCursor(0, 16);
      display.print(t, 1);
      display.print(" C");
      display.setTextSize(1);
      display.setCursor(0, 42);
      display.print(p, 0);
      display.print(" hPa");
      display.display();
    }
  } else {
    Serial.println(F("--- BMP280 --- (no disponible, sin lectura)"));
  }

  if (rtcOk) {
    DateTime now = rtc.now();
    Serial.print(F("--- RTC --- "));
    Serial.print(now.hour());
    Serial.print(':');
    Serial.println(now.minute());
  }

  Serial.println(F("Comandos: 'b' = test bomba 3s | 's' = leer ahora"));
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println(F("\n\n===== DIAGNOSTICO MACETERO IOT ====="));

  Wire.begin(SDA_PIN, SCL_PIN);

  pinMode(BOMBA_PIN, OUTPUT);
  digitalWrite(BOMBA_PIN, LOW); // bomba apagada por seguridad

  probarBMP280();
  probarOLED();
  probarRTC();

  Serial.println(F("=====================================\n"));
  Serial.println(F("Escribe 'b' + Enter para probar la bomba 3s."));
  Serial.println(F("Escribe 's' + Enter para forzar una lectura.\n"));
}

void loop() {
  if (Serial.available()) {
    char c = Serial.read();
    if (c == 'b' || c == 'B') {
      testBomba();
    } else if (c == 's' || c == 'S') {
      leerYMostrarTodo();
    }
  }

  if (millis() - lastRead > INTERVALO) {
    lastRead = millis();
    leerYMostrarTodo();
  }
}
