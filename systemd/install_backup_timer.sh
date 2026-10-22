#!/usr/bin/env bash
#
# Instala (o desinstala) el timer de backups mensuales de Ayanami.
#
# Detecta la raíz del proyecto desde la ubicación de este script, de modo
# que funciona en cualquier máquina (laptop, servidor de desarrollo, etc.)
# sin editar rutas a mano.
#
# Uso:
#   ./install_backup_timer.sh                 # instalar y activar (mensual)
#   ./install_backup_timer.sh --uninstall     # desinstalar
#   ./install_backup_timer.sh --calendar "daily" --persistent false
#
# Variables de entorno opcionales:
#   AYANAMI_DIR  ruta del repo (por defecto se calcula sola)
#   AYANAMI_VENV ruta del python del venv     (por defecto <repo>/venv/bin/python)
#   AYANAMI_BACKUP_CALENDAR    OnCalendar por defecto: monthly
#   AYANAMI_BACKUP_PERSISTENT  Persistent por defecto: true
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${AYANAMI_DIR:-$(dirname "$SCRIPT_DIR")}"
VENV_PY="${AYANAMI_VENV:-$REPO_ROOT/venv/bin/python}"
UNIT_DIR="/etc/systemd/system"
SERVICE="$UNIT_DIR/ayanami-backup.service"
TIMER="$UNIT_DIR/ayanami-backup.timer"

UNINSTALL=0
CALENDAR="${AYANAMI_BACKUP_CALENDAR:-monthly}"
PERSISTENT="${AYANAMI_BACKUP_PERSISTENT:-true}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --uninstall)
            UNINSTALL=1
            shift
            ;;
        --calendar)
            [[ $# -ge 2 ]] || { echo "Falta el valor de --calendar" >&2; exit 2; }
            CALENDAR="$2"
            shift 2
            ;;
        --calendar=*)
            CALENDAR="${1#*=}"
            shift
            ;;
        --persistent)
            [[ $# -ge 2 ]] || { echo "Falta el valor de --persistent" >&2; exit 2; }
            PERSISTENT="$2"
            shift 2
            ;;
        --persistent=*)
            PERSISTENT="${1#*=}"
            shift
            ;;
        -h|--help)
            echo "Uso: $0 [--uninstall] [--calendar EXPRESIÓN] [--persistent true|false]"
            exit 0
            ;;
        *)
            echo "Opción desconocida: $1" >&2
            exit 2
            ;;
    esac
done

if [[ "$UNINSTALL" == "1" ]]; then
    echo "Desinstalando el timer de backup de Ayanami..."
    sudo systemctl disable --now ayanami-backup.timer 2>/dev/null || true
    sudo rm -f "$SERVICE" "$TIMER"
    sudo systemctl daemon-reload
    echo "OK: timer desinstalado."
    exit 0
fi

if [[ -z "$CALENDAR" ]]; then
    echo "La expresión OnCalendar no puede estar vacía." >&2
    exit 2
fi

case "${PERSISTENT,,}" in
    true|yes|1|on) PERSISTENT="true" ;;
    false|no|0|off) PERSISTENT="false" ;;
    *)
        echo "Valor inválido para --persistent: $PERSISTENT (usá true o false)." >&2
        exit 2
        ;;
esac

if command -v systemd-analyze >/dev/null 2>&1; then
    if ! systemd-analyze calendar "$CALENDAR" >/dev/null 2>&1; then
        echo "Expresión OnCalendar inválida: $CALENDAR" >&2
        exit 2
    fi
fi

if [[ ! -x "$VENV_PY" ]]; then
    echo "Aviso: no se encontró $VENV_PY; usaré 'python3' del PATH." >&2
    VENV_PY="$(command -v python3)"
fi

echo "Raíz del proyecto : $REPO_ROOT"
echo "Python            : $VENV_PY"

# Generamos los units con la ruta real en tiempo de instalación.
sudo tee "$SERVICE" >/dev/null <<EOF
[Unit]
Description=Backup programado de la configuración de Ayanami
After=network.target

[Service]
Type=oneshot
# Generado por systemd/install_backup_timer.sh — la ruta se calculó al instalar.
ExecStart=$VENV_PY $REPO_ROOT/tui/firewall_config.py

[Install]
WantedBy=multi-user.target
EOF

sudo tee "$TIMER" >/dev/null <<EOF
[Unit]
Description=Ejecuta el backup programado de Ayanami
Requires=ayanami-backup.service

[Timer]
OnCalendar=$CALENDAR
Persistent=$PERSISTENT
Unit=ayanami-backup.service

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ayanami-backup.timer
sudo systemctl restart ayanami-backup.timer

echo "OK: timer instalado y activo (OnCalendar=$CALENDAR, Persistent=$PERSISTENT)."
systemctl list-timers ayanami-backup.timer --no-pager
