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

## 8. Series fragmentadas en InfluxDB por modelar un valor cambiante como tag

**Síntoma**: en Grafana, la gráfica de humedad de suelo aparecía cortada en múltiples segmentos de colores distintos, en lugar de como una línea continua. La leyenda mostraba entradas separadas del tipo `humedad_suelo {device_id="macetero01", estado="SECO"}`, `... estado="HUMEDO"`, etc.

**Diagnóstico**: `estado` se había modelado como **tag** en InfluxDB. En una base de datos de series temporales, cada combinación única de tags define una serie independiente, de modo que un valor que cambia con frecuencia genera tantas series como valores distintos pueda tomar. Cada vez que la planta pasaba de `SECO` a `HUMEDO`, la primera serie dejaba de recibir puntos y arrancaba otra: de ahí las líneas cortadas.

**Solución**: mover `estado` de tag a field, dejando `device_id` como único tag. Además de resolver la fragmentación, es lo correcto conceptualmente: `estado` es un valor derivado de `humedad_suelo` mediante umbrales, no un metadato del dispositivo.

**Efecto secundario durante la migración**: al aplicar el cambio, la consulta en el Data Explorer dejó de devolver datos con el error `unsupported input type for mean aggregate: string`. La causa era que `estado`, ahora field de tipo texto, estaba incluido en una consulta cuya función de agregación era `mean` — no se puede promediar una cadena. Al deseleccionarlo de los campos consultados, la consulta volvió a funcionar.

Adicionalmente, los datos anteriores al cambio conservan el tag antiguo, por lo que durante un tiempo conviven ambos esquemas en el mismo bucket. Filtrar por `estado` en el Data Explorer devolvía únicamente los datos históricos, dando la falsa impresión de que la ingesta se había detenido.

**Aprendizaje**: la regla práctica es sencilla — si vas a **filtrar o agrupar** por un valor y es estable, es un tag; si vas a **graficarlo o agregarlo** y cambia con cada lectura, es un field. Modelar mal esta distinción no da un error inmediato, pero degrada las consultas y, a escala, el rendimiento por explosión de cardinalidad.

---

## 9. Riegos en ráfaga al introducir la confirmación del dispositivo

**Síntoma**: al cambiar la lógica para que el contador de "último riego" dependiera de la confirmación del dispositivo en lugar de la orden enviada, el sistema empezó a regar de forma repetida cada pocos segundos.

**Diagnóstico**: dos causas encadenadas.

La primera fue de secuencia: el cambio se aplicó en la plataforma **antes** de flashear el firmware que envía las confirmaciones. Sin confirmaciones, el registro de último riego permanecía a cero, la condición "han pasado más de 24 h" se cumplía siempre, y cada lectura de sensores disparaba una orden nueva.

La segunda persistió incluso con el firmware correcto: como el riego en el ESP32 es bloqueante (`delay()` de 9 segundos), durante ese tiempo el dispositivo no procesa MQTT. Las órdenes que la plataforma seguía emitiendo se acumulaban en el broker y se ejecutaban en cadena al terminar el primer riego. La confirmación llegaba demasiado tarde para frenar las que ya estaban en camino.

**Solución**: añadir en la plataforma una ventana mínima de 60 segundos entre órdenes consecutivas al mismo dispositivo, registrada en el momento de emitir el comando y evaluada antes de emitir el siguiente. A diferencia de la confirmación, esta guarda protege aunque el dispositivo no responda nunca.

**Aprendizaje**: en un sistema distribuido, condicionar una acción a la respuesta de otro componente introduce una ventana temporal en la que la acción puede repetirse. Hace falta una protección local (idempotencia, ventana de bloqueo o límite de reintentos) que no dependa de que la otra parte responda. Y en migraciones que afectan a dos componentes a la vez, el orden importa: el que emite debe actualizarse después del que responde, no antes.

---

## 10. Node.js rechaza un certificado que OpenSSL acepta (SAN ausente)

**Síntoma**: tras habilitar TLS en el broker, `mosquitto_sub` conectaba correctamente por el puerto 8883, pero el nodo MQTT de Node-RED se quedaba indefinidamente en estado "conectando", con el log repitiendo `Connection failed to broker: mqtts://...` sin más detalle.

**Diagnóstico**: el certificado del servidor se había generado indicando la dirección del broker únicamente en el campo **Common Name (CN)**. OpenSSL, y por tanto las herramientas de línea de comandos de Mosquitto, aceptan el CN como identificador del servidor. Node.js, en cambio, sigue la recomendación de RFC 6125 e **ignora el CN por completo**, exigiendo que la dirección figure en la extensión **Subject Alternative Name (SAN)**.

Se confirmó con:

```bash
openssl x509 -in server.crt -noout -text | grep -A1 "Subject Alternative Name"
```

que no devolvía nada: el certificado carecía de SAN.

**Solución**: regenerar el certificado del servidor incluyendo la extensión, mediante un archivo de extensiones pasado con `-extfile`. La CA no se toca, de modo que los dispositivos que ya llevan el `ca.crt` embebido no requieren reflasheo.

**Aprendizaje**: el CN como identificador de servidor está obsoleto desde hace años. Cualquier certificado nuevo debe llevar SAN, incluso en entornos internos con CA propia.

---

## 11. mbedTLS (ESP32) rechaza un certificado que Node.js acepta (SAN por IP)

**Síntoma**: tras corregir el problema anterior, Node-RED conectaba correctamente pero el ESP32 pasó a fallar de forma sistemática con:

```
(-9984) X509 - Certificate verification failed, e.g. CRL, CA or signature check failed
```

**Diagnóstico**: el caso simétrico al anterior. El SAN se había generado con la entrada `IP Address:192.168.1.140`, que es lo formalmente correcto para una dirección IP. Node.js interpreta correctamente las entradas de tipo `iPAddress`. La implementación de mbedTLS que utiliza el ESP32, en cambio, compara el nombre solicitado contra las entradas de tipo **dNSName**, sin evaluar las de tipo `iPAddress`, por lo que ninguna coincidía y la verificación fallaba.

**Solución**: incluir la dirección **también** como entrada DNS, aunque sea una IP:

```
subjectAltName = IP:192.168.1.140, DNS:192.168.1.140, DNS:raspberrypi, DNS:localhost
```

Las entradas se acumulan, de modo que ambos clientes encuentran una coincidencia válida con el mismo certificado.

**Aprendizaje**: dos implementaciones de TLS que cumplen el estándar pueden diferir en qué partes del certificado evalúan. En un sistema con clientes heterogéneos (un runtime de servidor y un microcontrolador), el certificado debe satisfacer a la implementación más restrictiva de todas, no a la más permisiva. Conviene verificar la conexión desde **cada** tipo de cliente antes de dar por buena una configuración TLS.

**Nota de diagnóstico**: el código `-9984` de mbedTLS agrupa varias causas distintas (firma inválida, CA desconocida, nombre no coincidente, certificado caducado). Cuando aparece, merece la pena descartar por orden: fecha del dispositivo, cadena de firma (`openssl verify -CAfile ca.crt server.crt`) y, por último, coincidencia de nombre en el SAN.

---

## 12. Riego automático duplicado entre firmware y plataforma

**Síntoma**: no llegó a manifestarse como fallo en producción, pero se detectó durante la migración de la lógica al servidor.

**Diagnóstico**: al implementar la decisión de riego en Node-RED, el firmware del ESP32 conservaba todavía su propio bloque de decisión automática (comparación de humedad, franja horaria y tiempo desde el último riego). Ambas lógicas quedaron activas en paralelo. Mientras los parámetros de ambas coincidían el comportamiento parecía correcto, pero en el momento en que se modificara el umbral desde el dashboard, el ESP32 habría seguido regando según su criterio interno, ajeno al cambio.

**Solución**: eliminar por completo el bloque de decisión del firmware, dejando únicamente la ejecución del comando recibido por MQTT. El ESP32 pasó a ser exclusivamente sensor y actuador.

**Aprendizaje**: durante una migración de responsabilidad de un componente a otro, el estado intermedio en el que ambos hacen lo mismo es especialmente traicionero: funciona, y por eso es fácil olvidarse de completar la migración. Conviene tratar la eliminación de la lógica antigua como parte de la misma tarea, no como una limpieza posterior opcional.

---

## 13. `-9984 X509 verify failed` en el ESP32 al añadir mTLS, causado por un `CA_CERT` desactualizado

**Síntoma**: al implementar autenticación mutua (certificado de cliente por dispositivo), el ESP32 dejó de conectar al broker con `(-9984) X509 - Certificate verification failed`, el mismo código genérico que agrupa varias causas (ver entrada 11). El log de Mosquitto mostraba, casi en el instante de aceptar la conexión: `OpenSSL Error[0]: error:0A000418:SSL routines::tlsv1 alert unknown ca`.

**Diagnóstico**: la sospecha inicial fue el certificado de cliente recién creado — el cambio más reciente. Se descartó en dos pasos: primero, probando el par `macetero01.crt`/`macetero01.key` directamente desde la propia Pi con `mosquitto_sub --cert ... --key ...`, que conectó sin problema, confirmando que el certificado de cliente era válido. Segundo, desactivando temporalmente `require_certificate` en el broker (de modo que el certificado de cliente dejaba de intervenir) y comprobando que el ESP32 **seguía fallando exactamente igual** — lo que descartó por completo la vía del certificado de cliente y apuntó a la verificación del certificado del *servidor*, sin relación con el trabajo de mTLS.

Con eso, el patrón del log (fallo casi inmediato, alerta `unknown ca` recibida por el broker) encajaba con que fuera el propio ESP32 quien rechazaba el certificado del broker y abortaba el handshake enviando esa alerta — es decir, el `CA_CERT` embebido en el firmware no correspondía ya al `ca.crt` real de la Pi, probablemente por haber quedado una copia de una generación de CA anterior.

**Solución**: volver a copiar el `ca.crt` actual de la Pi al `secrets.h` del firmware (archivo a archivo, sin retipear el contenido — ver la nota siguiente) y reflashear.

**Aprendizaje**: cuando un fallo de TLS aparece justo después de tocar *otra* pieza relacionada (aquí, añadir el certificado de cliente), es tentador asumir que la pieza recién tocada es la culpable. Aislar la variable — probar el certificado nuevo por separado, y luego desactivar temporalmente la función nueva para ver si el fallo persiste sin ella — evita perder tiempo depurando la parte equivocada. El código `-9984` seguía sin distinguir la causa exacta; hizo falta cruzar el log del ESP32 con el del broker (no solo mirar un lado) para saber qué certificado era el que realmente estaba fallando.

**Nota sobre copiar/pegar certificados**: retranscribir manualmente un bloque PEM (por terminal o a mano) es una fuente de errores fácil de introducir y difícil de detectar a simple vista. La forma fiable es traer el archivo real al equipo (`scp`) y copiar su contenido directamente en un editor de texto, sin que el contenido pase por una reescritura intermedia.

---

## 14. Caddy sirviendo en TLS y bloqueando todo por el filtro de `Host`

**Síntoma**: al configurar Caddy como proxy local para exponer solo `/ui` de Node-RED, dos fallos encadenados durante la puesta en marcha.

Primero, cualquier petición HTTP normal (`curl http://localhost:8080/...`) devolvía `400 Bad Request` con el cuerpo `Client sent an HTTP request to an HTTPS server.`

**Diagnóstico**: el bloque del `Caddyfile` empezaba con `127.0.0.1:8080 { ... }`, sin especificar esquema. Caddy asume HTTPS por defecto salvo que se le diga lo contrario, y para una dirección así (sin dominio público) lo hace sirviendo TLS con su propia CA interna autofirmada — de ahí que una petición en texto plano fuera rechazada por el propio servidor TLS antes de llegar a ninguna lógica de rutas.

**Solución parcial**: anteponer el esquema explícitamente, `http://127.0.0.1:8080 { ... }`, para forzar HTTP plano sin TLS.

Con eso resuelto, apareció el segundo fallo: **todas** las rutas devolvían `200` con cuerpo vacío — incluidas rutas que deberían estar bloqueadas (`/`, `/flows`) e incluso una ruta inventada que no podía coincidir con nada. El bloque `handle { respond 404 }` pensado como salida por defecto no se estaba aplicando nunca.

**Diagnóstico**: preguntando directamente a la API de administración de Caddy (`curl http://localhost:2019/config/`) qué configuración tenía cargada de verdad, se confirmó que el `reload` sí se aplicaba — pero la ruta activa incluía `"match":[{"host":["127.0.0.1"]}]`. Al escribir `127.0.0.1:8080` como dirección del sitio, Caddy usa esa IP no solo para decidir en qué interfaz escuchar, sino también como **filtro sobre la cabecera `Host`** de la petición. Las pruebas se hacían con `curl http://localhost:8080/...`, que manda `Host: localhost:8080`, no `Host: 127.0.0.1` — la petición nunca coincidía con el único route definido, y caía al manejador por defecto de Caddy (200 vacío) en lugar de a los bloques `handle` configurados.

**Solución**: separar la interfaz de escucha del filtrado por host con la directiva `bind`, dejando la dirección del sitio sin IP:

```
:8080 {
	bind 127.0.0.1
	...
}
```

Así Caddy escucha solo en loopback (nada expuesto a la red local ni a internet salvo lo que decida reenviar `cloudflared`) sin exigir un `Host` concreto.

**Aprendizaje**: cuando el comportamiento observado no cuadra con la configuración que se cree tener cargada, preguntarle directamente al proceso en marcha (aquí, la API de admin de Caddy en `:2019`) qué tiene activo de verdad ahorra mucho tiempo frente a seguir editando el archivo a ciegas — el archivo puede ser correcto y aun así no significar lo que se piensa que significa. Y una dirección de sitio en un Caddyfile no es solo "dónde escuchar": mezclar ahí una IP tiene efectos de *matching* que no son obvios a primera vista.
