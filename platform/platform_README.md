# Plataforma

Instalación y configuración del stack del servidor sobre Raspberry Pi (Debian Bookworm, ARM64).

Componentes: **Mosquitto** (broker MQTT) · **Node-RED** (lógica y dashboard) · **InfluxDB 2.x** (series temporales) · **Grafana** (visualización).

---

## 1. Mosquitto

```bash
sudo apt install -y mosquitto mosquitto-clients
```

Configuración en `/etc/mosquitto/conf.d/iot.conf`:

```
listener 1883
allow_anonymous true
```

```bash
sudo systemctl enable --now mosquitto
```

> **Advertencia**: `allow_anonymous true` no requiere credenciales. Es aceptable únicamente en una red local aislada. Antes de exponer el broker a internet hay que configurar autenticación con `password_file` y ACLs por dispositivo.

Comprobación:

```bash
mosquitto_sub -h localhost -t "maceteros/#" -v
```

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

### Persistencia del contexto

Los parámetros de riego se guardan en el *global context*. Sin esta configuración se pierden en cada reinicio. En `~/.node-red/settings.js`:

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

### Importar los flujos

Menú → *Import* → pegar el contenido de [`nodered/flows.json`](nodered/flows.json).

Tras importar hay que revisar: la dirección del broker MQTT (debe ser `localhost`), y el token, organización y bucket del nodo de InfluxDB.

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

Accesible en `http://<ip-raspberry>:3000` (credenciales iniciales `admin` / `admin`).

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
mosquitto_pub -h localhost -t "maceteros/test01/sensores" \
  -m '{"device_id":"test01","humedad_suelo":42,"temp_aire":22.5,"presion":1013.2,"estado":"OK"}'
```

El dato debe aparecer en el bucket `macetero_iot` de InfluxDB y, por tanto, en Grafana.

---

## Puertos

| Servicio | Puerto |
|---|---|
| Mosquitto | 1883 |
| Node-RED | 1880 |
| InfluxDB | 8086 |
| Grafana | 3000 |

Ninguno de estos servicios tiene autenticación configurada actualmente. No deben exponerse fuera de la red local sin resolver antes ese punto.
