# Hardware

## Lista de componentes (BOM)

| Componente | Modelo / referencia | Función | Notas |
|---|---|---|---|
| Microcontrolador | ESP32 DevKit (AZ-Delivery) | Lectura de sensores, conectividad WiFi/MQTT, control del relé | Chip ESP32-D0WD-V3 |
| Sensor ambiental | BMP280 | Temperatura y presión atmosférica | Vendido como BME280; ver nota abajo |
| Sensor de humedad de suelo | Sonda capacitiva | Humedad del sustrato | Salida analógica |
| Reloj de tiempo real | DS1307 | Timestamp de las lecturas | Incluye EEPROM AT24C32 en la misma placa |
| Pantalla | OLED SSD1306 0,96" | Visualización local de lecturas | I2C |
| Relé | JQC3F-05VDC-C | Conmutación de la bomba | Módulo con optoacoplador |
| Bomba | Bomba sumergible 3–5 V | Riego | Alimentada de forma independiente |
| Alimentación bomba | Portapilas 3×AA (4,5 V) | Alimentación de la bomba | Circuito separado del ESP32 |
| Alimentación ESP32 | USB (red eléctrica) | Alimentación del microcontrolador y sensores | — |

### Nota sobre el sensor ambiental

El módulo se adquirió etiquetado como **BME280** pero es en realidad un **BMP280**: responde en el bus I2C con chip ID `0x58` en lugar de `0x60`. La diferencia práctica es que **no dispone de sensor de humedad ambiente** — solo temperatura y presión. El firmware usa la librería `Adafruit_BMP280` en consecuencia. Ver [`troubleshooting.md`](troubleshooting.md#1-sensor-vendido-como-bme280-que-en-realidad-era-un-bmp280) para el diagnóstico completo.

## Pinout

| Función | GPIO |
|---|---|
| I²C SDA | 21 |
| I²C SCL | 22 |
| Humedad de suelo (analógico) | 34 |
| Relé de la bomba | 27 |

Los tres periféricos I2C (BMP280, SSD1306 y DS1307) comparten el mismo bus en GPIO 21/22.

## Direcciones I2C

Salida real del escáner I2C sobre el montaje:

| Dirección | Dispositivo |
|---|---|
| `0x3C` | OLED SSD1306 |
| `0x50` | EEPROM AT24C32 (integrada en el módulo RTC) |
| `0x68` | RTC DS1307 |
| `0x76` | BMP280 |

La presencia de `0x50` es normal: la mayoría de módulos DS1307 comerciales incorporan una EEPROM AT24C32 en la misma placa, que aparece como un dispositivo I2C independiente aunque el proyecto no la utilice.

## Calibración del sensor de humedad

Los valores de referencia del sensor capacitivo, obtenidos empíricamente:

```cpp
#define SOIL_DRY 2482   // lectura ADC en aire / sustrato seco
#define SOIL_WET 905    // lectura ADC sumergido en agua
```

El firmware mapea linealmente el valor crudo del ADC a un porcentaje de 0 a 100 entre esos dos extremos. Lecturas por encima de `SOIL_DRY` se recortan a 0 %.

**Recalibración**: estos valores dependen del sensor concreto y del tipo de sustrato. Para recalibrar, leer el valor crudo (`analogRead(34)`) con la sonda al aire y con la sonda sumergida en agua, y ajustar las constantes en consecuencia.

## Alimentación

El ESP32 y los sensores se alimentan por USB desde la red eléctrica. La bomba se alimenta de forma **independiente** desde un portapilas de 3×AA, conmutada por el relé.

Esta separación es deliberada: el arranque de un motor genera picos de corriente y ruido eléctrico que, compartiendo la alimentación con el microcontrolador, pueden provocar reinicios o lecturas erráticas de los sensores.

## Montaje del prototipo

El prototipo actual está montado sobre una cesta de fibra con:
- Maceta de terracota como contenedor de la planta
- Táper con tapa perforada como depósito de agua
- Electrónica fijada sobre una base de cartón adherida a la pared interior de la cesta, con silicona
- Pantalla OLED situada en el borde superior para que sea visible sin abrir nada

Es un montaje deliberadamente provisional, orientado a validar la electrónica y el software antes de invertir en una carcasa definitiva.

### Diseño previsto

Existe un diseño de carcasa dedicada (sección y planta acotadas) con:
- Cesta de plantación extraíble con cámara de drenaje
- Depósito de ~1,5 L sin orificios bajo la línea de agua
- Bahía electrónica seca, separada del agua
- Anillo técnico seco de 7 mm para todo el cableado
- Torre de servicio (llenado, indicador LED y pozo de bomba)
- Rebosaderos que drenan al exterior, nunca al depósito
- Junta EPDM por encima de la línea de agua

Su fabricación está pospuesta por coste; el desarrollo continúa sobre el prototipo provisional.

## Mejoras de hardware pendientes

- **Sensor de nivel de depósito**: con 1,5 L de capacidad, el margen antes de que la bomba trabaje en seco es reducido. Un sensor de nivel (dos electrodos o un interruptor de flotador) permitiría a la plataforma bloquear el riego cuando no hay agua, evitando dañar la bomba.
- **Pila del RTC**: verificar el estado de la pila CR2032 del DS1307. Si el reloj pierde la hora entre reinicios, es señal de que hay que sustituirla antes de fiarse del timestamp que genera.
- **Paso de cable estanco**: el cable de la bomba, al salir del agua hacia la zona seca, necesita un sellado adecuado (pasamuros con junta o prensaestopas) en el diseño definitivo.
