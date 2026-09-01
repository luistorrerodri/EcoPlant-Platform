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

`WiFiClientSecure` y `time.h` (NTP) forman parte del core de Arduino para ESP32 y no requieren declaración.

## Configuración previa

**1. Credenciales y certificado.** Copia la plantilla y rellénala:

```bash
cp secrets.h.example secrets.h
```

```cpp
#define WIFI_SSID "tu_red"
#define WIFI_PASS "tu_contraseña"

#define MQTT_USER "macetero01"
#define MQTT_PASS "contraseña_de_este_dispositivo_en_el_broker"

static const char CA_CERT[] PROGMEM = R"EOF(
-----BEGIN CERTIFICATE-----
...contenido de ca.crt...
-----END CERTIFICATE-----
)EOF";
```

El `CA_CERT` es el certificado de la autoridad certificadora que firmó el certificado del broker (`ca.crt` en el servidor). Con él, el dispositivo verifica que se conecta al broker legítimo. `PROGMEM` lo almacena en flash en lugar de RAM.

`secrets.h` está en `.gitignore` y no debe subirse al repositorio.

**2. Dirección del broker.** En el `.ino`, ajusta `mqtt_server`. Debe coincidir **exactamente** con una de las entradas del SAN del certificado del servidor, o el handshake TLS fallará por validación de nombre.

**3. Identificador del dispositivo.** Cada macetero necesita el suyo:

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
OLED inicializada
Conectando a WiFi.....
WiFi conectado
IP ESP32: 192.168.x.x
Sincronizando hora por NTP
Hora NTP: ...
RTC actualizado desde NTP
Conectando MQTT (TLS)... conectado
MQTT enviado: {"device_id":"macetero01",...}
Heap libre: 201004 | minimo historico: 191820
```

El orden es deliberado: los periféricos se inicializan **antes** que la red, de modo que un fallo de conectividad no impide que el dispositivo siga midiendo y mostrando datos en local.

Si algún periférico no aparece como listo, revisar el bus I2C. La carpeta [`pruebas/`](pruebas/) contiene sketches de diagnóstico independientes (escáner I2C, verificación de chip ID, prueba de cada componente por separado) que ayudan a aislar el problema.

## Diagnóstico de errores de conexión

Los códigos de `PubSubClient` distinguen la causa:

| Código | Significado | Dónde mirar |
|---|---|---|
| `rc=-2` | Fallo de red o de handshake TLS | IP, puerto, certificado, hora del dispositivo |
| `rc=4` | Credenciales mal formadas | `MQTT_USER` / `MQTT_PASS` |
| `rc=5` | No autorizado | Usuario inexistente o contraseña incorrecta en el broker |

Cuando el fallo es de TLS, la librería imprime además un código de mbedTLS. El más habitual es `-9984` (`X509 - Certificate verification failed`), que agrupa varias causas. Conviene descartarlas por orden:

1. **Fecha del dispositivo**: TLS valida la vigencia del certificado. Si NTP falló y el RTC está desajustado, la verificación falla.
2. **Cadena de firma**: comprobar en el servidor con `openssl verify -CAfile ca.crt server.crt`.
3. **Coincidencia de nombre**: la dirección usada en `mqtt_server` debe figurar en el SAN del certificado, y como entrada de tipo DNS — mbedTLS no evalúa las entradas de tipo `iPAddress`. Ver [`../docs/troubleshooting.md`](../docs/troubleshooting.md).

## Consumo de recursos

Con TLS habilitado, sobre un ESP32 DevKit:

| Recurso | Uso | Notas |
|---|---|---|
| RAM estática | ~14 % | — |
| Flash | ~73 % | mbedTLS ocupa una parte considerable |
| Heap en ejecución | ~200 KB libres | Mínimo observado: ~190 KB durante el handshake |

El margen de heap es amplio. La flash, en cambio, condiciona el trabajo futuro: habilitar OTA requiere espacio para dos imágenes de firmware, lo que obligará a ajustar el esquema de particiones (`board_build.partitions` en `platformio.ini`).

El firmware imprime el heap libre y su mínimo histórico en cada publicación. El mínimo es el dato relevante, porque captura el pico de consumo del handshake TLS aunque ya haya pasado.

## Notas

- **Si falla el flasheo a mitad de la escritura** (`chip stopped responding`), reducir la velocidad con `upload_speed = 115200` en `platformio.ini`.
- **El relé se inicializa en LOW como primera instrucción** del `setup()`, de modo que un reinicio inesperado nunca deja la bomba encendida.
- **El riego es no bloqueante**: el dispositivo sigue publicando y atendiendo MQTT mientras la bomba está activa. Una orden que llegue durante un riego en curso se descarta en lugar de encolarse.
- **Tope de seguridad**: la duración efectiva del riego se acota a un máximo absoluto (`TIEMPO_RIEGO_MAX`), de modo que un valor de configuración erróneo no puede dejar la bomba encendida indefinidamente.
- **GPIO 25 y 26 están reservados** para un futuro caudalímetro por pulsos.
