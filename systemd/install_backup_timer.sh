#!/usr/bin/env bash
#
# Instala (o desinstala) el timer de backups mensuales de Ayanami.
#
# Detecta la raíz del proyecto desde la ubicación de este script, de modo
# que funciona en cualquier máquina (laptop, servidor de desarrollo, etc.)
# sin editar rutas a mano.
#
# Uso:
#   ./install_backup_timer.sh                 # instalar y activar
#   ./install_backup_timer.sh --uninstall     # desinstalar
#
# Variables de entorno opcionales:
#   AYANAMI_DIR  ruta del repo (por defecto se calcula sola)
#   AYANAMI_VENV ruta del python del venv     (por defecto <repo>/venv/bin/python)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${AYANAMI_DIR:-$(dirname "$SCRIPT_DIR")}"
VENV_PY="${AYANAMI_VENV:-$REPO_ROOT/venv/bin/python}"
UNIT_DIR="/etc/systemd/system"
SERVICE="$UNIT_DIR/ayanami-backup.service"
TIMER="$UNIT_DIR/ayanami-backup.timer"

if [[ "${1:-}" == "--uninstall" ]]; then
    echo "Desinstalando el timer de backup de Ayanami..."
    sudo systemctl disable --now ayanami-backup.timer 2>/dev/null || true
    sudo rm -f "$SERVICE" "$TIMER"
    sudo systemctl daemon-reload
    echo "OK: timer desinstalado."
    exit 0
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
Description=Backup mensual de la configuración de Ayanami
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
Description=Ejecuta el backup mensual de Ayanami (1º de cada mes)
Requires=ayanami-backup.service

[Timer]
OnCalendar=monthly
Persistent=true
Unit=ayanami-backup.service

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now ayanami-backup.timer

echo "OK: timer instalado y activo."
systemctl list-timers ayanami-backup.timer --no-pager