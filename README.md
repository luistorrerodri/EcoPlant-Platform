# EcoPlant Platform 🌱

Plataforma IoT de riego inteligente para maceteros, construida de cero: desde el sensor hasta el dashboard, con la lógica de decisión centralizada en el servidor en lugar del microcontrolador.

Proyecto personal desarrollado como portfolio técnico durante un Máster en IoT, con el objetivo de cubrir el stack completo de un sistema IoT real: hardware, firmware, mensajería, persistencia de datos, visualización y control remoto.

## Qué hace

- Mide humedad de suelo, temperatura y presión atmosférica en tiempo real
- Decide automáticamente cuándo regar según un umbral y una franja horaria configurables, **sin que la lógica viva en el microcontrolador**
- Verifica que cada orden de riego se ha ejecutado realmente, en lugar de asumirlo
- Detecta cuándo un dispositivo se desconecta de forma inesperada
- Comunicación cifrada con autenticación y autorización por dispositivo
- Permite riego manual bajo demanda desde un dashboard web
- Guarda histórico de todas las lecturas para análisis posterior
- Pensado desde el diseño para escalar a múltiples dispositivos

## Arquitectura

```
ESP32 (sensores + bomba)
        │  maceteros/{device_id}/sensores
        │  maceteros/{device_id}/comando
        │  maceteros/{device_id}/estado
        ▼
   Mosquitto (broker MQTT)
        │
        ▼
     Node-RED  ──────────────┐
   (lógica de decisión)      │
        │                    ▼
        ▼                InfluxDB (histórico)
  Dashboard web                │
  (control manual,             ▼
   parámetros)              Grafana
                          (visualización)
```

Todo corre sobre una Raspberry Pi en red local. El ESP32 **solo mide y ejecuta comandos** — nunca decide. La decisión de regar (umbral de humedad, franja horaria, tiempo desde el último riego) se evalúa en Node-RED, que publica un comando MQTT cuando corresponde. Esta separación es la decisión de arquitectura central del proyecto: permite cambiar la lógica de riego, añadir machine learning más adelante, o gestionar decenas de dispositivos, sin volver a flashear ni un solo ESP32.

Ver [`docs/architecture.md`](docs/architecture.md) para el detalle de cada decisión de diseño.

## Stack

| Capa | Tecnología |
|---|---|
| Sensores | BMP280 (temp/presión), sonda capacitiva de humedad de suelo, RTC DS1307 |
| Microcontrolador | ESP32 DevKit (Arduino framework, PlatformIO) |
| Mensajería | MQTT (Mosquitto) |
| Orquestación / lógica | Node-RED |
| Persistencia | InfluxDB 2.x (series temporales) |
| Visualización | Grafana + Node-RED Dashboard |
| Servidor | Raspberry Pi (Debian Bookworm, ARM64) |

## Estado actual

- [x] Hardware validado (sensores, RTC, OLED, bomba)
- [x] Firmware de producción: mide, publica por MQTT, obedece comandos
- [x] Pipeline completo de datos: ESP32 → MQTT → Node-RED → InfluxDB → Grafana
- [x] Dashboard de control: riego manual, umbral y horario configurables en caliente
- [x] Lógica de decisión de riego migrada completamente al servidor
- [x] Estructura de topics escalable para múltiples dispositivos (`device_id` dinámico)
- [x] Configuración persistente entre reinicios de la plataforma
- [x] Ciclo cerrado: el dispositivo confirma cada riego ejecutado
- [x] Detección de dispositivos desconectados (MQTT Last Will and Testament)
- [x] Firmware no bloqueante: el dispositivo sigue operativo durante el riego
- [x] Seguridad: autenticación por dispositivo, ACLs por topic y MQTT sobre TLS
- [ ] Autenticación mutua (mTLS) con certificado por dispositivo
- [ ] Acceso remoto seguro (reverse proxy con HTTPS)
- [ ] Backend propio con modelo multi-usuario (usuario → ubicación → dispositivo)
- [ ] App móvil
- [ ] Integración meteorológica y analítica sobre el histórico

## Problemas reales resueltos

Una parte del valor de este proyecto está en los problemas de integración reales que surgieron y cómo se diagnosticaron — no solo en que "funcione". Detalle completo en [`docs/troubleshooting.md`](docs/troubleshooting.md), por ejemplo:

- **Sensor mal etiquetado**: un módulo vendido como BME280 resultó ser un BMP280 (sin sensor de humedad) tras leer su chip ID por I2C directamente — el fabricante había reutilizado la serigrafía.
- **Repositorio APT roto en Bookworm/ARM64**: fallo de verificación GPG persistente en el repositorio oficial de InfluxData para esa combinación de sistema, resuelto instalando desde el binario oficial con un servicio systemd propio en lugar de depender de `apt`.
- **Riegos en ráfaga**: al condicionar el riego a la confirmación del dispositivo, las órdenes se encolaron en el broker mientras el firmware bloqueaba. Resuelto con una ventana de guarda en la plataforma y, de raíz, con un firmware no bloqueante.
- **Dos implementaciones de TLS, dos criterios**: el mismo certificado era aceptado por un cliente y rechazado por el otro, primero por falta de SAN (Node.js ignora el Common Name) y después por el tipo de entrada del SAN (mbedTLS no evalúa las de tipo `iPAddress`). Resuelto con un certificado que satisface a ambas implementaciones.

## Estructura del repositorio

- [`firmware/`](firmware/) — código del ESP32 y guía de compilación/flasheo
- [`platform/`](platform/) — configuración de Node-RED, Grafana, y guía de instalación del stack en Raspberry Pi
- [`docs/`](docs/) — arquitectura, hardware, troubleshooting y roadmap detallados

## Autor

Luis — Ingeniero de Telecomunicaciones, cursando Máster en IoT.
