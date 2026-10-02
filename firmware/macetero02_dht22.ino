// macetero02 - variante de sensores con DHT22 (sin BMP280, sin presion;
// anade humedad ambiente). Mismo esqueleto de red/seguridad/riego que
// macetero_produccion_6.ino (macetero01) sin ningun cambio de fondo -
// solo difiere la lectura de ambiente y lo que se publica/muestra de
// ello. Ver firmware/README.md para el porque de un fichero aparte en
// vez de condicionales dentro del mismo.
#include <WiFiClientSecure.h>
#include <Arduino.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <DHT.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <RTClib.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <WiFiManager.h>
#include <time.h>
#include "secrets.h"

// ---------- PINES ----------
// Cableado real de esta placa (COM4) - distinto de macetero01 a
// proposito, cada ESP32 lleva el suyo, no tienen por que coincidir.
#define SDA_PIN 21
#define SCL_PIN 22
#define SOIL_PIN 34
#define BOMBA_PIN 26
#define DHTPIN 4
#define DHTTYPE DHT22
#define DS18B20_PIN 18
// GPIO 35 reservado para un futuro sensor de nivel de deposito (ya
// cableado en esta placa, sin usar todavia - ver WATER_PIN en el
// sketch de pruebas original).
#define WATER_PIN 35

// ---------- CALIBRACIÓN SUELO ----------
#define SOIL_DRY_DEFAULT 2482
#define SOIL_WET_DEFAULT 905

// ---------- MQTT ----------
const char* mqtt_server = "192.168.1.140";
const int mqtt_port = 8883;   // MQTT sobre TLS

// Identificador único de este macetero. Es lo ÚNICO que hay que cambiar
// para desplegar el mismo firmware en un dispositivo nuevo.
#define DEVICE_ID "macetero02"

const char* mqtt_client_id = "esp32_" DEVICE_ID;
const char* mqtt_topic = "maceteros/" DEVICE_ID "/sensores";
const char* mqtt_topic_comando = "maceteros/" DEVICE_ID "/comando";
const char* mqtt_topic_estado = "maceteros/" DEVICE_ID "/estado";
const char* mqtt_topic_config = "maceteros/" DEVICE_ID "/config";

// ---------- RIEGO ----------
// Igual que macetero01: la decision de CUANDO regar vive en Node-RED,
// no aqui. El sketch de pruebas original decidia el riego el mismo
// (umbral + franja horaria fijos en el propio .ino) - eso se ha
// quitado por completo al integrarlo en la plataforma.
#define TIEMPO_RIEGO 9000       // 9 segundos, redefinible luego por tipo de planta
#define TIEMPO_RIEGO_MAX 30000  // 30 segundos, tope de seguridad absoluto

volatile bool riegoManualSolicitado = false;
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
DHT dht(DHTPIN, DHTTYPE);
RTC_DS1307 rtc;
OneWire oneWire(DS18B20_PIN);
DallasTemperature dsSensors(&oneWire);

bool ds18b20Ok = false;
bool horaSincronizada = false;

// Umbrales de humedad de este dispositivo, recibidos por MQTT desde el
// servidor - identico a macetero01, ver los comentarios de ese fichero.
float humedadMinCfg = 36;
float humedadMaxCfg = 65;
int soilDryCfg = SOIL_DRY_DEFAULT;
int soilWetCfg = SOIL_WET_DEFAULT;

// ---------- TIMING ----------
unsigned long lastSend = 0;
unsigned long ultimoRiego = 0;

// ---------- FUNCIONES ----------
int soilMoisturePercent(int raw) {
  raw = constrain(raw, soilWetCfg, soilDryCfg);
  return map(raw, soilDryCfg, soilWetCfg, 0, 100);
}

String soilStatus(int soilPct) {
  // Identica a macetero01 y al nodo "Formatear para InfluxDB" de
  // Node-RED - si se cambia aqui, cambiarla tambien alli.
  float margen = (humedadMaxCfg - humedadMinCfg) * 0.4;
  if (soilPct < humedadMinCfg - margen) return "SECO";
  if (soilPct < humedadMinCfg) return "NECESITA_RIEGO";
  if (soilPct <= humedadMaxCfg) return "OK";
  if (soilPct <= humedadMaxCfg + margen) return "HUMEDO";
  return "EXCESO_AGUA";
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String mensaje;
  for (unsigned int i = 0; i < length; i++) {
    mensaje += (char)payload[i];
  }

  Serial.print("Mensaje recibido en ");
  Serial.print(topic);
  Serial.print(": ");
  Serial.println(mensaje);

  String topicStr(topic);

  if (topicStr == mqtt_topic_comando) {
    if (mensaje == "REGAR") {
      riegoManualSolicitado = true;
    }
    return;
  }

  if (topicStr == mqtt_topic_config) {
    StaticJsonDocument<192> cfgDoc;
    DeserializationError err = deserializeJson(cfgDoc, mensaje);
    if (err) {
      Serial.print("Config recibida invalida: ");
      Serial.println(err.c_str());
      return;
    }
    if (cfgDoc.containsKey("humedadMin")) humedadMinCfg = cfgDoc["humedadMin"];
    if (cfgDoc.containsKey("humedadMax")) humedadMaxCfg = cfgDoc["humedadMax"];
    if (cfgDoc.containsKey("soilDry")) soilDryCfg = cfgDoc["soilDry"];
    if (cfgDoc.containsKey("soilWet")) soilWetCfg = cfgDoc["soilWet"];
    Serial.print("Config aplicada: humedadMin=");
    Serial.print(humedadMinCfg);
    Serial.print(" humedadMax=");
    Serial.print(humedadMaxCfg);
    Serial.print(" soilDry=");
    Serial.print(soilDryCfg);
    Serial.print(" soilWet=");
    Serial.println(soilWetCfg);
  }
}

void connectWiFi() {
  WiFiManager wm;
  wm.setConfigPortalTimeout(180);

  Serial.println("Conectando a WiFi (o abriendo portal EcoPlant-Setup si hace falta)...");
  bool conectado = wm.autoConnect("EcoPlant-Setup");

  if (!conectado) {
    Serial.println("No se pudo conectar ni configurar a tiempo, reiniciando...");
    ESP.restart();
  }

  Serial.println("WiFi conectado");
}

void reconnectMQTT() {
  while (!client.connected()) {
    Serial.print("Conectando MQTT (mTLS)...");

    bool conectado = client.connect(
      mqtt_client_id,
      mqtt_topic_estado,
      1,
      true,
      "{\"online\":false}"
    );

    if (conectado) {
      Serial.println(" conectado");
      client.subscribe(mqtt_topic_comando);
      client.subscribe(mqtt_topic_config);
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

    rtc.adjust(DateTime(
      timeinfo.tm_year + 1900, timeinfo.tm_mon + 1, timeinfo.tm_mday,
      timeinfo.tm_hour, timeinfo.tm_min, timeinfo.tm_sec
    ));
    Serial.println("RTC actualizado desde NTP");
  } else {
    Serial.println();
    Serial.println("NTP fallo: se mantiene la hora del RTC");
    if (!rtc.isrunning()) {
      Serial.println("AVISO: RTC parado y sin NTP. TLS puede fallar por fecha invalida.");
    }
  }
}

// t/h = temperatura/humedad de ambiente (DHT22, pueden ser NAN si falla
// la lectura - no hay presion en esta placa, a diferencia de macetero01.
void updateDisplay(float t, float h, int soilPct, float tempSuelo, String estado, DateTime now) {

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
      if (isnan(t)) {
        display.print("T: --");
      } else {
        display.print(t, 1);
        display.print(" C");
      }

      display.setTextSize(1);
      display.setCursor(0, 42);
      display.print("Humedad: ");
      if (isnan(h)) {
        display.print("--");
      } else {
        display.print(h, 0);
        display.print(" %");
      }
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

      display.setTextSize(1);
      display.setCursor(0, 45);
      display.print("Temp: ");
      if (isnan(tempSuelo)) {
        display.print("--");
      } else {
        display.print(tempSuelo, 1);
        display.print(" C");
      }
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

  pinMode(BOMBA_PIN, OUTPUT);
  digitalWrite(BOMBA_PIN, LOW);

  Wire.begin(SDA_PIN, SCL_PIN);

  dht.begin();
  // El DHT no tiene un begin() que confirme presencia como el BMP280 -
  // se hace una lectura de prueba solo para dejar constancia en el
  // log, el loop() ya tolera NAN en cada ciclo independientemente.
  delay(2000);  // el DHT22 necesita ~2s desde el arranque antes de la primera lectura fiable
  float testT = dht.readTemperature();
  if (isnan(testT)) {
    Serial.println("DHT22: sin lectura valida en el arranque (se seguira intentando cada ciclo)");
  } else {
    Serial.println("DHT22 listo");
  }

  if (!rtc.begin()) {
    Serial.println("RTC DS1307 no encontrado");
  } else {
    Serial.println("RTC DS1307 listo");
  }

  dsSensors.begin();
  if (dsSensors.getDeviceCount() > 0) {
    ds18b20Ok = true;
    Serial.println("DS18B20 listo");
  } else {
    Serial.println("DS18B20 no encontrado");
  }

  if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR)) {
    Serial.println("OLED no encontrada");
  } else {
    Serial.println("OLED inicializada");
    display.clearDisplay();
    display.setTextColor(SSD1306_WHITE);
    display.setTextSize(1);
    display.setCursor(0, 28);
    display.print("Conectando...");
    display.display();
  }

  connectWiFi();
  Serial.print("IP ESP32: ");
  Serial.println(WiFi.localIP());

  sincronizarHora();

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

    char ackBuffer[128];
    serializeJson(ack, ackBuffer);
    client.publish(mqtt_topic_estado, ackBuffer);

    Serial.print("RIEGO COMPLETADO, confirmacion enviada: ");
    Serial.println(ackBuffer);
  }

  // ---- Ciclo de medida y publicación ----
  if (millis() - lastSend > 4000) {
    lastSend = millis();

    float t = dht.readTemperature();
    float h = dht.readHumidity();

    int soilRaw = analogRead(SOIL_PIN);
    int soilPct = soilMoisturePercent(soilRaw);

    float tempSuelo = NAN;
    if (ds18b20Ok) {
      dsSensors.requestTemperatures();
      tempSuelo = dsSensors.getTempCByIndex(0);
      if (tempSuelo == DEVICE_DISCONNECTED_C) {
        tempSuelo = NAN;
      }
    }

    DateTime now = rtc.now();

    if (!riegoEnCurso) {
      updateDisplay(t, h, soilPct, tempSuelo, soilStatus(soilPct), now);
    }

    StaticJsonDocument<350> doc;
    doc["device_id"] = DEVICE_ID;
    doc["humedad_suelo"] = soilPct;
    doc["humedad_suelo_raw"] = soilRaw;
    doc["estado"] = soilStatus(soilPct);
    doc["temp_aire"] = t;
    // Sin "presion": esta placa no tiene BMP280/BME280, no se publica
    // un campo que no existe de verdad - ni aqui ni con un 0 falso.
    doc["humedad_ambiente"] = h;
    doc["temp_suelo"] = tempSuelo;
    doc["hora"] = String(now.hour()) + ":" + String(now.minute()) + ":" + String(now.second());
    doc["fecha"] = String(now.year()) + "-" + String(now.month()) + "-" + String(now.day());
    doc["timestamp"] = now.unixtime();

    char buffer[350];
    serializeJson(doc, buffer);

    client.publish(mqtt_topic, buffer);

    Serial.println("MQTT enviado:");
    Serial.println(buffer);

    Serial.print("Heap libre: ");
    Serial.print(ESP.getFreeHeap());
    Serial.print(" | minimo historico: ");
    Serial.println(ESP.getMinFreeHeap());
  }
}
