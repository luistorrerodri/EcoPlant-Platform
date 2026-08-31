#include <WiFi.h>
#include <Arduino.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BMP280.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <RTClib.h>
#include "secrets.h"

// ---------- PINES ----------
#define SDA_PIN 21
#define SCL_PIN 22
#define SOIL_PIN 34
#define BOMBA_PIN 27

// ---------- CALIBRACIÓN SUELO ----------
#define SOIL_DRY 2482
#define SOIL_WET 905

// ---------- WIFI (definido en secrets.h) ----------
const char* ssid = WIFI_SSID;
const char* pass = WIFI_PASS;

// ---------- MQTT ----------
const char* mqtt_server = "192.168.1.140";
const int mqtt_port = 1883;
const char* mqtt_client_id = "esp32_macetero01"; // único por dispositivo si añades más adelante
const char* mqtt_topic = "planta_datos";
const char* mqtt_topic_comando = "planta_datos/comando";

volatile bool riegoManualSolicitado = false;

// ---------- RIEGO ----------
// Duración del pulso de riego. El umbral y la franja horaria ya no
// se gestionan aquí: la decisión de CUÁNDO regar vive en Node-RED.
#define TIEMPO_RIEGO 9000   // 9 segundos

// ---------- OLED ----------
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1
#define OLED_ADDR 0x3C

unsigned long lastScreenChange = 0;
int screenIndex = 0;

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// ---------- OBJETOS ----------
WiFiClient espClient;
PubSubClient client(espClient);
Adafruit_BMP280 bmp;
RTC_DS1307 rtc;

bool bmpOk = false;

// ---------- TIMING ----------
unsigned long lastSend = 0;
unsigned long ultimoRiego = 0;

// ---------- FUNCIONES ----------
int soilMoisturePercent(int raw) {
  raw = constrain(raw, SOIL_WET, SOIL_DRY);
  return map(raw, SOIL_DRY, SOIL_WET, 0, 100);
}

String soilStatus(int soilPct) {
  if (soilPct < 25) return "SECO";
  if (soilPct < 36) return "NECESITA_RIEGO";
  if (soilPct <= 65) return "OK";
  if (soilPct <= 80) return "HUMEDO";
  return "EXCESO_AGUA";
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String mensaje;
  for (unsigned int i = 0; i < length; i++) {
    mensaje += (char)payload[i];
  }

  Serial.print("Comando recibido en ");
  Serial.print(topic);
  Serial.print(": ");
  Serial.println(mensaje);

  if (mensaje == "REGAR") {
    riegoManualSolicitado = true;
  }
}

void connectWiFi() {
  Serial.print("Conectando a WiFi");
  WiFi.begin(ssid, pass);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi conectado");
}

void reconnectMQTT() {
  while (!client.connected()) {
    Serial.print("Conectando MQTT...");
    if (client.connect(mqtt_client_id)) {
      Serial.println(" conectado");
      client.subscribe(mqtt_topic_comando);
    } else {
      Serial.print(" fallo rc=");
      Serial.println(client.state());
      delay(2000);
    }
  }
}

void updateDisplay(float t, float p, int soilPct, String estado, DateTime now) {

  if (millis() - lastScreenChange > 4000) {
    lastScreenChange = millis();
    screenIndex = (screenIndex + 1) % 4;
  }

  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);

  switch (screenIndex) {

    // ---------- PANTALLA 1: AMBIENTE ----------
    case 0:
      display.setTextSize(1);
      display.setCursor(0, 0);
      display.print("AMBIENTE");
      display.drawLine(0, 14, 127, 14, SSD1306_WHITE);

      display.setTextSize(2);
      display.setCursor(0, 16);
      display.print("T:");
      display.print(t, 1);
      display.print(" C");

      display.setTextSize(1);
      display.setCursor(0, 42);
      display.print("Presion: ");
      display.print(p, 0);
      display.print(" hPa");
      break;

    // ---------- PANTALLA 2: SUELO ----------
    case 1:
      display.setTextSize(1);
      display.setCursor(0, 0);
      display.print("SUELO");
      display.drawLine(0, 14, 127, 14, SSD1306_WHITE);

      display.setTextSize(2);
      display.setCursor(0, 20);
      display.print(soilPct);
      display.print(" %");
      break;

    // ---------- PANTALLA 3: ESTADO ----------
    case 2:
      display.setTextSize(1);
      display.setCursor(0, 0);
      display.print("ESTADO PLANTA");
      display.drawLine(0, 14, 127, 14, SSD1306_WHITE);

      display.setTextSize(2);
      display.setCursor(10, 28);

      if (estado == "OK") {
        display.print("OK");
      } else if (estado == "NECESITA_RIEGO") {
        display.print("RIEGO");
      } else if (estado == "SECO") {
        display.print("SECO");
      } else if (estado == "HUMEDO") {
        display.print("HUMEDO");
      } else {
        display.print("AGUA!");
      }
      break;

    // ---------- PANTALLA 4: FECHA Y HORA ----------
    case 3:
      display.setTextSize(1);
      display.setCursor(0, 0);
      display.print("FECHA / HORA");
      display.drawLine(0, 14, 127, 14, SSD1306_WHITE);

      display.setTextSize(2);
      display.setCursor(0, 20);

      if (now.hour() < 10) display.print("0");
      display.print(now.hour());
      display.print(":");
      if (now.minute() < 10) display.print("0");
      display.print(now.minute());

      display.setTextSize(1);
      display.setCursor(0, 45);
      display.print(now.day());
      display.print("/");
      display.print(now.month());
      display.print("/");
      display.print(now.year());
      break;
  }

  display.display();
}

// ---------- SETUP ----------
void setup() {
  Serial.begin(115200);

  connectWiFi();
  Serial.print("IP ESP32: ");
  Serial.println(WiFi.localIP());

  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(mqttCallback);
  reconnectMQTT();

  Wire.begin(SDA_PIN, SCL_PIN);

  if (bmp.begin(0x76) || bmp.begin(0x77)) {
    bmpOk = true;
    Serial.println("BMP280 listo");
  } else {
    Serial.println("BMP280 no encontrado");
  }

  if (!rtc.begin()) {
    Serial.println("RTC DS1307 no encontrado");
  } else {
    Serial.println("RTC DS1307 listo");
  }

  if (!rtc.isrunning()) {
    Serial.println("RTC parado, ajustando hora...");
    rtc.adjust(DateTime(F(__DATE__), F(__TIME__)));
  }

  if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR)) {
    Serial.println("OLED no encontrada");
  } else {
    Serial.println("OLED inicializada");
  }

  pinMode(BOMBA_PIN, OUTPUT);
  digitalWrite(BOMBA_PIN, LOW); // bomba apagada
}

// ---------- LOOP ----------
void loop() {
  if (!client.connected()) reconnectMQTT();
  client.loop();

  if (riegoManualSolicitado) {
    riegoManualSolicitado = false;

    Serial.println("RIEGO MANUAL ACTIVADO");
    display.clearDisplay();
    display.setTextColor(SSD1306_WHITE);
    display.setTextSize(2);
    display.setCursor(0, 22);
    display.print("RIEGO");
    display.setTextSize(1);
    display.setCursor(0, 45);
    display.print("(manual)");
    display.display();

    digitalWrite(BOMBA_PIN, HIGH);
    delay(TIEMPO_RIEGO);
    digitalWrite(BOMBA_PIN, LOW);

    ultimoRiego = rtc.now().unixtime();
    Serial.println("RIEGO MANUAL COMPLETADO");
  }

  if (millis() - lastSend > 4000) {
    lastSend = millis();

    float t = bmpOk ? bmp.readTemperature() : NAN;
    float p = bmpOk ? bmp.readPressure() / 100.0F : NAN;

    int soilRaw = analogRead(SOIL_PIN);
    int soilPct = soilMoisturePercent(soilRaw);

    DateTime now = rtc.now();

    // La decisión de regar ya no se toma aquí: Node-RED evalúa la config
    // (umbral, horario) y publica "REGAR" en mqtt_topic_comando cuando toca.
    // Este ESP32 solo mide y espera ese comando (ver mqttCallback).

    updateDisplay(t, p, soilPct, soilStatus(soilPct), now);

    StaticJsonDocument<256> doc;
    doc["humedad_suelo"] = soilPct;
    doc["estado"] = soilStatus(soilPct);
    doc["temp_aire"] = t;
    doc["presion"] = p;
    doc["hora"] = String(now.hour()) + ":" + String(now.minute()) + ":" + String(now.second());
    doc["fecha"] = String(now.year()) + "-" + String(now.month()) + "-" + String(now.day());
    doc["timestamp"] = now.unixtime();

    char buffer[256];
    serializeJson(doc, buffer);

    client.publish(mqtt_topic, buffer);

    Serial.println("MQTT enviado:");
    Serial.println(buffer);
  }
}
