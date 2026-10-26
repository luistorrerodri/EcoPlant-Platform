#!/usr/bin/env bash
# Copia de seguridad completa de EcoPlant en la Raspberry Pi.
#
# Genera UN archivo cifrado (AES-256) en /tmp con todo lo que no se regenera
# solo: bases de datos, flujos de Node-RED, certificados y CA, ACLs, .env, etc.
# No lo guarda en la Pi: lo recoge el PC con backup-from-pi.ps1 y lo borra.
#
# Uso (en la Pi):  sudo bash ~/EcoPlant-Platform/platform/backup/pi-backup.sh
# Pide la contraseña de cifrado dos veces. SIN ella el archivo no se puede abrir.

set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Ejecuta con sudo: sudo bash $0" >&2
  exit 1
fi

cd /tmp  # evita avisos de "could not change directory" al lanzar comandos como postgres

OWNER="${SUDO_USER:-piluis}"
PI_HOME="$(getent passwd "$OWNER" | cut -d: -f6)"
REPO="$PI_HOME/EcoPlant-Platform"
STAMP="$(date +%Y%m%d-%H%M)"
OUT="/tmp/ecoplant-backup-$STAMP.tar.gz.enc"
STAGE="$(mktemp -d /tmp/ecoplant-backup-stage.XXXXXX)"
chmod 700 "$STAGE"

INFLUX_STOPPED=0
cleanup() {
  # Pase lo que pase, InfluxDB no puede quedarse parado.
  if [[ $INFLUX_STOPPED -eq 1 ]]; then
    systemctl start influxdb || echo "AVISO: no se pudo reiniciar influxdb, hazlo a mano" >&2
  fi
  rm -rf "$STAGE"
}
trap cleanup EXIT

read -rsp "Contraseña de cifrado de la copia: " PASS; echo
read -rsp "Repítela: " PASS2; echo
if [[ -z "$PASS" || "$PASS" != "$PASS2" ]]; then
  echo "Las contraseñas no coinciden (o están vacías). Abortado." >&2
  exit 1
fi
export BACKUP_PASS="$PASS"
unset PASS PASS2

mkdir -p "$STAGE/files"
SKIPPED=()

# Copia una ruta (si existe) conservando permisos y propietarios, bajo files/<ruta>.
add_path() {
  local src="$1"; shift
  if [[ -e "$src" ]]; then
    tar -C / -cf - "$@" "${src#/}" | tar -C "$STAGE/files" -xpf -
  else
    SKIPPED+=("$src")
  fi
}

echo "==> PostgreSQL"
sudo -u postgres pg_dump -Fc ecoplant > "$STAGE/postgres-ecoplant.dump"
sudo -u postgres pg_dumpall --globals-only > "$STAGE/postgres-globals.sql"

echo "==> InfluxDB (se para unos segundos para copiar los datos de forma consistente)"
if [[ -d /var/lib/influxdb ]]; then
  systemctl stop influxdb
  INFLUX_STOPPED=1
  tar -C / -czf "$STAGE/influxdb.tar.gz" var/lib/influxdb
  systemctl start influxdb
  INFLUX_STOPPED=0
else
  SKIPPED+=("/var/lib/influxdb")
fi

echo "==> Node-RED (sin node_modules: se reinstalan desde package.json)"
add_path "$PI_HOME/.node-red" --exclude=node_modules --exclude=.npm --exclude='*.backup'

echo "==> Certificados y CA"
add_path "$PI_HOME/certs"

echo "==> Mosquitto"
add_path /etc/mosquitto
add_path /etc/systemd/system/mosquitto.service.d

echo "==> Backend (.env) y servicios"
add_path "$REPO/backend/.env"
add_path /etc/systemd/system/ecoplant-backend.service
add_path /etc/systemd/system/cloudflared-demo.service
add_path /etc/systemd/system/influxdb.service
add_path /etc/systemd/system/nodered.service.d
add_path /etc/caddy/Caddyfile

echo "==> Grafana"
add_path /etc/grafana/grafana.ini
add_path /var/lib/grafana/grafana.db

cat > "$STAGE/MANIFEST.txt" <<EOF
Copia de seguridad EcoPlant — $(date -Is)
Host: $(hostname)
Alembic (backend): $(sudo -u postgres psql -At -d ecoplant -c 'select version_num from alembic_version' 2>/dev/null || echo desconocida)
Repo (commit): $(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo desconocido)

Contenido:
  postgres-ecoplant.dump   pg_dump -Fc de la base 'ecoplant'
  postgres-globals.sql     roles de PostgreSQL (pg_dumpall --globals-only)
  influxdb.tar.gz          /var/lib/influxdb completo (datos + bolt)
  files/                   resto de ficheros, con su ruta absoluta original

Rutas que no existían y se omitieron:
$(printf '  %s\n' "${SKIPPED[@]:-ninguna}")

Restauración: ver "Copia de seguridad" en platform/README.md.
EOF

echo "==> Comprimiendo y cifrando"
tar -C "$STAGE" -czf - . \
  | openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass env:BACKUP_PASS -out "$OUT"

echo "==> Verificando que se puede abrir"
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass env:BACKUP_PASS -in "$OUT" | tar -tzf - > /dev/null
unset BACKUP_PASS

chown "$OWNER":"$OWNER" "$OUT"
chmod 600 "$OUT"

echo
echo "Listo: $OUT ($(du -h "$OUT" | cut -f1))"
if [[ ${#SKIPPED[@]} -gt 0 ]]; then
  echo "Rutas omitidas por no existir: ${SKIPPED[*]}"
fi
