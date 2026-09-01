# Plataforma

Instalación y configuración del stack del servidor sobre Raspberry Pi (Debian Bookworm, ARM64).

Componentes: **Mosquitto** (broker MQTT) · **Node-RED** (lógica y dashboard) · **InfluxDB 2.x** (series temporales) · **Grafana** (visualización).

---

## 1. Mosquitto

```bash
sudo apt install -y mosquitto mosquitto-clients
```

### Credenciales

Un usuario para la plataforma y uno por dispositivo:

```bash
sudo mosquitto_passwd -c /etc/mosquitto/passwd nodered     # -c crea el archivo
sudo mosquitto_passwd /etc/mosquitto/passwd macetero01     # sin -c: añade
```

> El flag `-c` **sobrescribe** el archivo. Solo se usa la primera vez.

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

Cada dispositivo nuevo requiere su usuario y su bloque de ACL correspondiente.

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

### Configuración final

En `/etc/mosquitto/conf.d/iot.conf`:

```
listener 8883
cafile /etc/mosquitto/certs/ca.crt
certfile /etc/mosquitto/certs/server.crt
keyfile /etc/mosquitto/certs/server.key
tls_version tlsv1.2

allow_anonymous false
password_file /etc/mosquitto/passwd
acl_file /etc/mosquitto/acl
```

```bash
sudo systemctl enable --now mosquitto
```

### Verificación

```bash
# Con TLS y credenciales: debe funcionar
mosquitto_sub -h 192.168.1.140 -p 8883 --cafile ~/certs/ca.crt \
  -u nodered -P '<password>' -t "maceteros/#" -v

# Sin cifrar: debe fallar (no hay listener en 1883)
mosquitto_sub -h 192.168.1.140 -p 1883 -u nodered -P '<password>' -t "maceteros/#" -v

# Un dispositivo leyendo topics ajenos: conecta, pero la ACL no entrega nada
mosquitto_sub -h 192.168.1.140 -p 8883 --cafile ~/certs/ca.crt \
  -u macetero01 -P '<password>' -t "maceteros/#" -v
```

> Al conectar hay que usar la **misma dirección** que figura en el certificado. Con `localhost` la validación del nombre falla aunque el broker responda.

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
| Certificado CA | `/etc/mosquitto/ca_certificates/ca.crt` |
| Verificar certificado del servidor | activado |
| Usuario / Contraseña | pestaña *Seguridad*, credenciales del usuario `nodered` |

En la configuración TLS hay que marcar **"Utilizar claves y certificados de archivos locales"** para poder indicar la ruta en lugar de subir el archivo. Los campos de certificado y clave de cliente quedan vacíos mientras no se implemente mTLS.

### Importar los flujos

Menú → *Import* → pegar el contenido de [`nodered/flows.json`](nodered/flows.json).

Tras importar hay que revisar: la configuración del broker MQTT (dirección, puerto TLS, ruta del certificado y credenciales), y el token, organización y bucket del nodo de InfluxDB.

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

## Verificación del stack completo

```bash
systemctl status mosquitto nodered influxdb grafana-server --no-pager
```

Prueba de extremo a extremo sin necesidad de hardware, publicando una lectura simulada:

```bash
mosquitto_pub -h 192.168.1.140 -p 8883 --cafile ~/certs/ca.crt \
  -u nodered -P '<password>' \
  -t "maceteros/test01/sensores" \
  -m '{"device_id":"test01","humedad_suelo":42,"temp_aire":22.5,"presion":1013.2,"estado":"OK"}'
```

El dato debe aparecer en el bucket `macetero_iot` de InfluxDB y, por tanto, en Grafana.

---

## Puertos

| Servicio | Puerto | Autenticación | Cifrado |
|---|---|---|---|
| Mosquitto | 8883 | usuario/contraseña + ACL | TLS 1.2 |
| Node-RED | 1880 | editor y dashboard separados | — |
| InfluxDB | 8086 | usuario/contraseña + token API | — |
| Grafana | 3000 | usuario/contraseña | — |

El puerto MQTT sin cifrar (1883) está cerrado. Los tres servicios web sirven por HTTP sin cifrar: es asumible en una red local aislada, pero exponerlos a internet requiere un reverse proxy con HTTPS delante.

---

## Copia de seguridad

Los siguientes elementos no se regeneran solos y conviene respaldarlos:

| Qué | Dónde |
|---|---|
| Flujos y credenciales de Node-RED | `~/.node-red/flows.json`, `~/.node-red/flows_cred.json` |
| Clave de cifrado de credenciales | `credentialSecret` en `settings.js` |
| Contexto persistente (parámetros de riego) | `~/.node-red/context/` |
| CA y certificados | `~/certs/` |
| Contraseñas y ACLs del broker | `/etc/mosquitto/passwd`, `/etc/mosquitto/acl` |
| Datos históricos | `/var/lib/influxdb/` |

La clave privada de la CA (`ca.key`) es el elemento más sensible del conjunto: quien la posea puede emitir certificados que los dispositivos aceptarán como legítimos.
