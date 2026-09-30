# Macetero con riego automático — diseño CAD, sin imprimir todavía

Ø240 mm de base · Ø200 mm de maceta · ~226 mm de alto total. Depósito útil **1.25 L** · tierra **2.45 L** · 7 piezas · **sin soportes**.

Diseño paramétrico generado con un motor propio en Python/numpy (sin CAD externo) — ver [Cómo se ha hecho esto](#cómo-se-ha-hecho-esto). Verificado geométricamente (41 puntos de control, 0 interferencias entre piezas), pero **todavía no impreso ni validado físicamente** — antes de encargar el pedido, revisar [Lo que queda pendiente](#lo-que-queda-pendiente).

Renders reales del modelo en [`preview/`](preview/) y en la ficha técnica autocontenida [`ficha_tecnica.html`](ficha_tecnica.html). [`concepto_visual.jpg`](concepto_visual.jpg) es distinto: una **visualización conceptual generada por IA** (no una foto real ni un render del CAD) para transmitir de un vistazo cómo quedaría el producto acabado en un entorno doméstico — útil para explicar la idea, pero no representa fielmente la geometría (por ejemplo, no muestra el saliente de la torre de llenado) ni confirma que la pantalla que aparece tenga hueco real todavía.

## La regla que ordena todo el diseño

**El depósito no tiene ni un solo orificio por debajo del nivel máximo de agua.**

En impresión FDM las capas filtran, así que en lugar de intentar sellar mejor los pasos, se han eliminado. Todo entra y sale del depósito por arriba: el llenado por la torre, el tubo de impulsión de la bomba y su cable de alimentación por sendas ranuras en la cara inferior de la tapa, y el resto de cables por el anillo técnico seco. La única junta del conjunto está 9 mm por encima del nivel máximo y solo controla evaporación, no presión.

## Las 7 piezas

| # | Pieza | Material | Cotas | Volumen | Orientación |
|---|---|---|---|---|---|
| 01 | cubeta_base | PETG | Ø240 × 70 | 473 cm³ | Suelo abajo |
| 02 | tapa_superior | PETG | Ø232 × 12 | 248 cm³ | Plana, collar arriba |
| 03 | maceta | PETG o PLA | Ø200 × 156 | 399 cm³ | Suelo abajo |
| 04 | cesta | PETG | Ø188 × 133 | 197 cm³ | Fondo abajo |
| 05 | tapon_llenado | PETG | Ø28 × 15 | 5 cm³ | Cabeza abajo |
| 06 | tapa_bahia | PLA | Ø69 × 2 | 7 cm³ | Plana |
| 07 | rejilla_drenaje | PETG | Ø176 × 2.5 | 52 cm³ | Plana |

Total ≈ 1380 cm³ de volumen sólido → unos 0.9–1.1 kg de filamento y 50–60 h de impresión repartidas en 7 trabajos.

> **Ojo con la cama.** La cubeta y la tapa miden Ø240 y Ø232: hace falta una cama de **250 mm o más** (Bambu X1/P1 con 256, Prusa XL, Elegoo Neptune 4 Max...). La Prusa MK4 (250 × 210) y las 220 × 220 tipo Ender **no entran**. Si es el caso, edita `D_BASE = 240.0` en `params.py`, cámbialo por `200.0` y ejecuta `python3 build.py`: se regeneran los 7 STL a escala, con los huecos de componentes intactos.

## Ajustes de laminado

Lo único crítico es la **cubeta base**, que es la que aguanta el agua.

| Ajuste | Cubeta base | Resto de piezas |
|---|---|---|
| Material | PETG | PETG (PLA vale en 03 y 06) |
| Boquilla / capa | 0.4 / 0.25 mm | 0.4 / 0.2 mm |
| Perímetros | **5** | 3 |
| Capas sup./inf. | 5 / 5 | 4 / 4 |
| Relleno | 25 % giroide | 15 % giroide |
| Temperatura | 245 °C / cama 80 °C | 240 °C / 80 °C |
| Ventilador | 30 % | 40 % |
| Flujo | 102–103 % | 100 % |
| Soportes | ninguno | ninguno |
| Falda | brim 5 mm | brim 5 mm en 03 |

Menos ventilador y algo más de flujo sueldan mejor las capas: es lo que hace que un depósito impreso no sude.

**Prueba de fugas, antes de montar nada.** Llena la cubeta hasta 55 mm y déjala 24 h sobre papel de cocina. Si aparece humedad, da dos manos de resina epoxi alimentaria o poliuretano transparente por el interior y repite la prueba.

## Lista de materiales

| Cant. | Componente | Nota |
|---|---|---|
| 1 | ESP32 DevKit | El que ya usa `macetero01` en producción — cabe de sobra en la bahía |
| 1 | Bomba sumergible 5 V | La misma que ya usas. **Vive suelta en el suelo del depósito**, cerca de (x=26, y=20) — su cable sale por el canal dedicado de la tapa hacia la bahía |
| 1 | Driver MOSFET o relé | Para la bomba |
| 1.5 m | Tubo de silicona 3 × 5 mm | Impulsión (la sumergible no necesita tubo de aspiración) |
| 1 | Sensor de humedad capacitivo | **No** resistivo: los resistivos se corroen |
| 1 | AHT20 o DHT22 | Opcional, temperatura y humedad ambiente |
| 1 | LED difuso 5 mm RGB | Entra a presión en el taladro de la brida |
| 2 | Hilos de acero inoxidable | Sonda de nivel por conductividad, cuelgan de la tapa |
| 1 | Placa adaptadora USB-C | Va en la ventana trasera |
| 3 | Tornillo M3 × 10 autorroscante | Tapa de la bahía |
| 700 mm | Cordón de silicona Ø2 mm | Junta de la tapa superior |
| 0.3 L | Arlita (arcilla expandida) | Cámara de aireación |
| 4 | Fieltros adhesivos | Bajo la base |

> **Decisión (2026-09-29): se adapta el diseño a la electrónica actual**, no al revés. `macetero01` ya usa ESP32 DevKit + bomba sumergible en producción — este macetero nuevo reutiliza esos mismos componentes en vez de migrar a ESP32-C3. La bomba peristáltica queda como alternativa documentada, no descartada, por si la sumergible no rinde bien en este depósito.
>
> **Ya aplicado en el CAD.** El modelo asumía una bomba *peristáltica* seca en la bahía con un tubo de aspiración entrando al depósito desde arriba. Con la sumergible, la bomba vive suelta dentro del propio depósito (hay espacio de sobra, Ø214×60 mm por dentro — no hace falta ningún hueco nuevo para el cuerpo) y lo que cambia es el canal que antes llevaba el tubo de aspiración: ahora lleva su cable de alimentación desde el depósito hasta la bahía, por la cara inferior de la tapa superior (`box(20, 32, 20, 50, ...)` en `tapa_superior()`, ensanchado 2 mm de alto para que quepa un conector pequeño). Sigue sin romper la regla de "cero agujeros por debajo del nivel máximo de agua": el cable sale por arriba, igual que antes salía el tubo. Reverificado con `test.py` (41/41, 0 interferencias) tras el cambio.

**Sobre el rendimiento de la peristáltica y la gravedad**: no sería el cuello de botella. Una peristáltica es de desplazamiento positivo — a diferencia de una sumergible centrífuga barata, su caudal no se desploma al bombear contra altura (aquí, unos 15–20 cm desde el agua hasta la tierra); de hecho suele sostener mejor esa altura que una centrífuga pequeña. Lo que sí es menor es el **caudal absoluto** (mL/min) — pero para riegos de 30–50 ml eso no es un problema real, como mucho tarda algunos segundos más por riego que la sumergible. Si algún día cambias de bomba, no sería por la gravedad.

## Montaje

1. **Cubeta.** Pega el cordón de silicona en la garganta de la coronación del depósito. Coloca la bomba sumergible suelta en el suelo del depósito, cerca de (x=26, y=20), con su cable subiendo por el canal dedicado de la tapa. Mete el ESP32 y el driver en la bahía trasera (con la tapa superior fuera la bahía está completamente abierta desde arriba: es el momento de cablear). La placa USB-C entra por la ventana trasera.
2. **Tubo de impulsión.** Sale de la bomba y sube por el taladro del nervio hasta la maceta — es el único tubo, la sumergible no necesita aspiración.
3. **Cables.** El de la bomba sube desde el depósito por su canal dedicado (junto al de aspiración de antes) hasta la bahía. El del LED va desde la bahía por el canal largo de la cara inferior de la tapa hasta la torre, y sube por el conducto que queda al lado del tabique interior. El del sensor de humedad sube por el nervio, junto al tubo de impulsión. Las dos sondas de nivel cuelgan dentro del depósito.
4. **Tapa superior.** Encájala en el alojamiento haciendo coincidir el chavetero con la chaveta del frente; así quedan alineados los canales. Los taladros de la torre y del nervio quedan mirando al frente y al dorso.
5. **Maceta.** Baja la torre y el nervio por sus huecos del collar. Solo entra en una posición.
6. **Cesta.** Apóyala en los tres tetones del fondo de la maceta. Echa 20 mm de arlita, pon la rejilla sobre la repisa, y encima la tierra.
7. **Tapa de la bahía** con los 3 tornillos M3, y los fieltros bajo la base.
8. **Tapón** a presión en la boca de llenado. Llena con una botella o un embudo.

## Lo que ya está resuelto en el modelo

- **Drenaje sin contaminar el depósito.** La cesta no drena al agua limpia: el exceso queda en la cámara de aireación de 20 mm y se reabsorbe por capilaridad. Si se pasa, dos rebosaderos a 17 mm del fondo vierten al hueco entre cesta y maceta, y salen por dos taladros visibles en la pared. Goteo a la vista = aviso.
- **Servicio sin herramientas para lo frecuente.** Rellenar: tapón. Cambiar la planta: se saca la cesta entera por las dos asas del borde. Limpiar el depósito: se levanta la maceta y la tapa (no van atornilladas, las sujetan la junta y el peso). Solo la bahía lleva tornillos.
- **Escalable.** Un único parámetro, `D_BASE`. Los huecos que alojan componentes comerciales son absolutos a propósito y no escalan.

## Lo que queda pendiente

- **Pantalla.** Sin hueco reservado todavía en ningún sitio del modelo. La torre de servicio mide solo Ø30 mm por fuera — insuficiente incluso para una OLED de 0.96″ (~27×27 mm de módulo). Decidir el módulo concreto antes de tocar esa zona.
- **Difusor de riego.** Ahora el tubo gotea en un punto. Un anillo repartidor impreso sería la pieza 08.
- **Embudo de llenado.** La boca es una D de 16 × 24 mm: cómoda con botella, justa con jarra.
- **Nivel de agua.** Las dos sondas por conductividad dan un aviso de «poca agua», no una medida. Excitar en pulsos cortos o en alterna para no electrolizar.
- **Sin roscas impresas.** El tapón es a presión y la tapa superior va libre. Es deliberado: menos puntos de fuga y nada que se agarrote.

Con la pantalla como único hueco por decidir, el resto del prototipo se puede dar por completo con los componentes reales que ya tienes.

## Cómo se ha hecho esto

No hay CAD detrás: el modelo son funciones de distancia con signo (SDF) en Python. Solo necesita `numpy`.

| Archivo | Qué hace |
|---|---|
| `params.py` | Todas las cotas, en mm |
| `design.py` | Las 7 piezas |
| `geo.py` | Primitivas, booleanas, mallador y escritor de STL |
| `build.py` | Genera `stl/*.stl` → `python3 build.py` |
| `test.py` | Verificación numérica → `python3 test.py` |
| `render.py` | Vistas previas PNG → `python3 render.py` |
| `reporte.json` | Malla, volumen y cotas de cada pieza |

Para cambiar una cota, edítala en `params.py` y vuelve a ejecutar `build.py`.

**Verificación pasada:** 41 comprobaciones de material/hueco en puntos concretos, 0 fallos. 0 interferencias entre piezas (barrido volumétrico de 1.2 mm con margen de 0.15 mm). Mallas cerradas: 6 de 7 piezas con 0 aristas defectuosas; `03_maceta` tiene 3 sobre 1.2 millones de triángulos, en la intersección torre-pared (zona no estructural, del cableado del LED) — cualquier laminador la repara sola al abrirla.

`stl/*.stl` (las piezas listas para laminar) no se versionan aquí por tamaño — se generan localmente con `python3 build.py` cuando hagan falta.
