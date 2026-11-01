#!/usr/bin/env bash
#
# Instala o desinstala los servicios de arranque automático de AYANAMI.
#
# Servicios:
#   ayanami-restore.service
#   ayanami-vpn-guard.service
#
# Uso:
#   ./install_ayanami_services.sh
#   ./install_ayanami_services.sh --uninstall
#   ./install_ayanami_services.sh --status
#
# Variables opcionales:
#   AYANAMI_DIR       Raíz del proyecto
#   AYANAMI_VENV      Python del entorno virtual
#   AYANAMI_LAN_IFACE Interfaz LAN (predeterminado: eno2)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${AYANAMI_DIR:-$(dirname "$SCRIPT_DIR")}"

REPO_ROOT="$(cd "$REPO_ROOT" && pwd -P)"

VENV_PY="${AYANAMI_VENV:-$REPO_ROOT/venv/bin/python}"

if [[ -n "${AYANAMI_LAN_IFACE:-}" ]]; then
    LAN_IFACE="$AYANAMI_LAN_IFACE"
elif [[ -f "$REPO_ROOT/backup.json" ]]; then
    LAN_IFACE="$(
        python3 - "$REPO_ROOT/backup.json" <<'PY'
import json
import sys

try:
    with open(sys.argv[1], encoding="utf-8") as handle:
        data = json.load(handle)
    print(data.get("gateway", {}).get("lan_iface", "") or "")
except Exception:
    print("")
PY
    )"
    if [[ -z "$LAN_IFACE" ]]; then
        LAN_IFACE="eno2"
    fi
else
    LAN_IFACE="eno2"
fi

UNIT_DIR="/etc/systemd/system"

RESTORE_SERVICE="$UNIT_DIR/ayanami-restore.service"
VPN_SERVICE="$UNIT_DIR/ayanami-vpn-guard.service"

UNINSTALL=0
STATUS=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --uninstall)
            UNINSTALL=1
            shift
            ;;
        --status)
            STATUS=1
            shift
            ;;
        -h|--help)
            echo "Uso: $0 [--uninstall|--status]"
            exit 0
            ;;
        *)
            echo "Opción desconocida: $1" >&2
            exit 2
            ;;
    esac
done

# --------------------------------------------------
# ESTADO
# --------------------------------------------------

if [[ "$STATUS" == "1" ]]; then
    echo "Estado de los servicios AYANAMI:"
    echo

    systemctl status \
        ayanami-restore.service \
        ayanami-vpn-guard.service \
        --no-pager || true

    exit 0
fi

# --------------------------------------------------
# DESINSTALACIÓN
# --------------------------------------------------

if [[ "$UNINSTALL" == "1" ]]; then
    echo "Desinstalando servicios AYANAMI..."

    sudo systemctl disable --now \
        ayanami-vpn-guard.service 2>/dev/null || true

    sudo systemctl stop \
        ayanami-restore.service 2>/dev/null || true

    sudo systemctl disable \
        ayanami-restore.service 2>/dev/null || true

    sudo rm -f \
        "$RESTORE_SERVICE" \
        "$VPN_SERVICE"

    sudo systemctl daemon-reload

    echo "OK: servicios desinstalados."
    echo "La configuración de AYANAMI no fue eliminada."

    exit 0
fi

# --------------------------------------------------
# VALIDACIONES
# --------------------------------------------------

if [[ ! -f "$REPO_ROOT/tui/restore_gateway.py" ]]; then
    echo "ERROR: No existe tui/restore_gateway.py" >&2
    exit 1
fi

if [[ ! -f "$REPO_ROOT/tui/vpn_guard.py" ]]; then
    echo "ERROR: No existe tui/vpn_guard.py" >&2
    exit 1
fi

if [[ ! -x "$VENV_PY" ]]; then
    echo "Aviso: no se encontró el Python del entorno virtual."

    VENV_PY="$(command -v python3)"
fi

if ! ip link show "$LAN_IFACE" >/dev/null 2>&1; then
    echo "ERROR: No existe la interfaz LAN $LAN_IFACE" >&2
    exit 1
fi

echo "======================================"
echo "       INSTALADOR AYANAMI"
echo "======================================"
echo
echo "Proyecto : $REPO_ROOT"
echo "Python   : $VENV_PY"
echo "LAN      : $LAN_IFACE"
echo

# --------------------------------------------------
# SERVICIO DE RESTAURACIÓN
# --------------------------------------------------

echo "Generando ayanami-restore.service..."

sudo tee "$RESTORE_SERVICE" >/dev/null <<EOF
[Unit]
Description=AYANAMI - Restauracion del gateway y firewall
Wants=network-online.target
After=network-online.target NetworkManager.service
Before=ayanami-vpn-guard.service

[Service]
Type=oneshot
User=root
WorkingDirectory=$REPO_ROOT
ExecStart=$VENV_PY $REPO_ROOT/tui/restore_gateway.py
RemainAfterExit=yes
TimeoutStartSec=60

[Install]
WantedBy=multi-user.target
EOF

# --------------------------------------------------
# SERVICIO VPN GUARD
# --------------------------------------------------

echo "Generando ayanami-vpn-guard.service..."

sudo tee "$VPN_SERVICE" >/dev/null <<EOF
[Unit]
Description=AYANAMI - VPN Guard
Requires=ayanami-restore.service
After=ayanami-restore.service network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=$REPO_ROOT

ExecStart=$VENV_PY $REPO_ROOT/tui/vpn_guard.py --interface $LAN_IFACE --lan-iface $LAN_IFACE --block-duration 5 --block-device --apply

Restart=on-failure
RestartSec=5

KillSignal=SIGINT
TimeoutStopSec=15

StandardOutput=append:$REPO_ROOT/vpn_guard.log
StandardError=append:$REPO_ROOT/vpn_guard.log

[Install]
WantedBy=multi-user.target
EOF

# --------------------------------------------------
# HABILITAR IP FORWARD
# --------------------------------------------------

echo "Configurando IPv4 forwarding..."

echo "net.ipv4.ip_forward=1" |
    sudo tee /etc/sysctl.d/90-ayanami.conf >/dev/null

sudo sysctl -w net.ipv4.ip_forward=1 >/dev/null

# --------------------------------------------------
# INSTALAR SERVICIOS
# --------------------------------------------------

echo "Recargando systemd..."

sudo systemctl daemon-reload

echo "Validando servicios..."

sudo systemd-analyze verify \
    "$RESTORE_SERVICE" \
    "$VPN_SERVICE"

echo "Habilitando arranque automático..."

sudo systemctl enable ayanami-restore.service
sudo systemctl enable ayanami-vpn-guard.service

echo
echo "======================================"
echo "    INSTALACIÓN COMPLETADA"
echo "======================================"
echo
echo "Servicios habilitados:"
echo "  - ayanami-restore.service"
echo "  - ayanami-vpn-guard.service"
echo
echo "Los servicios se iniciarán automáticamente"
echo "durante el próximo arranque del servidor."
echo
echo "Para probarlos ahora:"
echo
echo "  sudo systemctl start ayanami-restore.service"
echo "  sudo systemctl start ayanami-vpn-guard.service"
echo
echo "Para consultar su estado:"
echo
echo "  ./systemd/install_ayanami_services.sh --status"
