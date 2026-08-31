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
- No hay autenticación en el broker MQTT (`allow_anonymous true`) ni en el acceso a Node-RED/Grafana — aceptable en red local aislada, pero es el primer bloqueante a resolver antes de exponer la plataforma a internet.
- El pulso de riego en el firmware sigue siendo bloqueante (`delay()`): durante los segundos que dura el riego, el ESP32 no procesa mensajes MQTT entrantes. Esto provocó, durante el desarrollo, que varias órdenes se encolaran en el broker y se ejecutaran en cadena al terminar el primer riego. Se mitigó con una ventana de bloqueo en la plataforma, pero la solución de fondo es un riego no bloqueante basado en `millis()`.
- Las confirmaciones de riego no distinguen si la orden fue manual o automática, de modo que un riego manual también bloquea el automático durante 24 horas. Es el comportamiento deseado hoy (la planta tiene agua, sin importar quién lo ordenara), pero convendría diferenciarlo si en el futuro se quieren políticas distintas.
- No hay sensor de nivel de depósito, por lo que la plataforma no puede saber si hay agua disponible antes de ordenar un riego.
