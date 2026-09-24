# Ayanami

**Ayanami** es una herramienta de control de red con **Interfaz de Texto (TUI)** y una versión CLI, ambas pensadas para Linux. Permite inspeccionar interfaces, crear un hotspot, detectar dispositivos, monitorear tráfico en tiempo real, esnifar paquetes con Scapy, gestionar un firewall con bloqueo por apps y una lista blanca de IPs, y consultar el estado del sistema.

```text
▄████▄ ██  ██ ▄████▄ ███  ██ ▄████▄ ██▄  ▄██ ██
██▄▄██  ▀██▀  ██▄▄██ ██ ▀▄██ ██▄▄██ ██ ▀▀ ██ ██
██  ██   ██   ██  ██ ██   ██ ██  ██ ██    ██ ██
```

---

Herramienta en Python 3, diseñada para ejecutarse con permisos de root para la mayoría de sus funcionalidades (iptables, nmcli, sniffing).

---

## TUI — Interfaz de Texto (recomendada)

La TUI está construida con **Textual** y es la forma más completa y amigable de usar Ayanami. Incluye una barra lateral de navegación y **7 vistas**:

| Vista | Descripción |
|---|---|
| **Interfaces** | Lista las interfaces de red con tipo, estado, IPs y acciones. |
| **Hotspot** | Crea y gestiona un punto de acceso WiFi con `nmcli`. |
| **Scanner** | Detecta dispositivos en la LAN (`ip neigh`) con panel de detalles. |
| **Monitor** | Monitorea ancho de banda por host en tiempo real. |
| **Sniffer** | Captura paquetes con Scapy (todo el tráfico, por dispositivo, RAW). |
| **Firewall** | Control total del firewall con 3 pestañas (ver abajo). |
| **Sistema** | Dashboard tipo *fastfetch*: CPU, memoria, disco, procesos, temperatura y red. |

### Pestañas del Firewall

- **Apps** — Registra aplicaciones con sus dominios, activa/desactiva su bloqueo con un switch, filtra y ordena. El bloqueo se aplica vía **dnsmasq** (`address=/{dominio}/0.0.0.0`) más **iptables** para QUIC/NAT.
- **Lista Blanca** — Exenta IPs, rangos (`10.0.0.1-10.0.0.255`) o subredes CIDR (`192.168.1.0/24`) de todas las reglas de bloqueo. Las IPs listadas resuelven DNS externamente (8.8.8.8) en vez del dnsmasq local, con aplicación automática de las reglas.
- **Config** — Configura el gateway/NAT, fuerza DNS local, muestra el estado de las reglas y limpia el firewall completo.

### Atajos de teclado

| Tecla | Acción |
|---|---|
| `q` | Salir |
| `r` | Actualizar la vista actual |

### Ejecutar la TUI

```bash
cd tui
sudo venv/bin/python tui.py
```

---

## Requisitos e instalación

### Dependencias del sistema

- Linux con **NetworkManager** (`nmcli`).
- `iptables` disponible en el sistema.
- `iftop` para el monitoreo de ancho de banda (opcional pero recomendado).
- `dnsmasq` (el bloqueo de apps usa el dnsmasq compartido de NetworkManager).

```bash
sudo apt update
sudo apt install -y network-manager iftop iptables dnsmasq nmap arp-scan
```

> En otras distribuciones usa tu gestor de paquetes (`pacman`, `dnf`, etc.).

### Dependencias de Python

Las dependencias están fijadas en **`requirements.txt`**. Se recomienda instalarlas en un entorno virtual:

```bash
# Crear el entorno virtual
python3 -m venv venv

# Activar el entorno
source venv/bin/activate

# Instalar las dependencias
pip install -r requirements.txt
```

El contenido del archivo incluye: `textual` (la TUI), `scapy` (sniffer), `python-nmap`, `qrcode` y utilidades relacionadas.

### Permisos

Las funciones que manipulan el firewall, crean el hotspot o capturan paquetes requieren privilegios de root.

```bash
# Opción A: usar el Python del venv directamente
sudo venv/bin/python tui/tui.py

# Opción B: activar el venv y luego ejecutar
source venv/bin/activate
sudo python tui/tui.py
```

---

## CLI — Versión de consola (alternativa)

Existe una versión CLI basada en menús interactivos en la carpeta `cli/`. Es útil cuando no se dispone de la TUI o se prefiere un flujo por prompts.

```bash
sudo python3 cli/ayanami.py
```

### Módulos CLI

- `ayanami.py` — Entrada principal; menú interactivo que orquesta las opciones.
- `network.py` — Lista interfaces (`nmcli`), desconecta y obtiene detalles.
- `gateway.py` — Crea un hotspot con `nmcli` y muestra la contraseña.
- `scanner.py` — Detecta vecinos en la LAN usando `ip neigh`.
- `monitor_bw.py` — Lanza `iftop` para monitorear ancho de banda.
- `sniffer.py` — Sniffer basado en Scapy (modos: todo, por dispositivo, RAW).
- `firewall.py` — Aplica reglas `iptables` (bloquear IPs, listar, borrar, flush).
- `firewall_apps.py` — Gestión de aplicaciones con IPs asociadas (persistencia en `firewall_apps.json`).

---

## Permisos y seguridad

- Muchas funciones requieren privilegios de administrador: ejecutar la herramienta con `sudo` o como root.
- Manipular `iptables` y `dnsmasq` afecta la conectividad de la red; úsalo con cuidado y solo en entornos de prueba o con autorización.
- El sniffer captura paquetes — evita usarlo en redes que no administras o sin permisos.

## Depuración y problemas comunes

- **`nmcli` no disponible**: instala NetworkManager o ejecuta las funciones manualmente.
- **`scapy` falla**: verifica la instalación con `pip show scapy` y prueba `python3 -c "from scapy.all import sniff; print('OK')"`.
- **`iftop` no está instalado**: instálalo en tu distribución (ej. `sudo apt install iftop`).
- **Errores de permisos**: reintenta con `sudo`.
- **La TUI no arranca**: asegúrate de que `textual` está instalado y ejecuta desde la carpeta `tui/`.

---