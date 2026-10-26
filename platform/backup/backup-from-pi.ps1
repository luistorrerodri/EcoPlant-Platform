# Descarga una copia de seguridad completa de EcoPlant desde la Raspberry Pi al PC.
#
# Uso (PowerShell, desde cualquier carpeta):
#   .\backup-from-pi.ps1
#   .\backup-from-pi.ps1 -Destino D:\Backups\EcoPlant
#
# Pide la contraseña de la Pi (sudo) y la contraseña de cifrado de la copia.
# Hay que estar en la misma red (WiFi de casa) que la Pi.

param(
    [string]$PiHost = "192.168.1.140",
    [string]$PiUser = "piluis",
    [string]$Destino = (Join-Path $env:USERPROFILE "Backups\EcoPlant")
)

$ErrorActionPreference = "Stop"

New-Item -ItemType Directory -Force -Path $Destino | Out-Null

$remote = "$PiUser@$PiHost"
$script = "~/EcoPlant-Platform/platform/backup/pi-backup.sh"

Write-Host "==> Generando la copia en la Pi (te pedirá la contraseña sudo y la de cifrado)"
# -t: terminal interactivo para poder teclear las contraseñas (sin tuberías, para ver los avisos).
ssh -t $remote "sudo bash $script"
if ($LASTEXITCODE -ne 0) { throw "El script de la Pi falló (código $LASTEXITCODE). No se descarga nada." }

# El archivo recién creado es el más reciente de su patrón en /tmp.
$remoto = (ssh $remote "ls -t /tmp/ecoplant-backup-*.tar.gz.enc | head -n 1").Trim()
if (-not $remoto) { throw "No se encontró el archivo generado en la Pi." }
$nombre = Split-Path -Leaf $remoto
$local = Join-Path $Destino $nombre

Write-Host "==> Descargando $nombre"
scp "${remote}:$remoto" $local
if ($LASTEXITCODE -ne 0) { throw "scp falló. El archivo sigue en la Pi: $remoto" }

# Comprobación: el tamaño local debe coincidir con el remoto antes de borrar nada.
$tamRemoto = [int64](ssh $remote "stat -c %s $remoto")
$tamLocal = (Get-Item $local).Length
if ($tamRemoto -ne $tamLocal) {
    throw "El tamaño no coincide (Pi: $tamRemoto, PC: $tamLocal). No se borra la copia de la Pi: $remoto"
}

Write-Host "==> Borrando la copia temporal de la Pi"
ssh $remote "rm -f $remoto"

Write-Host ""
Write-Host "Copia guardada en: $local ($([math]::Round($tamLocal / 1MB, 1)) MB)"
Write-Host "Guarda también la contraseña de cifrado en tu gestor de contraseñas: sin ella no se puede restaurar."
