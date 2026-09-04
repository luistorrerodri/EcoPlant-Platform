# Plataforma

Instalación y configuración del stack del servidor sobre Raspberry Pi (Debian Bookworm, ARM64).

Componentes: **Mosquitto** (broker MQTT) · **Node-RED** (lógica y dashboard) · **InfluxDB 2.x** (series temporales) · **Grafana** (visualización) · **PostgreSQL** + **Backend API** (usuarios, ubicaciones, dispositivos).

---

## 1. Mosquitto

```bash
sudo apt install -y mosquitto mosquitto-clients
```

### ACLs

En `/etc/mosquitto/acl`:

```
# Plataforma: acceso completo al árbol de maceteros
user nodered
topic readwrite maceteros/#

# Dispositivo: solo sus propios topics
user macetero01
topic write maceteros/macetero01/sensores
topic write maceteros/macetero01/estado
topic read  maceteros/macetero01/comando
```

Cada dispositivo nuevo requiere su bloque de ACL correspondiente. El `user` de cada bloque ya no es una cuenta con contraseña propia (ver "Certificados de cliente (mTLS)" más abajo): con `use_identity_as_username` activado, Mosquitto toma este nombre directamente del **CN del certificado de cliente** presentado en el handshake TLS. Por eso el CN de cada certificado debe coincidir exactamente con el `user` de su bloque de ACL.

### Certificados TLS

Se crea una CA propia que firma el certificado del broker:

```bash
mkdir -p ~/certs && cd ~/certs

# CA (la clave se protege con contraseña y NO se copia al servidor)
openssl genrsa -des3 -out ca.key 2048
openssl req -new -x509 -days 3650 -key ca.key -out ca.crt

# Clave y petición de firma del servidor
openssl genrsa -out server.key 2048
openssl req -new -key server.key -out server.csr \
  -subj "/C=ES/ST=Alicante/L=Aspe/O=EcoPlant/CN=192.168.1.140"
```

**El archivo de extensiones es imprescindible.** Sin SAN, Node.js rechaza el certificado; con SAN únicamente de tipo `IP`, lo rechaza mbedTLS en el ESP32. La dirección debe figurar en ambas formas:

```bash
cat > server.ext << 'EOF'
subjectAltName = IP:192.168.1.140, DNS:192.168.1.140, DNS:raspberrypi, DNS:localhost
EOF

openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out server.crt -days 730 -extfile server.ext
```

Verificación antes de instalar:

```bash
openssl verify -CAfile ca.crt server.crt
openssl x509 -in server.crt -noout -text | grep -A1 "Subject Alternative Name"
```

Instalación:

```bash
sudo cp ca.crt server.crt server.key /etc/mosquitto/certs/
sudo chown root:mosquitto /etc/mosquitto/certs/*
sudo chmod 640 /etc/mosquitto/certs/*

# Copia legible por Node-RED (es un certificado público, no una clave)
sudo mkdir -p /etc/mosquitto/ca_certificates
sudo cp ca.crt /etc/mosquitto/ca_certificates/
sudo chmod 644 /etc/mosquitto/ca_certificates/ca.crt
```

### Certificados de cliente (mTLS)

Hasta aquí el broker demuestra su identidad al cliente (TLS del lado servidor). Falta el sentido contrario: que cada cliente demuestre la suya al broker, con un certificado propio firmado por la misma CA. Esto sustituye por completo al usuario/contraseña como mecanismo de autenticación — la identidad pasa a ser el **CN del certificado**, no una contraseña que se pueda filtrar.

**Genera estos certificados donde tengas `ca.key`, no en la Raspberry Pi** — la clave privada de la CA no reside en el servidor (ver más abajo), así que este paso no puede hacerse ahí.

```bash
mkdir -p ~/certs/clients && cd ~/certs/clients

# Un certificado de cliente por identidad: uno por cada dispositivo
# (CN = su DEVICE_ID) y uno para la propia plataforma (CN = nodered).
for cn in macetero01 nodered; do
  openssl genrsa -out "$cn.key" 2048
  openssl req -new -key "$cn.key" -out "$cn.csr" \
    -subj "/C=ES/ST=Alicante/L=Aspe/O=EcoPlant/CN=$cn"
  openssl x509 -req -in "$cn.csr" -CA ../ca.crt -CAkey ../ca.key -CAcreateserial \
    -out "$cn.crt" -days 730
  openssl verify -CAfile ../ca.crt "$cn.crt"
done
```

El CN debe coincidir exactamente con el `user` del bloque de ACL correspondiente (ver arriba). `macetero01.crt`/`macetero01.key` se embeben en el firmware de ese dispositivo como `CLIENT_CERT`/`CLIENT_KEY` (ver [`../firmware/README.md`](../firmware/README.md)) — no se copian a la Raspberry Pi, viajan directamente al ESP32. `nodered.crt`/`nodered.key` sí van al servidor, para que el propio Node-RED se autentique como cliente:

```bash
scp nodered.crt nodered.key piluis@192.168.1.140:~/certs/
ssh piluis@192.168.1.140 'chmod 600 ~/certs/nodered.key'
```

**Revocación**: sin una CRL (lista de revocación), "revocar" un dispositivo hoy significa quitar su bloque de `/etc/mosquitto/acl` — el certificado seguiría siendo válido para el TLS, pero sin ACL no podría publicar ni leer nada. Si la clave privada de un dispositivo se viera comprometida de verdad, la única garantía real es regenerar la CA. Añadir una CRL queda como mejora futura.

### Configuración final

En `/etc/mosquitto/conf.d/iot.conf`:

```
listener 8883
cafile /etc/mosquitto/certs/ca.crt
certfile /etc/mosquitto/certs/server.crt
keyfile /etc/mosquitto/certs/server.key
tls_version tlsv1.2

require_certificate true
use_identity_as_username true

allow_anonymous false
acl_file /etc/mosquitto/acl
```

`require_certificate true` obliga a todo cliente a presentar un certificado firmado por la CA configurada en `cafile` — sin él, el handshake TLS ni siquiera se completa. `use_identity_as_username true` hace que Mosquitto ignore cualquier usuario/contraseña que el cliente envíe y use en su lugar el CN del certificado como identidad para las ACLs. `password_file` ya no hace falta: la identidad la garantiza el certificado, no una contraseña.

```bash
sudo systemctl restart mosquitto
```

### Verificación

```bash
# Con certificado de cliente válido: debe funcionar (sin -u/-P, ya no se usan)
mosquitto_sub -h 192.168.1.140 -p 8883 --cafile ~/certs/ca.crt \
  --cert ~/certs/clients/nodered.crt --key ~/certs/clients/nodered.key \
  -t "maceteros/#" -v

# Sin certificado de cliente: debe fallar, el handshake TLS ni se completa
mosquitto_sub -h 192.168.1.140 -p 8883 --cafile ~/certs/ca.crt -t "maceteros/#" -v

# Sin cifrar: debe fallar (no hay listener en 1883)
mosquitto_sub -h 192.168.1.140 -p 1883 -t "maceteros/#" -v

# Certificado de un dispositivo leyendo topics ajenos: conecta (CN válido),
# pero la ACL no entrega nada fuera de maceteros/macetero01/*
mosquitto_sub -h 192.168.1.140 -p 8883 --cafile ~/certs/ca.crt \
  --cert ~/certs/clients/macetero01.crt --key ~/certs/clients/macetero01.key \
  -t "maceteros/#" -v
```

> Al conectar hay que usar la **misma dirección** que figura en el certificado del servidor. Con `localhost` la validación del nombre falla aunque el broker responda.

---

## 2. Node-RED

```bash
bash <(curl -sL https://raw.githubusercontent.com/node-red/linux-installers/master/deb/update-nodejs-and-nodered)
sudo systemctl enable --now nodered
```

Accesible en `http://<ip-raspberry>:1880` (editor) y `http://<ip-raspberry>:1880/ui` (dashboard).

### Paletas necesarias

Menú → *Manage palette* → *Install*:

- `node-red-dashboard`
- `node-red-contrib-influxdb`

### Autenticación

Node-RED distingue el acceso al editor del acceso al dashboard. Genera un hash por usuario:

```bash
node -e "console.log(require('/usr/lib/node_modules/node-red/node_modules/bcryptjs').hashSync(process.argv[1], 8));" '<password>'
```

En `~/.node-red/settings.js`:

```javascript
adminAuth: {
    type: "credentials",
    users: [{
        username: "admin",
        password: "<hash del admin>",
        permissions: "*"
    }]
},

httpNodeAuth: {
    user: "usuario",
    pass: "<hash del usuario de dashboard>"
},

credentialSecret: "<cadena larga y aleatoria>",
```

`credentialSecret` cifra las credenciales de los nodos (tokens, contraseñas) con una clave propia en lugar de una autogenerada por la instalación. Sin ella, un backup de los flujos no es restaurable en otra máquina. **Si se pierde, las credenciales guardadas hay que reintroducirlas a mano.** Se aplica en el siguiente Deploy.

### Persistencia del contexto

Los parámetros de riego se guardan en el *global context*. Sin esta configuración se pierden en cada reinicio:

```javascript
contextStorage: {
    default: {
        module: "localfilesystem"
    },
},
```

```bash
sudo systemctl restart nodered
```

### Conexión TLS al broker

En el nodo de configuración del broker MQTT:

| Campo | Valor |
|---|---|
| Servidor | `192.168.1.140` (no `localhost`: debe coincidir con el certificado) |
| Puerto | `8883` |
| Utilizar TLS | activado |

En la configuración TLS, con **"Utilizar claves y certificados de archivos locales"** marcado:

| Campo | Valor |
|---|---|
| Certificado CA | `/etc/mosquitto/ca_certificates/ca.crt` |
| Certificado | `/home/piluis/certs/nodered.crt` |
| Clave privada | `/home/piluis/certs/nodered.key` |
| Verificar certificado del servidor | activado |

Con mTLS, la pestaña *Seguridad* del broker (usuario/contraseña) queda vacía: la identidad de Node-RED ante el broker la demuestra el certificado de cliente, no una credencial. Rutas locales — nada de esto se sube al repositorio; `flows.json` solo guarda las rutas de archivo, no el contenido de la clave.

### Importar los flujos

Menú → *Import* → pegar el contenido de [`nodered/flows.json`](nodered/flows.json).

Tras importar hay que revisar: la configuración del broker MQTT (dirección, puerto TLS, ruta del certificado y credenciales), el token, organización y bucket del nodo de InfluxDB, y la cabecera `X-Internal-Token` del nodo `http request` que sondea `/api/internal/device-configs` (el valor real vive solo en `backend/.env` de la Pi — nunca se versiona, ver § "Catálogo de plantas y configuración de riego en Postgres").

---

## 3. InfluxDB 2.x

> El repositorio APT oficial de InfluxData falla la verificación GPG en Bookworm/ARM64 (`NO_PUBKEY DA61C26A0585BD3B`). La instalación desde el binario oficial es la vía fiable. Detalle en [`../docs/troubleshooting.md`](../docs/troubleshooting.md).

```bash
cd ~
curl -L -O https://download.influxdata.com/influxdb/releases/influxdb2-2.9.1_linux_arm64.tar.gz
tar xvzf influxdb2-2.9.1_linux_arm64.tar.gz
sudo cp influxdb2-2.9.1/influxd /usr/local/bin/
influxd version
```

Usuario de sistema y directorio de datos:

```bash
sudo useradd -rs /bin/false influxdb
sudo mkdir -p /var/lib/influxdb
sudo chown influxdb:influxdb /var/lib/influxdb
```

Servicio en `/etc/systemd/system/influxdb.service`:

```ini
[Unit]
Description=InfluxDB OSS 2.x
After=network-online.target
Wants=network-online.target

[Service]
User=influxdb
Group=influxdb
LimitNOFILE=65536
ExecStart=/usr/local/bin/influxd --bolt-path=/var/lib/influxdb/influxd.bolt --engine-path=/var/lib/influxdb/engine
KillMode=control-group
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now influxdb
```

### Configuración inicial

En `http://<ip-raspberry>:8086`, completar el asistente (opción *Configure Later* en el último paso; Telegraf no se utiliza) y crear:

- **Organización**: el nombre exacto debe coincidir con el configurado en Node-RED y Grafana, respetando mayúsculas y espacios.
- **Bucket**: `macetero_iot`

Después, en *Load Data → API Tokens*, generar un token con permisos de lectura y escritura sobre ese bucket. Se usa tanto en Node-RED (escritura) como en Grafana (lectura).

---

## 4. Grafana

El repositorio APT de Grafana sí funciona correctamente en este sistema:

```bash
sudo apt install -y apt-transport-https software-properties-common wget gnupg
sudo mkdir -p /etc/apt/keyrings/
wget -q -O - https://apt.grafana.com/gpg.key | gpg --dearmor | sudo tee /etc/apt/keyrings/grafana.gpg > /dev/null
echo "deb [signed-by=/etc/apt/keyrings/grafana.gpg] https://apt.grafana.com stable main" | sudo tee /etc/apt/sources.list.d/grafana.list
sudo apt update
sudo apt install -y grafana
sudo systemctl enable --now grafana-server
```

Accesible en `http://<ip-raspberry>:3000` (credenciales iniciales `admin` / `admin`, que Grafana obliga a cambiar en el primer acceso).

### Endurecimiento

En `/etc/grafana/grafana.ini`:

```ini
[users]
allow_sign_up = false

[auth.anonymous]
enabled = false
```

```bash
sudo systemctl restart grafana-server
```

### Fuente de datos

*Connections → Data sources → Add data source → InfluxDB*:

| Campo | Valor |
|---|---|
| Query Language | **Flux** (no InfluxQL; InfluxDB 2.x lo requiere) |
| URL | `http://localhost:8086` |
| Organization | el nombre exacto de la organización |
| Token | el token generado en InfluxDB |
| Default Bucket | `macetero_iot` |

*Save & test* debe confirmar la conexión y el número de buckets encontrados.

### Dashboard

*Dashboards → New → Import* → pegar [`grafana/dashboard.json`](grafana/dashboard.json).

Consulta Flux de ejemplo:

```flux
from(bucket: "macetero_iot")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r._measurement == "sensores")
  |> filter(fn: (r) => r._field == "humedad_suelo")
  |> filter(fn: (r) => r.device_id == "macetero01")
```

> El campo `estado` es de tipo texto. Incluirlo en una consulta con función de agregación `mean` produce el error `unsupported input type for mean aggregate: string`. Para consultarlo hay que usar `last` y hacerlo en una query separada de los campos numéricos.

---

## 5. Acceso remoto (demo pública bajo demanda)

El objetivo es poder enseñar el dashboard desde cualquier sitio sin exponer nada permanentemente: nada de abrir puertos en el router, nada corriendo salvo cuando se decide hacer una demo. La solución combina dos piezas:

- **Caddy**, como proxy local que solo deja pasar `/ui` (el dashboard de Node-RED) y bloquea todo lo demás — el editor, la API de administración, InfluxDB, Grafana.
- **Cloudflare Tunnel** (`cloudflared`, modo *Quick Tunnel*), que da una URL pública HTTPS sin necesidad de dominio propio ni de tocar el router: la Pi abre una conexión saliente hacia Cloudflare, nunca al revés.

### Caddy

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy
```

En `/etc/caddy/Caddyfile`:

```
:8080 {
	bind 127.0.0.1 192.168.1.140

	@dashboard path /ui /ui/*
	handle @dashboard {
		reverse_proxy localhost:1880
	}
	handle {
		respond 404
	}
}
```

```bash
sudo caddy reload --config /etc/caddy/Caddyfile
```

Dos detalles que costó descubrir (ver [`../docs/troubleshooting.md`](../docs/troubleshooting.md#14-caddy-sirviendo-en-tls-y-bloqueando-todo-por-el-filtro-de-host)):

- Sin el prefijo `:8080` a secas (sin IP delante), Caddy asume HTTPS con su propia CA interna por defecto — de ahí que se use `bind 127.0.0.1` en vez de escribir `127.0.0.1:8080`, que además de fijar la interfaz de escucha, Caddy lo interpreta también como un filtro sobre la cabecera `Host`.
- `httpNodeAuth` (usuario/contraseña del dashboard, ya configurado en Node-RED) se mantiene detrás de Caddy sin cambios — sigue pidiendo login incluso llegando por el túnel.

`bind` acepta varias direcciones: además de `127.0.0.1` (para `cloudflared`, que corre en la propia Pi), se añadió la IP de la Pi en la LAN (`192.168.1.140`) para que la app móvil pueda hablar con la API directamente por WiFi durante el desarrollo, sin depender del túnel. Sigue sin haber nada expuesto a internet (no hay *port-forwarding* en el router) — es una extensión deliberada del mismo nivel de confianza que ya tenían Node-RED, Grafana e InfluxDB.

Verificación desde la propia Pi antes de tocar el túnel:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/ui       # 401 (pide credenciales) o 200 con -u usuario:pass
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/         # 404 — el editor, bloqueado
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/flows    # 404 — la API de administración, bloqueada
```

### Cloudflare Tunnel

```bash
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb
sudo dpkg -i cloudflared.deb
```

Se deja como un servicio que se enciende y apaga a mano — **sin `enable`**, para que no arranque solo con la Pi y no quede nada expuesto salvo cuando se decide mostrar el proyecto. En `/etc/systemd/system/cloudflared-demo.service`:

```ini
[Unit]
Description=Cloudflare Quick Tunnel (demo bajo demanda)
After=network-online.target caddy.service
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/cloudflared tunnel --url http://localhost:8080
Restart=on-failure
User=piluis

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
```

**Para hacer una demo:**

```bash
sudo systemctl start cloudflared-demo
sudo journalctl -u cloudflared-demo --no-pager -l | grep -i "trycloudflare.com"
```

La segunda línea saca la URL pública (algo como `https://palabras-al-azar.trycloudflare.com`) — cambia cada vez que se arranca el servicio, porque un *Quick Tunnel* no tiene hostname fijo (para eso haría falta un *named tunnel* con un dominio propio dado de alta en Cloudflare, ver nota abajo). Se comparte `<url>/ui`.

**Para cerrarla:**

```bash
sudo systemctl stop cloudflared-demo
```

**Limitación conocida**: sin cuenta de Cloudflare ni dominio propio, la URL de cada demo es distinta e impredecible — vale para "mira, te enseño el proyecto ahora mismo", no para dejar un enlace fijo en un CV o portfolio. Para eso está el túnel con nombre de la siguiente sección.

### Túnel con nombre + dominio fijo

Para la app móvil (necesita una URL que no cambie nunca, tanto en casa como fuera) se añadió un segundo túnel, permanente: dominio propio (`ecoplantplatform.com`, comprado en **Cloudflare Registrar** — al estar en la misma cuenta que el túnel, el DNS se gestiona solo, sin los rodeos que hicieron falta al intentarlo primero con un dominio gratuito de terceros) + un túnel de Cloudflare **con nombre** (`ecoplant-pi`, creado desde el panel de **Zero Trust → Networks → Tunnels & Mesh**, no con `cloudflared tunnel login` — ese comando exige tener ya un dominio dado de alta y falla si la cuenta no tiene ninguno).

Instalación del conector en la Pi (token generado al crear el túnel en el panel):

```bash
sudo cloudflared service install <token>
```

Esto instala `cloudflared` como servicio systemd propio (`cloudflared.service`, distinto de `cloudflared-demo`), habilitado al arrancar — a diferencia del Quick Tunnel, este si tiene sentido que esté siempre activo, porque ahora hay una app de uso real detrás, no solo demos puntuales.

El enrutado (qué hostname va a qué servicio local) se configura en **Zero Trust → Networks → Tunnels & Mesh → `ecoplant-pi` → Published application routes**: `api.ecoplantplatform.com` → `http://127.0.0.1:8080` (Caddy). Se usa `127.0.0.1` explícito y no `localhost` — con `localhost`, `cloudflared` puede resolver a `::1` (IPv6) en vez de a la IP donde escucha Caddy, dando `502` de forma intermitente y confusa. Se reservó `api.` para el backend a propósito, dejando la raíz del dominio y `www` libres para una futura landing page del proyecto.

**Bug real encontrado al verificar esto**: tras un reinicio de la Pi, Caddy no volvía a arrancar (condición de carrera con la red al asignar la IP de la LAN) — ver [`../docs/troubleshooting.md`](../docs/troubleshooting.md#19-caddy-no-arranca-tras-un-reinicio-de-la-pi-condición-de-carrera-con-la-red) para el diagnóstico completo y el arreglo (`override.conf` de systemd con `network-online.target` + `Restart=on-failure`).

---

## 6. Backend API

Servicio nuevo y aditivo (FastAPI + PostgreSQL) que añade usuarios, ubicaciones y permisos — el modelo *usuario → ubicación → dispositivo* — por delante de la plataforma existente. No sustituye nada: Node-RED sigue decidiendo cuándo regar y sirviendo su propio dashboard; este servicio es la capa de autenticación y API que se monta al lado. Detalle de diseño en [`../docs/architecture.md`](../docs/architecture.md), instrucciones de desarrollo en [`../backend/README.md`](../backend/README.md).

### PostgreSQL

```bash
sudo apt install -y postgresql
sudo -u postgres psql -c "CREATE ROLE ecoplant WITH LOGIN PASSWORD '<password>';"
sudo -u postgres psql -c "CREATE DATABASE ecoplant OWNER ecoplant;"
```

### Certificado de cliente (mTLS) para el backend

Mismo procedimiento que para `nodered`/`macetero01` (ver "Certificados de cliente (mTLS)" más arriba), con CN `backend-api`:

```bash
cd ~/certs/clients
openssl genrsa -out backend-api.key 2048
openssl req -new -key backend-api.key -out backend-api.csr -subj "/C=ES/ST=Alicante/L=Aspe/O=EcoPlant/CN=backend-api"
openssl x509 -req -in backend-api.csr -CA ../ca.crt -CAkey ../ca.key -CAcreateserial -out backend-api.crt -days 730
openssl verify -CAfile ../ca.crt backend-api.crt
mv backend-api.crt backend-api.key ~/certs/
chmod 600 ~/certs/backend-api.key
```

Añadir a `/etc/mosquitto/acl`:

```
# Backend API: publica comandos de riego para dispositivos reclamados
# y consulta estado/presencia (el histórico se lee de InfluxDB, no MQTT)
user backend-api
topic write maceteros/+/comando
topic read  maceteros/+/estado
topic read  maceteros/+/sensores
```

```bash
sudo systemctl restart mosquitto
```

### Token de InfluxDB (solo lectura)

En `http://<ip-raspberry>:8086` → *Load Data → API Tokens → Generate API Token → Custom API Token*: nombre `backend-api-readonly`, marcar **Read** (no Write) sobre el bucket `macetero_iot`. Distinto del token de Node-RED, que sí tiene escritura.

### Despliegue

```bash
git clone https://github.com/luistorrerodri/EcoPlant-Platform.git ~/EcoPlant-Platform
cd ~/EcoPlant-Platform/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # rellenar con los valores reales (ver backend/README.md)
alembic upgrade head
```

Servicio systemd, **habilitado al arrancar** (a diferencia de `cloudflared-demo`: este servicio escucha solo en `127.0.0.1`, igual que Node-RED e InfluxDB, que también arrancan solos — lo que decide qué es alcanzable desde fuera es Caddy y el túnel, no si este servicio está vivo):

```bash
sudo nano /etc/systemd/system/ecoplant-backend.service
```

```ini
[Unit]
Description=EcoPlant Platform - Backend API (FastAPI)
After=network-online.target postgresql.service mosquitto.service
Wants=network-online.target

[Service]
Type=simple
User=piluis
WorkingDirectory=/home/piluis/EcoPlant-Platform/backend
EnvironmentFile=/home/piluis/EcoPlant-Platform/backend/.env
ExecStart=/home/piluis/EcoPlant-Platform/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ecoplant-backend
```

### Caddyfile

Nuevo bloque junto al de `/ui`, dentro del mismo `http://127.0.0.1:8080 { ... }`:

```
@api path /api/*
handle @api {
	reverse_proxy localhost:8000
}
```

```bash
sudo caddy reload --config /etc/caddy/Caddyfile
```

Con esto, `/api/docs` (Swagger) queda accesible por el mismo camino que `/ui` — local, por Caddy, y a través del Quick Tunnel cuando está levantado — mientras que el resto (editor de Node-RED, InfluxDB, Grafana, la propia base de datos) nunca se expone.

### Verificación

```bash
curl -s http://localhost:8000/api/health                                   # directo al backend
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/api/health   # a traves de Caddy, debe dar 200
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/flows        # debe seguir dando 404
sudo journalctl -u ecoplant-backend -n 20 --no-pager                        # confirmar que conecto a Postgres y MQTT sin errores
```

Con `cloudflared-demo` levantado, `<url>/api/docs` debe cargar el Swagger desde fuera, y permitir registrarse, crear una ubicación, reclamar un dispositivo y regarlo — igual que en local.

### Catálogo de plantas y configuración de riego en Postgres

La configuración de riego (`humedadMin`, `horaInicio`, `horaFin`, `duracionRiegoMs`) que hasta ahora vivía solo en el contexto de Node-RED (§2, "Persistencia del contexto") pasa a ser columnas de `devices` en Postgres, editables desde la app. Node-RED deja de ser la fuente de verdad y pasa a sondear al backend cada 60s — ver `docs/architecture.md` § "Configuración persistente y editable" para el porqué del diseño. Este cambio se despliega en dos partes, **en este orden**, porque la segunda depende de que la primera ya esté sirviendo los valores correctos:

**1. Backend (código versionado, despliegue normal):**

```bash
cd ~/EcoPlant-Platform
git pull
cd backend
source .venv/bin/activate
pip install -r requirements.txt   # sin cambios de dependencias en esta iteración, por si acaso
```

Añadir al `.env` (no está en `.env.example` por defecto — hay que generarlo, ver el comentario de esa sección en `backend/.env.example`):

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
# pega el resultado como INTERNAL_API_TOKEN=... en backend/.env
```

```bash
alembic upgrade head
sudo systemctl restart ecoplant-backend
```

**Verificar antes de tocar nada más** (el objetivo es que este paso sea un no-op de comportamiento — si `macetero01` no sale exactamente así, parar aquí):

```bash
sudo -u postgres psql -d ecoplant -c \
  "SELECT device_id, humedad_min, hora_inicio, hora_fin, duracion_riego_ms FROM devices WHERE device_id = 'macetero01';"
# debe dar exactamente: 36 | 8 | 21 | 9000

curl -H "X-Internal-Token: <el token de arriba>" http://localhost:8000/api/internal/device-configs
# {"macetero01": {"humedadMin": 36, "horaInicio": 8, "horaFin": 21, "duracionRiegoMs": 9000}}

curl -H "X-Internal-Token: token-incorrecto" http://localhost:8000/api/internal/device-configs
# 401
```

**2. Node-RED (manual, en el editor — `flows.json` del repo es solo referencia, no se despliega solo):**

En la misma pestaña de flujo, añadir sin tocar el nodo **"Decisión riego"**:

- `inject` → repetir cada 60s, y marcar "Inject once after 0.1 seconds" para que cargue en cuanto se hace Deploy.
- `http request` → método `GET`, URL `http://localhost:8000/api/internal/device-configs`, cabecera `X-Internal-Token: <mismo token del .env>`, "Return" = objeto JSON parseado.
- `function`, nómbralo **"Aplicar config recibida"**:
  ```javascript
  if (msg.statusCode !== 200) {
      node.warn('No se pudo actualizar config_maceteros: HTTP ' + msg.statusCode);
      return null;
  }
  global.set('config_maceteros', msg.payload);
  node.status({fill: "green", shape: "dot", text: "actualizado " + new Date().toLocaleTimeString()});
  return msg;
  ```
  Cablear: `inject → http request → Aplicar config recibida`. Un `debug` a la salida ayuda a verificar en el primer despliegue (se puede desactivar después).

Después, para que el dashboard no pelee con el sondeo escribiendo `config_maceteros` a la vez: desconecta (no borres) el cable del slider de humedad hacia el nodo "Guardar Umbral", y el de los desplegables de horario hacia "Guardar horario" — los nodos "Leer umbral actual"/"Leer horario actual" se quedan como están, así el dashboard sigue mostrando el valor vigente, solo que de solo lectura. Deshabilita también (clic derecho → Disable) el nodo "Init config maceteros": con el sondeo cargando en cada Deploy, ese bootstrap fijo para `macetero01` ya no hace falta, pero se deja ahí, inerte, como red de seguridad reactivable a mano si el backend no responde en el arranque.

Deploy, y confirmar en el panel de debug que "Aplicar config recibida" da exactamente los mismos valores que el `curl` de arriba. Dejar correr al menos un ciclo completo sin tocar nada más y confirmar que no se dispara ningún riego inesperado — el sistema debe comportarse igual que antes de este cambio.

### Interior / exterior por dispositivo

Columna `environment` en `devices` (roadmap punto 2, `docs/architecture.md`). A diferencia del catálogo de plantas, esta migración no toca Node-RED ni necesita ningún token nuevo — es puramente aditiva y nadie la lee todavía:

```bash
cd ~/EcoPlant-Platform && git pull
cd backend && alembic upgrade head
sudo systemctl restart ecoplant-backend
curl -s http://localhost:8000/api/health
```

### Meteorología para riego exterior

Roadmap punto 3 (`docs/architecture.md`). Añade `latitude`/`longitude` a `locations` y un `lluviaPrevista` calculado (Open-Meteo) al mismo objeto que ya sirve `GET /api/internal/device-configs` — sin token nuevo, sin cambios en el poller de Node-RED.

**1. Backend**, igual que los pasos anteriores:

```bash
cd ~/EcoPlant-Platform && git pull
cd backend && alembic upgrade head
sudo systemctl restart ecoplant-backend
curl -s http://localhost:8000/api/health
```

**Verificar antes de tocar Node-RED**: `macetero01` no tiene `environment` fijado, así que debe seguir dando `lluviaPrevista: false` — es el chequeo de no-regresión:

```bash
curl -s -H "X-Internal-Token: <token>" http://localhost:8000/api/internal/device-configs
```

Para probar el cálculo real: `PATCH /api/locations/{id}` con unas coordenadas bajo lluvia de verdad ahora mismo (comprobable en cualquier web del tiempo) y `PATCH /api/devices/{id}` con `{"environment": "exterior"}` en un dispositivo de prueba apuntando a esa ubicación — el siguiente `curl` de arriba debe dar `lluviaPrevista: true`. Deshacer ambos cambios de prueba después.

**2. Node-RED (manual, en el editor)** — dos líneas dentro de **"Decisión riego"**, sin tocar nada más de la función. Justo después de `let haPasadoTiempo = ...`:

```javascript
let sinLluviaPrevista = !cfg.lluviaPrevista;
```

Y en el `if` final, añadir la condición al final:

```javascript
if (necesitaRiego && dentroHorario && haPasadoTiempo && segundosDesdeOrden > 60 && sinLluviaPrevista) {
```

`!cfg.lluviaPrevista` (no `=== false`) es a propósito: si la clave todavía no ha llegado (config vieja, redeploy en curso), se trata como "sin lluvia prevista" — nunca bloquea el riego por un dato que falta.

**Probar la rama de "no regar por lluvia" sin esperar a que llueva**: un nodo `inject` desechable que fuerce `global.get('config_maceteros').macetero01.lluviaPrevista = true` en memoria (no toca Postgres, se autocorrige solo en el siguiente sondeo de 60s), seguido de una lectura de humedad simulada por debajo del umbral. Confirmar en el debug que "Decisión riego" no dispara `REGAR`. Borrar el nodo de prueba (no solo desactivarlo) y hacer Deploy otra vez.

**3. Actualizar el snapshot de `flows.json`**: el archivo del repo lleva desde el roadmap punto 1 sin reflejar los cambios hechos a mano en el editor (poller, sliders desconectados, init deshabilitado, y ahora esto). En vez de parchear el archivo a mano, hacer un *Export* completo desde el propio Node-RED (menú → Export → todo el flujo → copiar) y sobrescribir `platform/nodered/flows.json` entero, para que vuelva a ser un reflejo fiel del estado real.

---

## Verificación del stack completo

```bash
systemctl status mosquitto nodered influxdb grafana-server --no-pager
```

Prueba de extremo a extremo sin necesidad de hardware, publicando una lectura simulada:

```bash
mosquitto_pub -h 192.168.1.140 -p 8883 --cafile ~/certs/ca.crt \
  --cert ~/certs/clients/nodered.crt --key ~/certs/clients/nodered.key \
  -t "maceteros/test01/sensores" \
  -m '{"device_id":"test01","humedad_suelo":42,"temp_aire":22.5,"presion":1013.2,"estado":"OK"}'
```

El dato debe aparecer en el bucket `macetero_iot` de InfluxDB y, por tanto, en Grafana.

---

## Puertos

| Servicio | Puerto | Autenticación | Cifrado |
|---|---|---|---|
| Mosquitto | 8883 | certificado de cliente (mTLS) + ACL | TLS 1.2 |
| Node-RED | 1880 | editor y dashboard separados | — |
| InfluxDB | 8086 | usuario/contraseña + token API | — |
| Grafana | 3000 | usuario/contraseña | — |
| Backend API | 8000 | JWT (registro/login propios) | — |
| PostgreSQL | 5432 | usuario/contraseña, solo `127.0.0.1` | — |
| Caddy | 8080 | delega en cada servicio proxied | — |

El puerto MQTT sin cifrar (1883) está cerrado. Los servicios web (Node-RED, InfluxDB, Grafana, Backend API, Caddy) hablan HTTP sin cifrar entre sí en `127.0.0.1`: asumible porque nada de eso escucha en la red, solo en loopback. Lo único que sale de la Pi es lo que Caddy reenvía explícitamente (`/ui`, `/api/*`) a través del Cloudflare Tunnel, con TLS gestionado por Cloudflare — ver "Acceso remoto" más arriba.

---

## Copia de seguridad

Los siguientes elementos no se regeneran solos y conviene respaldarlos:

| Qué | Dónde |
|---|---|
| Flujos y credenciales de Node-RED | `~/.node-red/flows.json`, `~/.node-red/flows_cred.json` |
| Clave de cifrado de credenciales | `credentialSecret` en `settings.js` |
| Contexto persistente (parámetros de riego) | `~/.node-red/context/` |
| CA y certificado del servidor | `~/certs/` en la Pi (`ca.key` cifrada con contraseña) |
| Certificados de cliente (Node-RED, backend, por dispositivo) | `~/certs/clients/` y `~/certs/{nodered,backend-api}.{crt,key}` en la Pi |
| ACLs del broker | `/etc/mosquitto/acl` |
| Datos históricos | `/var/lib/influxdb/` |
| Base de datos de usuarios/ubicaciones/dispositivos | `pg_dump ecoplant` (PostgreSQL) |
| Variables de entorno del backend | `backend/.env` (fuera del repo, gitignored) |

La clave privada de la CA (`ca.key`) es el elemento más sensible del conjunto: quien la posea puede emitir certificados que los dispositivos aceptarán como legítimos. Vive en la propia Pi, cifrada con una contraseña que solo conoce el operador — mitiga que alguien robe el archivo y lo use directamente, pero no es lo mismo que mantenerla en una máquina totalmente separada del servidor; moverla fuera de la Pi queda como mejora de seguridad pendiente.
