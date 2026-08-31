# Firmware

Firmware del ESP32: lee sensores, los publica por MQTT y ejecuta los comandos de riego que recibe de la plataforma. No toma decisiones propias sobre cuándo regar.

## Requisitos

- [PlatformIO](https://platformio.org/) (extensión de VS Code o CLI)
- Placa: ESP32 DevKit (`board = esp32dev`)
- Framework: Arduino

## Dependencias

Declaradas en `platformio.ini`:

```ini
lib_deps =
    knolleary/PubSubClient
    bblanchon/ArduinoJson
    adafruit/Adafruit BMP280 Library
    adafruit/Adafruit Unified Sensor
    adafruit/Adafruit SSD1306
    adafruit/Adafruit GFX Library
    adafruit/RTClib
```

## Configuración previa

**1. Credenciales WiFi.** Copia la plantilla y rellénala con tus datos:

```bash
cp secrets.h.example secrets.h
```

```cpp
#define WIFI_SSID "tu_red"
#define WIFI_PASS "tu_contraseña"
```

`secrets.h` está en `.gitignore` y no debe subirse al repositorio.

**2. Dirección del broker.** En el `.ino`, ajusta `mqtt_server` a la IP de la máquina donde corre Mosquitto.

**3. Identificador del dispositivo.** Cada macetero necesita el suyo:

```cpp
#define DEVICE_ID "macetero01"
```

Es lo único que hay que cambiar para desplegar el mismo firmware en un dispositivo nuevo: a partir de ese valor se construyen los tres topics MQTT y el identificador de cliente. Dos dispositivos con el mismo `DEVICE_ID` se desconectarían mutuamente del broker.

## Compilar y flashear

```bash
pio run                  # compilar
pio run --target upload  # compilar y flashear
pio device monitor       # monitor serie (115200 baudios)
```

## Verificación tras el flasheo

Con el monitor serie abierto, la secuencia esperada al arrancar es:

```
Conectando a WiFi.....
WiFi conectado
IP ESP32: 192.168.x.x
Conectando MQTT... conectado
BMP280 listo
RTC DS1307 listo
OLED inicializada
MQTT enviado: {"device_id":"macetero01",...}
```

Si algún periférico no aparece como listo, revisar el bus I2C. La carpeta [`pruebas/`](pruebas/) contiene sketches de diagnóstico independientes (escáner I2C, verificación de chip ID, prueba de cada componente por separado) que ayudan a aislar el problema.

## Notas

- **Si falla el flasheo a mitad de la escritura** (`chip stopped responding`), reducir la velocidad con `upload_speed = 115200` en `platformio.ini`. Ver [`../docs/troubleshooting.md`](../docs/troubleshooting.md).
- **El relé se inicializa siempre en LOW** en el `setup()`, de modo que un reinicio inesperado no deja la bomba encendida.
- **El riego es no bloqueante**: el dispositivo sigue publicando y atendiendo MQTT mientras la bomba está activa.
