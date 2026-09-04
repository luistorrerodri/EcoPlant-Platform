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

El broker no admite conexiones anónimas, y cada cliente demuestra su identidad con un **certificado propio** (autenticación mutua, mTLS) en lugar de usuario y contraseña: la plataforma tiene el suyo y **cada dispositivo el suyo**, todos firmados por la misma CA. El CN del certificado (`nodered`, `macetero01`...) es lo que el broker usa como identidad para las ACLs. Esta separación permite revocar el acceso de un macetero concreto —por ejemplo, si se pierde o se ve comprometido— sin afectar al resto del sistema, y elimina de paso el riesgo de una contraseña filtrada: no hay contraseña que filtrar.

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

La clave privada de la CA vive en la propia Raspberry Pi (`~/certs/ca.key`), cifrada con una contraseña que solo conoce el operador — no está en texto plano ni la usa ningún servicio en su día a día, solo se necesita para firmar certificados nuevos. Es una mitigación razonable (un archivo robado no sirve de nada sin la contraseña) pero no equivale a mantenerla en una máquina separada del servidor: si la Pi se viera comprometida durante un tiempo prolongado, la contraseña podría capturarse la próxima vez que se usara. Moverla a una máquina offline queda como mejora pendiente.

La verificación es **mutua**: el dispositivo comprueba la identidad del broker (con `CA_CERT`) y el broker comprueba la identidad del dispositivo (con su certificado de cliente, `CLIENT_CERT`/`CLIENT_KEY`, firmado por la misma CA). El broker exige ese certificado antes de completar el handshake (`require_certificate`) y deriva la identidad de su CN en lugar de un usuario/contraseña (`use_identity_as_username`) — es el estándar en despliegues IoT de producción. Detalle de la generación de certificados de cliente en [`../platform/README.md`](../platform/README.md#certificados-de-cliente-mtls).

**Limitación conocida**: no hay lista de revocación (CRL). Revocar un dispositivo hoy es quitar su bloque de la ACL — el certificado seguiría siendo válido para TLS, pero sin ACL no podría hacer nada. Si una clave privada se comprometiera de verdad, la única garantía completa es regenerar la CA.

### Validez temporal

TLS valida el periodo de vigencia de los certificados, lo que exige que el dispositivo conozca la fecha real. El ESP32 sincroniza por NTP al arrancar, con la zona horaria peninsular y sus reglas de cambio estacional, y actualiza el RTC con esa referencia. El RTC queda como respaldo para operar sin red.

Esto resolvió además un problema anterior: la franja horaria de riego dependía de la hora del RTC, que podía quedar desajustada tras un reinicio.

### Acceso a los servicios

Node-RED distingue dos niveles de acceso: `adminAuth` protege el editor de flujos, y `httpNodeAuth` protege el dashboard. La separación tiene sentido de producto — el usuario final debe poder consultar su planta y regar, pero no reprogramar la lógica del sistema.

### Acceso remoto

El dashboard puede mostrarse desde fuera de la red local bajo demanda, sin exponer nada de forma permanente. Dos decisiones deliberadas:

- **Cloudflare Tunnel en vez de abrir un puerto en el router**: la Pi inicia una conexión saliente hacia Cloudflare; no hay ningún puerto escuchando conexiones entrantes desde internet en el router. Elimina de raíz la superficie de ataque típica de un port-forwarding casero (escaneos automatizados de puertos abiertos), a cambio de depender de un tercero para la ruta de acceso.
- **Un proxy local (Caddy) delante de Node-RED, no el túnel apuntando directamente a él**: Node-RED sirve el editor, la API de administración y el dashboard bajo la misma raíz, sin una separación de rutas pensada para exponer solo una parte. Caddy filtra por ruta y solo reenvía `/ui`, devolviendo 404 a cualquier otra cosa — así, aunque alguien obtenga la URL pública, lo único alcanzable es el dashboard, nunca el editor de flujos.

El túnel de `/ui` (Quick Tunnel) se levanta manualmente para cada demo — mientras no está corriendo, no hay nada expuesto a internet por ahí. Con la app móvil llegó un segundo túnel, este sí permanente: dominio propio (`ecoplantplatform.com`) + túnel de Cloudflare con nombre, exponiendo solo `api.ecoplantplatform.com` → Caddy → backend. Tiene sentido que este segundo sí esté siempre activo, porque ahora hay una app de uso real detrás, no solo demos puntuales — ver [`../platform/README.md`](../platform/README.md#5-acceso-remoto-demo-pública-bajo-demanda) para ambos.

Grafana e InfluxDB emplean su propia autenticación, con el registro de usuarios deshabilitado y sin acceso anónimo.

Las credenciales de los nodos de Node-RED se cifran con una clave propia (`credentialSecret`) en lugar de una autogenerada, de modo que una copia de seguridad de los flujos es restaurable en otra máquina.

## Modelo de datos en InfluxDB

- **Measurement**: `sensores`
- **Tag**: `device_id`
- **Fields**: `humedad_suelo`, `temp_aire`, `presion`, `estado`

La distinción entre tag y field es deliberada. En una base de datos de series temporales, cada combinación única de tags genera una serie independiente: los tags están pensados para metadatos estables por los que se filtra y agrupa, no para valores que cambian con cada lectura.

Inicialmente `estado` (SECO / HUMEDO / OK…) se modeló como tag, lo que fragmentaba la serie de humedad en tantas series como estados posibles, cortando las gráficas cada vez que la planta cambiaba de estado. Se corrigió moviéndolo a field: además de resolver la fragmentación, es coherente con el hecho de que `estado` es un valor **derivado** de `humedad_suelo` mediante umbrales, no un dato independiente.

## Configuración persistente y editable

Los parámetros de cada macetero (umbral de humedad, franja horaria de riego permitido, duración del pulso de riego, tipo de planta) viven en PostgreSQL, como columnas de `devices` — editables desde la app vía `PATCH /api/devices/{id}`. Node-RED sigue siendo quien decide si riega (`Decisión riego`, sección "Ciclo cerrado de riego"), pero ya no es la fuente de verdad de la configuración: cada 60 segundos sondea `GET /api/internal/device-configs` (backend, `127.0.0.1:8000`, nunca sale de loopback) y vuelca la respuesta en su *global context* (`config_maceteros`), con exactamente la misma forma que tenía antes de esta migración:

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

**Por qué un sondeo HTTP y no un nodo de Postgres en Node-RED ni una API nueva expuesta por Node-RED**: mover la configuración a Postgres exigía elegir quién habla con quién. Añadir un nodo de Postgres a Node-RED habría metido credenciales de base de datos en un sitio que hoy no las tiene, y construir una API nueva *dentro* de Node-RED habría ido contra el reparto de responsabilidades ya establecido (Node-RED es lógica de decisión + dashboard; FastAPI es la única superficie de API). Con un sondeo HTTP del lado de Node-RED hacia un endpoint del backend, el nodo **"Decisión riego"** — la automatización real, controlando una bomba física — no se toca en absoluto: solo cambia de dónde se rellena la variable que ya leía.

**`GET /api/internal/device-configs`** no usa el JWT de usuario del resto de la API — Node-RED no inicia sesión como nadie — sino un token estático compartido (cabecera `X-Internal-Token`, comparado con `secrets.compare_digest`), primer mecanismo de credencial de servicio a nivel HTTP en el backend. Es análogo a la identidad `backend-api` que ya existía en mTLS/MQTT (un servicio con su propia identidad, distinta de usuarios y dispositivos), solo que a nivel HTTP en vez de certificados. El riesgo real es bajo porque el tráfico nunca sale de `127.0.0.1` (Node-RED y el backend están en la misma Pi) — no pasa por Caddy, Cloudflare, ni el dominio público — pero el token evita que sea un endpoint abierto sin más dentro de esa confianza.

Elegir un tipo de planta desde la app (catálogo en `plant_types`, ver más abajo) solo rellena estos mismos campos con valores por defecto — se pueden seguir editando a mano después, y el ciclo de riego nunca lee el catálogo directamente, solo los valores ya copiados a `devices`.

## Backend multiusuario

Node-RED resuelve bien la orquestación (sensores, lógica de riego, un dashboard), pero no tiene ni tenía previsto tener un modelo de usuarios: cualquiera con la contraseña del `httpNodeAuth` ve y controla todo. El backend nuevo (FastAPI + PostgreSQL, en `backend/`) añade esa capa por delante, sin sustituir nada — es una pieza aditiva, un peer de Node-RED, no un reemplazo.

**Por qué una base de datos relacional aparte, y no extender el *context store* de Node-RED**: el modelo `usuario → ubicación → dispositivo` es fundamentalmente relacional (claves foráneas, restricciones de unicidad, permisos por propietario) — forzar eso sobre un almacén de pares clave-valor pensado para configuración de dispositivos habría sido más frágil que levantar una base de datos que ya está diseñada para este problema. PostgreSQL en concreto, y no SQLite, porque el resto de la plataforma ya trata "instalar el servidor de base de datos real como servicio systemd" como la norma (InfluxDB es el precedente directo), y porque SQLite con varios workers de `uvicorn` tiene un problema real de bloqueo de escritura de un solo archivo.

**Autenticación con tokens revocables, no solo un JWT de larga duración**: el token de acceso es un JWT de corta duración (30 min por defecto); el de refresco es un secreto aleatorio cuyo *hash* se guarda en una tabla (`refresh_tokens`), no el valor en sí — igual que una contraseña. Esto es lo que hace posible un logout real y que cambiar la contraseña invalide las sesiones activas: con un JWT de refresco puro (sin estado en el servidor), no hay forma de revocar nada antes de que expire por sí solo.

**El código de reclamación de dispositivos**: cada macetero es un objeto físico, preflasheado con un `DEVICE_ID` fijo — no hay forma de que se autoprovisione ni de que "sepa" a qué usuario pertenece. Para asociarlo a una cuenta hace falta un secreto compartido fuera de banda, igual que un certificado de cliente se entrega físicamente a un dispositivo: el operador siembra el dispositivo (`POST /api/admin/devices/seed`) y obtiene un código de un solo uso, que se hashea igual que una contraseña y se entrega por otro canal (una pegatina en el macetero, un mensaje al usuario). El propio usuario lo introduce junto al `device_id` para reclamarlo. Sin CRL ni revocación de certificados de por medio, es el mecanismo más simple que sigue exigiendo prueba de posesión física del dispositivo.

Sin envío de emails: el registro activa la cuenta al momento, sin verificación por correo ni recuperación de contraseña por email (hay un `change-password` para quien ya tiene sesión). Detalle completo del modelo de datos, endpoints y despliegue en [`../platform/README.md`](../platform/README.md#6-backend-api) y [`../backend/README.md`](../backend/README.md).

## App móvil

React Native + Expo (TypeScript), en `mobile/`. Consume la API del backend por HTTP igual que cualquier otro cliente futuro (un portal web usaría exactamente los mismos endpoints) — construir primero la API y después la app fue deliberado, no hay nada que rehacer al pasar de una a otra.

**React Native + Expo, no nativo por plataforma**: mismo código para Android e iOS. Con Expo además se puede compilar la build de iOS en la nube (EAS Build) sin poseer un Mac — relevante aquí, porque el desarrollo se hace desde Windows.

**JWT en `SecureStore`, nunca en `AsyncStorage`**: los tokens de acceso y refresco se guardan cifrados con el keychain/keystore del sistema operativo, coherente con cómo el propio backend trata esos mismos tokens (nunca en claro). Un interceptor en el cliente HTTP reintenta la petición una vez tras un `401`, refrescando el token en segundo plano — verificado de verdad bajando temporalmente `ACCESS_TOKEN_EXPIRE_MINUTES` en el backend en vez de asumir que el código estaba bien.

**URL del servidor configurable en tiempo de ejecución, no fija en el código**: se guarda en `SecureStore` y se edita desde la app. Por defecto apunta al dominio fijo (`api.ecoplantplatform.com`, dominio propio + túnel de Cloudflare con nombre, ambos permanentes) — funciona igual en casa o fuera sin tocar nada; la IP de la LAN sigue disponible como alternativa manual. Esta pieza fue la que evitó tener que duplicar trabajo entre "desarrollar en casa" y "usar la app fuera": se construyó una vez, y solo cambió el valor por defecto cuando el dominio estuvo listo.

**Notificaciones push (Firebase Cloud Messaging)**: el backend pasa de solo publicar en MQTT a también **suscribirse** a `maceteros/+/estado` (el ACL de `backend-api` ya lo permitía, pensado para esto desde que se creó el certificado). Al detectar una desconexión inesperada o un riego completado, resuelve el propietario del dispositivo (`Device.location.owner`) y le envía una notificación a través de la API pública de push de Expo, que a su vez usa Firebase Cloud Messaging por debajo. Requirió una build de desarrollo propia compilada con EAS: Expo retiró el soporte de notificaciones push en Android dentro de Expo Go a partir del SDK 53, y además Google exige credenciales FCM V1 propias (no vale la infraestructura compartida antigua) — la clave de administrador de Firebase para esto vive cifrada en EAS, nunca en el repositorio; solo `google-services.json` (contenido público, identifica la app pero no autoriza nada) está versionado.

**Acceso por LAN, además del túnel**: Caddy pasa a escuchar también en la IP de la Pi en la red local, no solo en `127.0.0.1` — mismo nivel de confianza que ya tenían Node-RED/Grafana/InfluxDB (nada expuesto a internet, sin *port-forwarding* en el router). Permite desarrollar y usar la app en casa sin depender de tener el túnel de Cloudflare levantado.

## Próxima iteración: personalización por planta, exterior y meteorología

Con el dominio fijo y el backend multiusuario ya en producción, el siguiente bloque de trabajo apunta a que la app sea más útil planta a planta, no solo dispositivo a dispositivo. Son cuatro piezas relacionadas pero independientes; se documentan juntas aquí porque comparten el mismo modelo de datos de partida (`Device`/`Location`), pero se construyen y se despliegan en fases separadas.

**1. Catálogo de tipos de planta con valores por defecto — construido.** Al editar un dispositivo, el usuario elige un tipo de planta (tabla `plant_types`, doce entradas de partida: tomate, hierbas aromáticas, hoja verde, suculenta/cactus, helecho, monstera, potos, rosal, lavanda, orquídea, ficus, y un "personalizado" que replica los valores por defecto que ya tenía `macetero01`) que rellena los umbrales de cuidado (`Configuración persistente y editable`, más arriba) como punto de partida editable, no como un valor fijo. Los valores del catálogo son ilustrativos — específicos del calibrado de este sensor capacitivo, no un dato agronómico validado — pensados para refinarse con el uso real y, más adelante, con el punto 4. Esta pieza es también la que forzó a migrar la configuración de riego de Node-RED a Postgres (ver más arriba), porque sin eso no había dónde aplicar los valores por defecto ni forma de editarlos desde la app.

**2. Interior / exterior como atributo del dispositivo.** Un campo más junto al tipo de planta. No cambia nada del ciclo de riego por sí solo — es la bandera que decide si se aplica el punto 3 (meteorología) a ese macetero en concreto. Las plantas de interior no la necesitan y no deberían pagar ese coste (una llamada a una API externa) en cada ciclo de decisión.

**3. Integración con una API meteorológica para exteriores.** Para los dispositivos marcados como exterior, el ciclo de riego (`Ciclo cerrado de riego`, más arriba) consulta la previsión antes de regar en automático — típicamente para posponer el riego si hay lluvia prevista en las próximas horas. Candidata recomendada: [Open-Meteo](https://open-meteo.com/), porque no exige clave de API ni tarjeta de crédito (coherente con el resto de la plataforma, que ha evitado dependencias de pago salvo el dominio) y tiene límites de uso generosos para un único punto geográfico consultado con poca frecuencia. Requiere guardar una ubicación geográfica (latitud/longitud, o una dirección que se resuelva una vez) en `Location`, que hoy no existe en el modelo.

**4. Aprendizaje automático por tipo de planta.** La pieza más ambiciosa y la que más depende de las otras tres: ajustar con el tiempo los umbrales del catálogo del punto 1 a partir de los datos históricos reales de InfluxDB (humedad, temperatura, riegos ejecutados) agrupados por tipo de planta, en vez de dejarlos fijos para siempre. Deliberadamente la última en construirse, por dos motivos: necesita que ya exista el campo "tipo de planta" del punto 1 para poder agrupar datos por planta, y necesita semanas o meses de histórico acumulado por tipo antes de que cualquier ajuste automático tenga sentido estadístico — construirla antes de tener datos suficientes sería optimizar sobre ruido. La primera versión razonable no es necesariamente un modelo entrenado: empezar por un ajuste estadístico simple (medias/percentiles observados por tipo de planta) y solo subir a un modelo más sofisticado si ese primer paso se queda corto, es el mismo criterio de "la solución más simple que resuelve el problema real" que ya ha guiado el resto del proyecto (ver por ejemplo la elección de PostgreSQL frente a alternativas más complejas, arriba).

**Orden de construcción recomendado**: 1 → 2 → 3, con 4 empezando en paralelo a 3 solo para *recopilar* datos etiquetados por tipo de planta (sin ajustar nada todavía), y su primera versión funcional (el ajuste estadístico simple) llegando después de acumular histórico real. Construir 3 o 4 antes que 1 obligaría a rehacerlos en cuanto exista el catálogo.

## Limitaciones conocidas y trabajo pendiente

- Sin *rate limiting* en `/api/auth/register` ni `/api/auth/login`: con `api.ecoplantplatform.com` permanentemente accesible (a diferencia del Quick Tunnel de `/ui`, que solo está arriba durante una demo puntual), esto ya es una puerta abierta 24/7 a intentos de fuerza bruta o registro masivo, no solo un riesgo ocasional. Mismo tipo de limitación que la falta de CRL en mTLS — documentada, pendiente de resolver, y con más motivo ahora que antes.
- Un dispositivo desenganchado no se puede volver a reclamar sin que un administrador rote un código nuevo (el código es de un solo uso y no se restaura solo). Asumible con un único operador; habría que revisarlo si algún día hay varios administradores.
- Sin verificación de email ni recuperación de contraseña por correo — vive como mejora futura, no como parte de esta iteración.
- No hay lista de revocación (CRL): revocar un dispositivo comprometido de forma robusta exige hoy regenerar la CA, no solo quitarlo de la ACL.
- Un solo `push_token` por usuario, no por dispositivo/instalación: si la misma cuenta se usa en dos móviles, solo el último en iniciar sesión recibe notificaciones. Asumible con un único usuario real; una tabla aparte sería la evolución si el proyecto gana usuarios de verdad.
- El acceso a Node-RED, Grafana e InfluxDB dentro de la red local es por HTTP sin cifrar — asumible por ser una red aislada. Solo el dashboard (`/ui`) sale al exterior, y lo hace vía Cloudflare Tunnel (HTTPS gestionado por Cloudflare) más un proxy local que bloquea todo lo demás; Grafana e InfluxDB nunca se exponen a internet.
- Las confirmaciones de riego no distinguen si la orden fue manual o automática, de modo que un riego manual también bloquea el automático durante 24 horas. Es el comportamiento deseado hoy, pero convendría diferenciarlo si se quieren políticas distintas.
- No hay sensor de nivel de depósito, por lo que la plataforma no puede saber si hay agua disponible antes de ordenar un riego. Es la principal carencia funcional: la bomba puede llegar a trabajar en seco.
- El riego se dosifica por **tiempo**, no por volumen. Un caudalímetro permitiría dosificación volumétrica real y detectar la degradación de la bomba (menos caudal para el mismo tiempo de funcionamiento).
- La calibración del sensor de humedad está fijada en el firmware. Recalibrar exige recompilar y flashear, cuando conceptualmente es un parámetro de configuración más.
- No hay actualización de firmware por red (OTA). Con el 73 % de la flash ocupada tras incorporar TLS, habilitarla requerirá ajustar el esquema de particiones.
