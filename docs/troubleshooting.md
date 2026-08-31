# Troubleshooting

Registro de los problemas de integración reales que surgieron durante el desarrollo, cómo se diagnosticaron y cómo se resolvieron. Documentado tanto para referencia futura como porque el proceso de diagnóstico es, en sí mismo, parte del valor del proyecto.

---

## 1. Sensor vendido como BME280 que en realidad era un BMP280

**Síntoma**: la librería `Adafruit_BME280` fallaba en `begin()` tanto en `0x76` como en `0x77`, pero un escáner I2C detectaba perfectamente un dispositivo respondiendo en `0x76`.

**Diagnóstico**: el hecho de que el escáner lo viera pero la librería lo rechazara descartaba un problema de cableado o alimentación — el chip estaba vivo y hablando por el bus. Eso apuntaba a que la librería estaba rechazando el dispositivo por su identificador interno. Se leyó directamente el registro de chip ID (`0xD0`) por I2C:

```cpp
Wire.beginTransmission(0x76);
Wire.write(0xD0);          // registro de chip ID
Wire.endTransmission();
Wire.requestFrom(0x76, 1);
byte chipId = Wire.read();
```

El resultado fue `0x58`. Según el datasheet de Bosch, `0x60` corresponde a un BME280 y `0x58` a un BMP280 — es decir, el módulo era un BMP280 (temperatura y presión, **sin sensor de humedad**) vendido y serigrafiado como BME280.

**Solución**: migrar a la librería `Adafruit_BMP280` y eliminar del payload el campo de humedad ambiente, que ese hardware físicamente no puede medir.

**Aprendizaje**: en módulos de bajo coste, la serigrafía no es fuente de verdad. Verificar el chip ID por I2C es un paso barato que ahorra horas de depuración achacada erróneamente al cableado.

---

## 2. Repositorio APT de InfluxData con fallo de firma GPG en Debian Bookworm / ARM64

**Síntoma**: `apt update` fallaba repetidamente con:

```
NO_PUBKEY DA61C26A0585BD3B
E: El repositorio «https://repos.influxdata.com/debian stable InRelease» no está firmado.
```

**Diagnóstico**: se verificó que la clave se descargaba correctamente (archivo de 1684 bytes, tamaño coherente para una clave GPG) y que `gnupg` estaba instalado y actualizado. Se reintentó el proceso paso a paso, separando la descarga de la conversión con `gpg --dearmor` en lugar de encadenarlo todo con pipes — el fallo persistió igualmente, descartando un error en la ejecución del comando.

Es un problema conocido y reportado por otros usuarios en esa combinación concreta de sistema (Raspberry Pi OS / Debian Bookworm sobre ARM64), no un error de configuración local.

**Solución**: abandonar la instalación vía `apt` e instalar desde el binario oficial, creando un servicio systemd propio:

```bash
curl -L -O https://download.influxdata.com/influxdb/releases/influxdb2-2.9.1_linux_arm64.tar.gz
tar xvzf influxdb2-2.9.1_linux_arm64.tar.gz
sudo cp influxdb2-2.9.1/influxd /usr/local/bin/
```

Con un usuario de sistema dedicado (`influxdb`), un directorio de datos en `/var/lib/influxdb` y una unidad systemd que apunta a `--bolt-path` y `--engine-path`. El detalle completo está en [`../platform/README.md`](../platform/README.md).

**Aprendizaje**: cuando un repositorio de terceros falla de forma reproducible en una arquitectura concreta, el binario oficial con un servicio systemd propio es una alternativa perfectamente válida y a menudo más rápida que seguir peleando con las firmas. Además obliga a entender qué hace realmente el servicio, en lugar de delegarlo ciegamente al paquete.

**Nota adicional**: el repositorio de Grafana (`apt.grafana.com`) funcionó sin problemas en el mismo sistema, lo que confirma que el fallo era específico del repositorio de InfluxData y no de la Raspberry Pi ni de la configuración de APT.

---

## 3. `rc=-2` al conectar el ESP32 al broker MQTT

**Síntoma**: el ESP32 conectaba correctamente al WiFi y obtenía IP, pero fallaba indefinidamente al conectar por MQTT con `rc=-2`.

**Diagnóstico**: en la librería `PubSubClient`, `rc=-2` significa literalmente "no se pudo establecer la conexión con el servidor" — es un fallo de red, no de autenticación (que daría `rc=4` o `rc=5`). Comparando la IP asignada al ESP32 (`192.168.1.139`) con la IP configurada del broker (`192.168.100.52`), la discrepancia era evidente: estaban en subredes distintas. La IP del broker era de una red anterior y había quedado obsoleta en el firmware.

**Solución**: actualizar `mqtt_server` a la IP real de la Raspberry Pi en la red actual.

**Aprendizaje**: distinguir entre los códigos de error de `PubSubClient` acelera mucho el diagnóstico. `-2` (fallo de red) y `5` (no autorizado) apuntan a causas completamente distintas y evitan buscar en el sitio equivocado.

---

## 4. `Invalid topic specified` al publicar desde Node-RED

**Síntoma**: al pulsar el botón de riego manual del dashboard, el nodo `mqtt out` lanzaba:

```
Error: Invalid topic specified
```

**Diagnóstico**: el nodo `mqtt out` estaba configurado con el campo *Topic* vacío, con la intención de que heredase el topic del mensaje entrante (`msg.topic`), que el nodo `button` sí estaba fijando. Sin embargo, el topic no llegaba efectivamente al nodo de salida, dejándolo sin destino válido en el momento de publicar.

**Solución**: fijar el topic (`planta_datos/comando`) directamente en la configuración del nodo `mqtt out`, en lugar de depender de que viaje dentro del mensaje.

**Aprendizaje**: cuando un valor puede definirse en el propio nodo o heredarse del mensaje, fijarlo en el nodo es más robusto y explícito, especialmente en rutas críticas como un comando de actuación física.

---

## 5. Nodo MQTT de Node-RED reconectando en bucle contra una IP obsoleta

**Síntoma**: en los logs de `journalctl` de Node-RED aparecía, cada ~45 segundos:

```
[info] [mqtt-broker:planta_datos] Connection failed to broker: ...52:1883
```

**Diagnóstico**: el nodo de configuración del broker MQTT en Node-RED conservaba la IP de una red anterior (`192.168.100.52`), heredada de un prototipo previo del proyecto. Node-RED reintentaba conectarse indefinidamente sin éxito.

**Solución**: editar el nodo de configuración del broker y apuntarlo a `localhost`, ya que Mosquitto corre en la misma Raspberry Pi que Node-RED.

**Aprendizaje**: cuando un servicio consume otro que vive en la misma máquina, `localhost` es preferible a la IP de red: elimina la dependencia de que la IP del host no cambie.

---

## 6. `The chip stopped responding` al flashear el ESP32

**Síntoma**: la subida del firmware fallaba consistentemente alrededor del 90% de la escritura:

```
A fatal error occurred: The chip stopped responding.
```

El código compilaba correctamente y la conexión inicial con el chip se establecía sin problemas.

**Diagnóstico**: que el fallo ocurriera durante la escritura y no al conectar apunta a un problema de estabilidad de la comunicación o de alimentación durante el volcado, no a un error de código ni de detección del puerto. Con todos los módulos (BMP280, OLED, RTC, relé) conectados y alimentados desde el propio ESP32, los picos de consumo durante la escritura en flash pueden provocar caídas de tensión.

**Solución / mitigaciones aplicables**:
- Reducir `upload_speed` a `115200` en `platformio.ini` (por defecto usa velocidades mucho más altas que son más sensibles a cableados largos).
- Usar un cable USB de datos corto y de calidad, conectado directamente al equipo (no a un hub).
- Desconectar temporalmente los periféricos durante el flasheo para descartar consumo excesivo.

**Aprendizaje**: en el flasheo de microcontroladores, distinguir *cuándo* falla (al conectar vs. durante la escritura) orienta el diagnóstico: lo primero suele ser puerto/bootloader, lo segundo alimentación o integridad de la señal.

---

## 7. Lectura `undefined` en el nodo de decisión de riego

**Síntoma**: el nodo de decisión mostraba en su status `humedad:undefined%`, por lo que nunca llegaba a evaluar correctamente la condición de riego.

**Diagnóstico**: el nodo estaba conectado a una salida de la función de reparto que ya había extraído un único valor numérico para alimentar un gauge del dashboard. En ese punto `msg.payload` era directamente un número (por ejemplo `74`), no el objeto completo, de modo que `msg.payload.humedad_suelo` no existía.

**Solución**: conectar el nodo de decisión directamente a la salida del nodo `json`, donde el mensaje todavía conserva el objeto completo tal como lo publica el ESP32.

**Aprendizaje**: en Node-RED es fácil perder de vista en qué punto del flujo el payload deja de ser el objeto original. Cuando un campo aparece como `undefined`, el primer sitio donde mirar es *de dónde* viene el cable, no el código de la función.

---

## 8. Riego automático duplicado entre firmware y plataforma

**Síntoma**: no llegó a manifestarse como fallo en producción, pero se detectó durante la migración de la lógica al servidor.

**Diagnóstico**: al implementar la decisión de riego en Node-RED, el firmware del ESP32 conservaba todavía su propio bloque de decisión automática (comparación de humedad, franja horaria y tiempo desde el último riego). Ambas lógicas quedaron activas en paralelo. Mientras los parámetros de ambas coincidían el comportamiento parecía correcto, pero en el momento en que se modificara el umbral desde el dashboard, el ESP32 habría seguido regando según su criterio interno, ajeno al cambio.

**Solución**: eliminar por completo el bloque de decisión del firmware, dejando únicamente la ejecución del comando recibido por MQTT. El ESP32 pasó a ser exclusivamente sensor y actuador.

**Aprendizaje**: durante una migración de responsabilidad de un componente a otro, el estado intermedio en el que ambos hacen lo mismo es especialmente traicionero: funciona, y por eso es fácil olvidarse de completar la migración. Conviene tratar la eliminación de la lógica antigua como parte de la misma tarea, no como una limpieza posterior opcional.
