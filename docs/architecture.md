# Arquitectura

## Principio de diseño central

**El ESP32 no decide nada.** Mide sensores, los publica por MQTT, y ejecuta un comando de riego cuando lo recibe — nada más. Toda la lógica (¿hay que regar ahora?, ¿qué umbral aplica?, ¿está dentro de la franja horaria permitida?) vive en el servidor, en Node-RED.

Esta decisión se tomó desde el inicio del proyecto, no como una refactorización posterior, y condiciona el resto de decisiones de arquitectura:

- **Escalabilidad**: añadir un macetero nuevo no requiere cambiar la lógica de decisión, solo dar de alta su configuración en el servidor.
- **Iteración rápida**: cambiar el umbral de riego, la franja horaria, o mañana un modelo de ML que decida en función del histórico, no requiere volver a flashear ningún dispositivo.
- **Mantenibilidad**: el firmware del ESP32 se mantiene simple y estable en el tiempo; la complejidad crece del lado del servidor, donde es más fácil de testear, versionar y depurar.

## Flujo de datos

1. El ESP32 lee sensores (humedad de suelo, temperatura, presión) cada 4 segundos y los publica como JSON en el topic MQTT `planta_datos`.
2. Mosquitto (broker MQTT, corriendo en la Raspberry Pi) distribuye ese mensaje a quien esté suscrito.
3. Node-RED, suscrito a `planta_datos`:
   - Reenvía los campos numéricos a InfluxDB para histórico.
   - Alimenta los gauges del dashboard en tiempo real.
   - Evalúa si toca regar, comparando la humedad recibida contra la configuración guardada (umbral, franja horaria, tiempo desde el último riego automático).
4. Si la evaluación decide regar, Node-RED publica `REGAR` en el topic `planta_datos/comando`.
5. El ESP32, suscrito a ese topic, activa el relé de la bomba durante un tiempo fijo al recibir el comando — sin evaluar nada, solo ejecuta.
6. En paralelo, un botón en el dashboard permite publicar el mismo comando manualmente, reutilizando exactamente el mismo camino que el riego automático.

## Por qué estas tecnologías

**MQTT sobre HTTP/REST**: bajo consumo, pensado para dispositivos con recursos limitados, y el patrón publicador/suscriptor encaja de forma natural con "muchos sensores publicando, un servidor escuchando" — especialmente de cara a escalar a múltiples dispositivos sin que cada uno necesite saber quién más existe.

**Node-RED como capa de orquestación**: permite iterar la lógica de negocio (reglas de riego, transformación de datos) de forma visual y rápida, sin recompilar nada, y tiene soporte de primera clase tanto para MQTT como para InfluxDB.

**InfluxDB (series temporales) en vez de una base de datos relacional para las lecturas**: los datos de sensores son fundamentalmente series temporales — una lectura, un timestamp, repetido miles de veces. InfluxDB está optimizado para ese patrón de escritura y consulta (agregaciones por ventana de tiempo, retención automática) de una forma en la que una base relacional genérica no lo está.

**Grafana para histórico, Node-RED Dashboard para control**: separación deliberada. Grafana es una herramienta de solo lectura pensada para visualización de series temporales; forzarla a hacer control (botones, escritura) es forzar su diseño. Node-RED, en cambio, ya tiene acceso directo a MQTT y al contexto de configuración, así que el control vive ahí de forma natural.

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

- La configuración vive en memoria de Node-RED (global context), no en una base de datos persistente — se pierde si Node-RED se reinicia sin tener el contexto configurado para persistir en disco. Migrar a una base de datos ligera (o activar la persistencia de contexto de Node-RED) es un paso pendiente antes de producción real.
- El topic MQTT (`planta_datos`) es fijo y no escalable — funciona con un único dispositivo. La estructura pensada para escalar (`maceteros/{device_id}/...`) está documentada pero no migrada aún.
- No hay autenticación en el broker MQTT ni en el acceso a Node-RED/Grafana — válido en red local, pero debe resolverse antes de exponer la plataforma a internet.
