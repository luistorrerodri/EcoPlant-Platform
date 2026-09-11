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
#include <OneWire.h>
#include <DallasTemperature.h>
#include <WiFiManager.h>
#include <time.h>
#include "secrets.h"

// ---------- PINES ----------
#define SDA_PIN 21
#define SCL_PIN 22
#define SOIL_PIN 34
#define BOMBA_PIN 27
#define DS18B20_PIN 4
// GPIO 25 y 26 reservados para un futuro caudalímetro (entrada por pulsos)

// ---------- CALIBRACIÓN SUELO ----------
// Valores por defecto de referencia (los que ya se usaban a mano) - se
// sobrescriben con los reales del dispositivo en cuanto llega el primer
// mensaje retenido de mqtt_topic_config, ver soilDryCfg/soilWetCfg.
#define SOIL_DRY_DEFAULT 2482
#define SOIL_WET_DEFAULT 905

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
const char* mqtt_topic_config = "maceteros/" DEVICE_ID "/config";

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
OneWire oneWire(DS18B20_PIN);
DallasTemperature dsSensors(&oneWire);

bool bmpOk = false;
bool ds18b20Ok = false;
bool horaSincronizada = false;

// Umbrales de humedad de este dispositivo, recibidos por MQTT desde el
// servidor (topic mqtt_topic_config, retained) segun el tipo de planta
// configurado en la app. El ESP32 no decide nada por su cuenta: solo
// aplica estos valores para calcular el estado de su propia pantalla,
// igual que ya aplica sin cuestionar la orden "REGAR". Arrancan con los
// valores de "Personalizado" como red de seguridad hasta que llega el
// primer mensaje retenido tras conectar.
float humedadMinCfg = 36;
float humedadMaxCfg = 65;

// Calibracion del sensor de humedad de suelo (raw ADC), mismo mecanismo
// que humedadMinCfg/humedadMaxCfg - el servidor la guarda y la envia por
// mqtt_topic_config, este dispositivo solo la aplica. Recalibrar ya no
// exige reflashear: se hace desde la app (pantalla "Calibrar sensor").
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
  // Formula identica a la de Node-RED (nodo "Formatear para InfluxDB",
  // funcion calcularEstado) - si se cambia el margen aqui, cambiarlo
  // tambien alli para que la pantalla y la app no diverjan. Margen
  // simetrico proporcional al rango configurado: un cactus (rango
  // estrecho) tiene margenes de SECO/EXCESO mas ajustados que un
  // helecho (rango ancho), en vez de un numero fijo igual para todos.
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
    // El servidor decide los umbrales (segun el tipo de planta elegido
    // en la app); este dispositivo solo los guarda para calcular el
    // estado de su propia pantalla, no decide nada por su cuenta.
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
  // Portal cautivo: si el ESP32 ya tiene credenciales guardadas en su
  // NVS (de un WiFi.begin() anterior, propio o de esta misma libreria),
  // se reconecta solo, sin mostrar nada. Si no las tiene (dispositivo
  // nuevo) o fallan, monta su propia red "EcoPlant-Setup" y sirve una
  // pagina de configuracion en el navegador de quien se conecte a ella
  // - todo el texto se escribe desde el movil, nunca en el propio
  // dispositivo. Sustituye por completo a WIFI_SSID/WIFI_PASS de
  // secrets.h, que ya no hacen falta.
  WiFiManager wm;
  wm.setConfigPortalTimeout(180);  // 3 min sin nadie configurando -> reintenta solo

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

void updateDisplay(float t, float p, int soilPct, float tempSuelo, String estado, DateTime now) {

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

    float tempSuelo = NAN;
    if (ds18b20Ok) {
      dsSensors.requestTemperatures();
      tempSuelo = dsSensors.getTempCByIndex(0);
      if (tempSuelo == DEVICE_DISCONNECTED_C) {
        tempSuelo = NAN;  // sensor mal conectado - no publicar -127 como si fuera un dato real
      }
    }

    DateTime now = rtc.now();

    // Mientras riega, la pantalla mantiene el aviso de RIEGO.
    if (!riegoEnCurso) {
      updateDisplay(t, p, soilPct, tempSuelo, soilStatus(soilPct), now);
    }

    StaticJsonDocument<350> doc;
    doc["device_id"] = DEVICE_ID;
    doc["humedad_suelo"] = soilPct;
    // Valor crudo del ADC, sin convertir - lo usa el backend para
    // capturar puntos de calibracion desde la app (ver POST
    // /devices/{id}/calibrate), no se muestra en la app normal.
    doc["humedad_suelo_raw"] = soilRaw;
    doc["estado"] = soilStatus(soilPct);
    doc["temp_aire"] = t;
    doc["presion"] = p;
    doc["temp_suelo"] = tempSuelo;
    doc["hora"] = String(now.hour()) + ":" + String(now.minute()) + ":" + String(now.second());
    doc["fecha"] = String(now.year()) + "-" + String(now.month()) + "-" + String(now.day());
    doc["timestamp"] = now.unixtime();

    char buffer[350];
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
