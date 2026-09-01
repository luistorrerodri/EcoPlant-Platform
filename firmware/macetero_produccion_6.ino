#include <WiFiClientSecure.h>
#include <Arduino.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BMP280.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <RTClib.h>
#include <time.h>
#include "secrets.h"

// ---------- PINES ----------
#define SDA_PIN 21
#define SCL_PIN 22
#define SOIL_PIN 34
#define BOMBA_PIN 27
// GPIO 25 y 26 reservados para un futuro caudalímetro (entrada por pulsos)

// ---------- CALIBRACIÓN SUELO ----------
#define SOIL_DRY 2482
#define SOIL_WET 905

// ---------- WIFI (definido en secrets.h) ----------
const char* ssid = WIFI_SSID;
const char* pass = WIFI_PASS;

// ---------- MQTT ----------
const char* mqtt_server = "192.168.1.140";
const int mqtt_port = 8883;   // MQTT sobre TLS

// Identificador único de este macetero. Es lo ÚNICO que hay que cambiar
// para desplegar el mismo firmware en un dispositivo nuevo.
#define DEVICE_ID "macetero01"

const char* mqtt_client_id = "esp32_" DEVICE_ID;
const char* mqtt_topic = "maceteros/" DEVICE_ID "/sensores";
const char* mqtt_topic_comando = "maceteros/" DEVICE_ID "/comando";
const char* mqtt_topic_estado = "maceteros/" DEVICE_ID "/estado";

// ---------- RIEGO ----------
// Duración del pulso de riego. El umbral y la franja horaria no se
// gestionan aquí: la decisión de CUÁNDO regar vive en Node-RED.
#define TIEMPO_RIEGO 9000       // 9 segundos

// Tope de seguridad: la bomba nunca debe estar encendida más que esto,
// pase lo que pase con la lógica de temporización.
#define TIEMPO_RIEGO_MAX 30000  // 30 segundos

volatile bool riegoManualSolicitado = false;

// Estado del riego no bloqueante
bool riegoEnCurso = false;
unsigned long riegoInicioMs = 0;

// ---------- OLED ----------
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1
#define OLED_ADDR 0x3C

unsigned long lastScreenChange = 0;
int screenIndex = 0;

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// ---------- OBJETOS ----------
WiFiClientSecure espClient;
PubSubClient client(espClient);
Adafruit_BMP280 bmp;
RTC_DS1307 rtc;

bool bmpOk = false;
bool horaSincronizada = false;

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
    Serial.print("Conectando MQTT (mTLS)...");

    // La identidad ya no viaja como usuario/contraseña: el broker la
    // deriva del CN del certificado de cliente (ver setup()). El payload
    // del LWT lo publica el broker automáticamente si este cliente se
    // desconecta sin avisar. Retained para que un suscriptor que llegue
    // después conozca el estado actual del dispositivo.
    bool conectado = client.connect(
      mqtt_client_id,
      mqtt_topic_estado,   // will topic
      1,                   // will QoS
      true,                // will retained
      "{\"online\":false}" // will payload
    );

    if (conectado) {
      Serial.println(" conectado");
      client.subscribe(mqtt_topic_comando);
      client.publish(mqtt_topic_estado, "{\"online\":true}", true);
    } else {
      int rc = client.state();
      Serial.print(" fallo rc=");
      Serial.print(rc);
      if (rc == 5) {
        Serial.println(" (certificado de cliente no autorizado: revisar CN y ACL)");
      } else if (rc == -2) {
        Serial.println(" (fallo de red o handshake TLS: revisar IP, certificado y hora)");
      } else {
        Serial.println();
      }
      delay(2000);
    }
  }
}

void sincronizarHora() {
  // Zona horaria de España peninsular, con cambio de horario automático.
  configTzTime("CET-1CEST,M3.5.0/2,M10.5.0/3", "pool.ntp.org", "time.nist.gov");

  Serial.print("Sincronizando hora por NTP");
  struct tm timeinfo;
  int intentos = 0;
  while (!getLocalTime(&timeinfo) && intentos < 20) {
    Serial.print(".");
    delay(500);
    intentos++;
  }

  if (getLocalTime(&timeinfo)) {
    horaSincronizada = true;
    Serial.println();
    Serial.print("Hora NTP: ");
    Serial.print(asctime(&timeinfo));

    // El RTC queda como respaldo para cuando no haya red.
    rtc.adjust(DateTime(
      timeinfo.tm_year + 1900, timeinfo.tm_mon + 1, timeinfo.tm_mday,
      timeinfo.tm_hour, timeinfo.tm_min, timeinfo.tm_sec
    ));
    Serial.println("RTC actualizado desde NTP");
  } else {
    Serial.println();
    Serial.println("NTP fallo: se mantiene la hora del RTC");
    // TLS valida la fecha de los certificados: sin hora fiable el
    // handshake puede fallar con un error poco descriptivo.
    if (!rtc.isrunning()) {
      Serial.println("AVISO: RTC parado y sin NTP. TLS puede fallar por fecha invalida.");
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
  delay(200);

  // 1) Hardware primero: si la red falla, el dispositivo sigue siendo
  //    utilizable en local (pantalla y sensores operativos).
  pinMode(BOMBA_PIN, OUTPUT);
  digitalWrite(BOMBA_PIN, LOW);   // la bomba nunca arranca sola tras un reinicio

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

  if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR)) {
    Serial.println("OLED no encontrada");
  } else {
    Serial.println("OLED inicializada");
  }

  // 2) Red
  connectWiFi();
  Serial.print("IP ESP32: ");
  Serial.println(WiFi.localIP());

  // 3) Hora antes que TLS: el handshake valida la vigencia del certificado.
  sincronizarHora();

  // 4) TLS mutuo y MQTT: CA_CERT valida al broker, CLIENT_CERT/CLIENT_KEY
  //    es como este dispositivo se identifica ante él (ver secrets.h).
  espClient.setCACert(CA_CERT);
  espClient.setCertificate(CLIENT_CERT);
  espClient.setPrivateKey(CLIENT_KEY);
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(mqttCallback);
  reconnectMQTT();
}

// ---------- LOOP ----------
void loop() {
  if (!client.connected()) reconnectMQTT();
  client.loop();

  // ---- Arranque del riego ----
  // Una orden nueva se ignora si ya hay un riego en curso.
  if (riegoManualSolicitado) {
    riegoManualSolicitado = false;

    if (!riegoEnCurso) {
      riegoEnCurso = true;
      riegoInicioMs = millis();
      digitalWrite(BOMBA_PIN, HIGH);

      Serial.println("RIEGO ACTIVADO");
      display.clearDisplay();
      display.setTextColor(SSD1306_WHITE);
      display.setTextSize(2);
      display.setCursor(0, 22);
      display.print("RIEGO");
      display.display();
    } else {
      Serial.println("Orden ignorada: riego ya en curso");
    }
  }

  // ---- Parada del riego ----
  // Se evalúa en cada vuelta del loop, sin bloquear. El tope de seguridad
  // garantiza el apagado aunque TIEMPO_RIEGO tuviera un valor erróneo.
  unsigned long limiteRiego = min((unsigned long)TIEMPO_RIEGO, (unsigned long)TIEMPO_RIEGO_MAX);

  if (riegoEnCurso && (millis() - riegoInicioMs >= limiteRiego)) {
    digitalWrite(BOMBA_PIN, LOW);
    unsigned long duracionReal = millis() - riegoInicioMs;
    riegoEnCurso = false;

    ultimoRiego = rtc.now().unixtime();

    StaticJsonDocument<128> ack;
    ack["evento"] = "riego_completado";
    ack["duracion_ms"] = duracionReal;
    ack["timestamp"] = ultimoRiego;
    // Cuando se instale el caudalímetro, añadir aquí "volumen_ml"
    // con la medida real en lugar de derivarla del tiempo.

    char ackBuffer[128];
    serializeJson(ack, ackBuffer);
    client.publish(mqtt_topic_estado, ackBuffer);

    Serial.print("RIEGO COMPLETADO, confirmacion enviada: ");
    Serial.println(ackBuffer);
  }

  // ---- Ciclo de medida y publicación ----
  if (millis() - lastSend > 4000) {
    lastSend = millis();

    float t = bmpOk ? bmp.readTemperature() : NAN;
    float p = bmpOk ? bmp.readPressure() / 100.0F : NAN;

    int soilRaw = analogRead(SOIL_PIN);
    int soilPct = soilMoisturePercent(soilRaw);

    DateTime now = rtc.now();

    // Mientras riega, la pantalla mantiene el aviso de RIEGO.
    if (!riegoEnCurso) {
      updateDisplay(t, p, soilPct, soilStatus(soilPct), now);
    }

    StaticJsonDocument<256> doc;
    doc["device_id"] = DEVICE_ID;
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

    // Vigilancia de memoria: con TLS el pico de consumo se produce en el
    // handshake, así que el mínimo histórico es más informativo que el actual.
    Serial.print("Heap libre: ");
    Serial.print(ESP.getFreeHeap());
    Serial.print(" | minimo historico: ");
    Serial.println(ESP.getMinFreeHeap());
  }
}
