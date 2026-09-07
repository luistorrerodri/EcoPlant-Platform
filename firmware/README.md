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
    paulstoffregen/OneWire
    milesburton/DallasTemperature
    tzapu/WiFiManager
```

`WiFiClientSecure` y `time.h` (NTP) forman parte del core de Arduino para ESP32 y no requieren declaración.

## Configuración previa

**1. Credenciales y certificados.** Copia la plantilla y rellénala:

```bash
cp secrets.h.example secrets.h
```

```cpp
static const char CA_CERT[] PROGMEM = R"EOF(
-----BEGIN CERTIFICATE-----
...contenido de ca.crt...
-----END CERTIFICATE-----
)EOF";

static const char CLIENT_CERT[] PROGMEM = R"EOF(
-----BEGIN CERTIFICATE-----
...contenido de macetero01.crt...
-----END CERTIFICATE-----
)EOF";

static const char CLIENT_KEY[] PROGMEM = R"EOF(
-----BEGIN PRIVATE KEY-----
...contenido de macetero01.key...
-----END PRIVATE KEY-----
)EOF";
```

El `CA_CERT` es el certificado de la autoridad certificadora que firmó el certificado del broker (`ca.crt` en el servidor): con él, el dispositivo verifica que se conecta al broker legítimo. `CLIENT_CERT`/`CLIENT_KEY` son el certificado de cliente de **este** dispositivo (CN = su `DEVICE_ID`), firmado por la misma CA: con ellos, el dispositivo demuestra su propia identidad al broker en el handshake TLS — es autenticación **mutua** (mTLS), y sustituye por completo al usuario/contraseña que se usaba antes. `PROGMEM` almacena los tres en flash en lugar de RAM.

Generar el certificado de cliente de un dispositivo nuevo es responsabilidad de la plataforma, no del firmware — ver "Certificados de cliente (mTLS)" en [`../platform/README.md`](../platform/README.md).

`secrets.h` está en `.gitignore` y no debe subirse al repositorio.

**2. WiFi: portal cautivo, no credenciales en el código.** El firmware ya no lleva `WIFI_SSID`/`WIFI_PASS` en ningún archivo. Al arrancar, `connectWiFi()` usa [WiFiManager](https://github.com/tzapu/WiFiManager):

- Si el ESP32 ya tiene credenciales guardadas en su NVS (de un `WiFi.begin()` anterior, propio o de esta misma librería), se reconecta solo, sin mostrar nada.
- Si no las tiene (dispositivo nuevo de fábrica) o la conexión falla, monta su propia red WiFi `EcoPlant-Setup` y sirve una página de configuración. Quien reciba el macetero se conecta a esa red desde su móvil, elige su WiFi real de la lista y escribe la contraseña — todo desde el navegador del móvil, sin tocar el dispositivo ni el firmware. El macetero se reinicia ya conectado.
- El portal se cierra solo a los 3 minutos (`setConfigPortalTimeout(180)`) si nadie lo completa, y el dispositivo reintenta.

Esto es lo que permite dar un macetero a alguien sin acceso al router (p. ej. un familiar) sin tener que reflashear nada.

**3. Dirección del broker.** En el `.ino`, ajusta `mqtt_server`. Debe coincidir **exactamente** con una de las entradas del SAN del certificado del servidor, o el handshake TLS fallará por validación de nombre.

**4. Identificador del dispositivo.** Cada macetero necesita el suyo:

```cpp
#define DEVICE_ID "macetero01"
```

Es lo único que hay que cambiar para desplegar el mismo firmware en un dispositivo nuevo: a partir de ese valor se construyen los tres topics MQTT y el identificador de cliente. Dos dispositivos con el mismo `DEVICE_ID` se desconectarían mutuamente del broker.

Cada dispositivo necesita además su propio usuario y su bloque de ACL en el broker (ver [`../platform/README.md`](../platform/README.md)).

## Compilar y flashear

```bash
pio run                  # compilar
pio run --target upload  # compilar y flashear
pio device monitor       # monitor serie (115200 baudios)
```

## Verificación tras el flasheo

Con el monitor serie abierto, la secuencia esperada al arrancar es:

```
BMP280 listo
RTC DS1307 listo
DS18B20 listo
OLED inicializada
Conectando a WiFi (o abriendo portal EcoPlant-Setup si hace falta)...
WiFi conectado
IP ESP32: 192.168.x.x
Sincronizando hora por NTP
Hora NTP: ...
RTC actualizado desde NTP
Conectando MQTT (mTLS)... conectado
MQTT enviado: {"device_id":"macetero01",...}
Heap libre: 201004 | minimo historico: 191820
```

El orden es deliberado: los periféricos se inicializan **antes** que la red, de modo que un fallo de conectividad no impide que el dispositivo siga midiendo y mostrando datos en local.

Si algún periférico I2C (BMP280, RTC, OLED) no aparece como listo, revisar el bus I2C. La carpeta [`pruebas/`](pruebas/) contiene sketches de diagnóstico independientes (escáner I2C, verificación de chip ID, prueba de cada componente por separado) que ayudan a aislar el problema.

Si aparece "DS18B20 no encontrado", revisar la resistencia de pull-up (4.7kΩ entre el pin de datos, GPIO4, y 3.3V) — es el fallo de cableado más habitual con este sensor.

## Diagnóstico de errores de conexión

Los códigos de `PubSubClient` distinguen la causa:

| Código | Significado | Dónde mirar |
|---|---|---|
| `rc=-2` | Fallo de red o de handshake TLS (incluye certificado de cliente rechazado) | IP, puerto, certificado, hora del dispositivo |
| `rc=5` | No autorizado | El CN del certificado de cliente no tiene entrada en el ACL del broker |

Cuando el fallo es de TLS, la librería imprime además un código de mbedTLS. El más habitual es `-9984` (`X509 - Certificate verification failed`), que agrupa varias causas. Conviene descartarlas por orden:

1. **Fecha del dispositivo**: TLS valida la vigencia del certificado. Si NTP falló y el RTC está desajustado, la verificación falla.
2. **Cadena de firma del servidor**: comprobar en el servidor con `openssl verify -CAfile ca.crt server.crt`.
3. **Cadena de firma del cliente**: comprobar que `CLIENT_CERT` en `secrets.h` corresponde de verdad al certificado firmado por la CA para este `DEVICE_ID` (`openssl verify -CAfile ca.crt macetero01.crt`), y que `CLIENT_KEY` es su clave privada correspondiente, no la de otro dispositivo.
4. **Coincidencia de nombre del servidor**: la dirección usada en `mqtt_server` debe figurar en el SAN del certificado del broker, y como entrada de tipo DNS — mbedTLS no evalúa las entradas de tipo `iPAddress`. Ver [`../docs/troubleshooting.md`](../docs/troubleshooting.md).

## Consumo de recursos

Con TLS y WiFiManager habilitados, sobre un ESP32 DevKit (build real, `pio run`: 47.836 / 327.680 bytes RAM, 1.078.057 / 1.310.720 bytes flash):

| Recurso | Uso | Notas |
|---|---|---|
| RAM estática | ~14.6 % | — |
| Flash | ~82.2 % | mbedTLS ya ocupaba una parte considerable; WiFiManager añade `WebServer`/`DNSServer`/`ESPmDNS` como dependencias transitivas |
| Heap en ejecución | ~200 KB libres | Mínimo observado: ~190 KB durante el handshake |

El margen de heap es amplio. La flash es la más ajustada: quedan ~227 KB libres, y habilitar OTA en el futuro requeriría espacio para dos imágenes de firmware, lo que obligará a ajustar el esquema de particiones (`board_build.partitions` en `platformio.ini`) o a liberar espacio en otro sitio primero.

El firmware imprime el heap libre y su mínimo histórico en cada publicación. El mínimo es el dato relevante, porque captura el pico de consumo del handshake TLS aunque ya haya pasado.

## Notas

- **Si falla el flasheo a mitad de la escritura** (`chip stopped responding`), reducir la velocidad con `upload_speed = 115200` en `platformio.ini`.
- **El relé se inicializa en LOW como primera instrucción** del `setup()`, de modo que un reinicio inesperado nunca deja la bomba encendida.
- **El riego es no bloqueante**: el dispositivo sigue publicando y atendiendo MQTT mientras la bomba está activa. Una orden que llegue durante un riego en curso se descarta en lugar de encolarse.
- **Tope de seguridad**: la duración efectiva del riego se acota a un máximo absoluto (`TIEMPO_RIEGO_MAX`), de modo que un valor de configuración erróneo no puede dejar la bomba encendida indefinidamente.
- **GPIO 25 y 26 están reservados** para un futuro caudalímetro por pulsos.
- **DS18B20 en GPIO4**, enterrado en la tierra junto a la sonda de humedad de suelo. Necesita una resistencia de pull-up de 4.7kΩ entre el pin de datos y 3.3V — sin ella, `dsSensors.getDeviceCount()` da 0 y el firmware sigue funcionando pero sin publicar `temp_suelo`.
