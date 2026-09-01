# Arquitectura

## Principio de diseño central

**El ESP32 no decide nada.** Mide sensores, los publica por MQTT, y ejecuta un comando de riego cuando lo recibe — nada más. Toda la lógica (¿hay que regar ahora?, ¿qué umbral aplica?, ¿está dentro de la franja horaria permitida?) vive en el servidor, en Node-RED.

Esta decisión se tomó desde el inicio del proyecto, no como una refactorización posterior, y condiciona el resto de decisiones de arquitectura:

- **Escalabilidad**: añadir un macetero nuevo no requiere cambiar la lógica de decisión, solo dar de alta su configuración en el servidor.
- **Iteración rápida**: cambiar el umbral de riego, la franja horaria, o mañana un modelo de ML que decida en función del histórico, no requiere volver a flashear ningún dispositivo.
- **Mantenibilidad**: el firmware del ESP32 se mantiene simple y estable en el tiempo; la complejidad crece del lado del servidor, donde es más fácil de testear, versionar y depurar.

## Flujo de datos

1. El ESP32 lee sensores (humedad de suelo, temperatura, presión) cada 4 segundos y los publica como JSON en el topic MQTT `maceteros/{device_id}/sensores`.
2. Mosquitto (broker MQTT, corriendo en la Raspberry Pi) distribuye ese mensaje a quien esté suscrito.
3. Node-RED, suscrito a `maceteros/+/sensores` (comodín que captura cualquier dispositivo):
   - Reenvía los campos numéricos a InfluxDB para histórico.
   - Alimenta los gauges del dashboard en tiempo real.
   - Evalúa si toca regar, comparando la humedad recibida contra la configuración guardada (umbral, franja horaria, tiempo desde el último riego automático).
4. Si la evaluación decide regar, Node-RED publica `REGAR` en `maceteros/{device_id}/comando`, construyendo el topic dinámicamente a partir del dispositivo que originó la lectura.
5. El ESP32, suscrito a ese topic, activa el relé de la bomba durante un tiempo fijo al recibir el comando — sin evaluar nada, solo ejecuta — y publica una confirmación en su topic de estado al terminar.
6. En paralelo, un botón en el dashboard permite publicar el mismo comando manualmente, reutilizando exactamente el mismo camino que el riego automático.

## Por qué estas tecnologías

**MQTT sobre HTTP/REST**: bajo consumo, pensado para dispositivos con recursos limitados, y el patrón publicador/suscriptor encaja de forma natural con "muchos sensores publicando, un servidor escuchando" — especialmente de cara a escalar a múltiples dispositivos sin que cada uno necesite saber quién más existe.

**Node-RED como capa de orquestación**: permite iterar la lógica de negocio (reglas de riego, transformación de datos) de forma visual y rápida, sin recompilar nada, y tiene soporte de primera clase tanto para MQTT como para InfluxDB.

**InfluxDB (series temporales) en vez de una base de datos relacional para las lecturas**: los datos de sensores son fundamentalmente series temporales — una lectura, un timestamp, repetido miles de veces. InfluxDB está optimizado para ese patrón de escritura y consulta (agregaciones por ventana de tiempo, retención automática) de una forma en la que una base relacional genérica no lo está.

**Grafana para histórico, Node-RED Dashboard para control**: separación deliberada. Grafana es una herramienta de solo lectura pensada para visualización de series temporales; forzarla a hacer control (botones, escritura) es forzar su diseño. Node-RED, en cambio, ya tiene acceso directo a MQTT y al contexto de configuración, así que el control vive ahí de forma natural.

## Esquema de topics MQTT

```
maceteros/{device_id}/sensores    → publica el ESP32, escucha la plataforma
maceteros/{device_id}/comando     → publica la plataforma, escucha el ESP32
maceteros/{device_id}/estado      → publica el ESP32 (presencia y confirmaciones)
```

El `device_id` se define en el firmware con un único `#define`, a partir del cual se construyen los topics y el identificador de cliente MQTT. Desplegar el mismo firmware en un dispositivo nuevo requiere cambiar esa única línea.

La plataforma se suscribe con los comodines `maceteros/+/sensores` y `maceteros/+/estado`, de modo que recibe automáticamente los datos de cualquier dispositivo nuevo sin cambios de configuración. El `device_id` se extrae del propio payload (el firmware lo incluye) o, como respaldo, del segundo nivel del topic.

## Ciclo cerrado de riego

La orden de riego no se considera cumplida hasta que el dispositivo lo confirma:

1. La plataforma publica `REGAR` en el topic de comando del dispositivo.
2. El ESP32 acciona el relé y, al terminar, publica en su topic de estado un evento `riego_completado` con la duración real medida.
3. La plataforma registra ese evento como el último riego efectivo del dispositivo.
4. La condición de "han pasado 24 h desde el último riego" se evalúa contra la **confirmación**, no contra la orden.

La consecuencia práctica es que si un dispositivo está apagado o no responde, la plataforma no da el riego por hecho y lo reintentará cuando vuelva a estar disponible. Para evitar que ese reintento se convierta en una ráfaga de órdenes, existe además una ventana mínima de 60 segundos entre comandos consecutivos al mismo dispositivo, independiente de la confirmación.

### Detección de presencia (LWT)

Al conectarse, cada dispositivo registra en el broker un mensaje *Last Will and Testament*: si la conexión se pierde de forma abrupta (corte de alimentación, cuelgue, pérdida de WiFi), el propio broker publica `{"online": false}` en el topic de estado del dispositivo. Tras una conexión exitosa, el dispositivo publica `{"online": true}`.

Ambos mensajes se publican con el flag *retained*, de modo que cualquier suscriptor que se conecte después conoce inmediatamente el estado actual de cada dispositivo sin esperar al siguiente mensaje.

## Diseño del firmware

El `loop()` del ESP32 no bloquea en ningún punto de su operación normal. El riego se implementa como una pequeña máquina de estados basada en `millis()`:

- Al recibir un comando, se activa el relé y se registra el instante de inicio.
- En cada vuelta del `loop()` se comprueba si ha transcurrido la duración configurada; si es así, se apaga el relé y se publica la confirmación.
- Una orden que llegue mientras hay un riego en curso se descarta, en lugar de encolarse.

La consecuencia es que durante el riego el dispositivo sigue publicando lecturas, procesando mensajes MQTT y manteniendo su conexión. La implementación anterior, basada en `delay()`, dejaba al ESP32 insensible durante todo el pulso de riego, lo que provocó que las órdenes se acumularan en el broker y se ejecutaran en cadena (ver [`troubleshooting.md`](troubleshooting.md#9-riegos-en-ráfaga-al-introducir-la-confirmación-del-dispositivo)).

Adicionalmente existe un tope de seguridad por hardware lógico: la duración efectiva del riego se acota a un máximo absoluto, de modo que un valor de configuración erróneo no puede dejar la bomba encendida indefinidamente.

## Seguridad

La plataforma aplica tres capas independientes sobre la comunicación con los dispositivos.

### Autenticación

El broker no admite conexiones anónimas. Cada cliente dispone de credenciales propias: un usuario para la plataforma y **un usuario por dispositivo**. Esta separación permite revocar el acceso de un macetero concreto —por ejemplo, si se pierde o se ve comprometido— sin afectar al resto del sistema.

### Autorización

La autenticación por sí sola no basta: un dispositivo legítimo no debe poder leer los datos de otros ni emitir órdenes. Las ACLs del broker restringen cada identidad a su ámbito:

```
user nodered
topic readwrite maceteros/#

user macetero01
topic write maceteros/macetero01/sensores
topic write maceteros/macetero01/estado
topic read  maceteros/macetero01/comando
```

La asimetría es deliberada: el dispositivo **publica** sus lecturas y su estado, pero solo **lee** comandos. Emitir órdenes de riego es privilegio exclusivo de la plataforma, incluso sobre el propio dispositivo.

### Cifrado en tránsito

Toda la comunicación MQTT viaja sobre TLS 1.2 en el puerto 8883. El puerto 1883 (sin cifrar) está cerrado.

Se emplea una **autoridad certificadora propia**: la CA firma el certificado del broker, y cada dispositivo lleva embebido el certificado de la CA para verificar que se conecta al broker legítimo y no a un suplantador. Es el mismo modelo de confianza de HTTPS, con la organización actuando como autoridad en lugar de una CA pública.

La clave privada de la CA no reside en el servidor: se mantiene fuera del alcance de los servicios, ya que solo se necesita para firmar certificados nuevos.

**Trabajo pendiente**: actualmente solo se verifica la identidad del servidor. El siguiente paso es la autenticación mutua (mTLS), en la que cada dispositivo presenta su propio certificado de cliente y el broker lo valida. Es el estándar en despliegues IoT de producción y sustituye a las credenciales de usuario y contraseña.

### Validez temporal

TLS valida el periodo de vigencia de los certificados, lo que exige que el dispositivo conozca la fecha real. El ESP32 sincroniza por NTP al arrancar, con la zona horaria peninsular y sus reglas de cambio estacional, y actualiza el RTC con esa referencia. El RTC queda como respaldo para operar sin red.

Esto resolvió además un problema anterior: la franja horaria de riego dependía de la hora del RTC, que podía quedar desajustada tras un reinicio.

### Acceso a los servicios

Node-RED distingue dos niveles de acceso: `adminAuth` protege el editor de flujos, y `httpNodeAuth` protege el dashboard. La separación tiene sentido de producto — el usuario final debe poder consultar su planta y regar, pero no reprogramar la lógica del sistema.

Grafana e InfluxDB emplean su propia autenticación, con el registro de usuarios deshabilitado y sin acceso anónimo.

Las credenciales de los nodos de Node-RED se cifran con una clave propia (`credentialSecret`) en lugar de una autogenerada, de modo que una copia de seguridad de los flujos es restaurable en otra máquina.

## Modelo de datos en InfluxDB

- **Measurement**: `sensores`
- **Tag**: `device_id`
- **Fields**: `humedad_suelo`, `temp_aire`, `presion`, `estado`

La distinción entre tag y field es deliberada. En una base de datos de series temporales, cada combinación única de tags genera una serie independiente: los tags están pensados para metadatos estables por los que se filtra y agrupa, no para valores que cambian con cada lectura.

Inicialmente `estado` (SECO / HUMEDO / OK…) se modeló como tag, lo que fragmentaba la serie de humedad en tantas series como estados posibles, cortando las gráficas cada vez que la planta cambiaba de estado. Se corrigió moviéndolo a field: además de resolver la fragmentación, es coherente con el hecho de que `estado` es un valor **derivado** de `humedad_suelo` mediante umbrales, no un dato independiente.

## Configuración persistente y editable

Los parámetros de cada macetero (umbral de humedad, franja horaria de riego permitido, duración del pulso de riego) se guardan en el *global context* de Node-RED, indexados por `device_id`:

```javascript
{
  "macetero01": {
    "humedadMin": 36,
    "horaInicio": 8,
    "horaFin": 21,
    "duracionRiegoMs": 9000
  }
}
```

Esta estructura, indexada por dispositivo desde el primer momento aunque hoy solo exista un macetero, es la que permite que escalar a múltiples dispositivos sea añadir una entrada al objeto, no rediseñar el sistema.

## Limitaciones conocidas y trabajo pendiente

- La configuración vive en el *global context* de Node-RED con persistencia en disco (`localfilesystem`), no en una base de datos. Es suficiente para el número actual de dispositivos, pero una base de datos relacional será necesaria cuando entren en juego usuarios, permisos y relaciones entre entidades.
- La autenticación de dispositivos es por usuario y contraseña sobre TLS. La evolución natural es **mTLS** con certificado por dispositivo, que además habilita el aprovisionamiento automático y la revocación individual sin gestionar contraseñas.
- El acceso a Node-RED, Grafana e InfluxDB es por HTTP sin cifrar. En red local aislada es asumible, pero exponerlos requiere un reverse proxy con HTTPS.
- Las confirmaciones de riego no distinguen si la orden fue manual o automática, de modo que un riego manual también bloquea el automático durante 24 horas. Es el comportamiento deseado hoy, pero convendría diferenciarlo si se quieren políticas distintas.
- No hay sensor de nivel de depósito, por lo que la plataforma no puede saber si hay agua disponible antes de ordenar un riego. Es la principal carencia funcional: la bomba puede llegar a trabajar en seco.
- El riego se dosifica por **tiempo**, no por volumen. Un caudalímetro permitiría dosificación volumétrica real y detectar la degradación de la bomba (menos caudal para el mismo tiempo de funcionamiento).
- La calibración del sensor de humedad está fijada en el firmware. Recalibrar exige recompilar y flashear, cuando conceptualmente es un parámetro de configuración más.
- No hay actualización de firmware por red (OTA). Con el 73 % de la flash ocupada tras incorporar TLS, habilitarla requerirá ajustar el esquema de particiones.
