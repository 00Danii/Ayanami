# Ayanami

**Ayanami** es una herramienta de control de red con **interfaz de usuario basada en texto (TUI)** y una versión CLI, ambas pensadas para Linux. Permite inspeccionar interfaces, crear un hotspot, detectar dispositivos, monitorear tráfico en tiempo real, esnifar paquetes con Scapy, gestionar un firewall con bloqueo por apps y una lista blanca de direcciones IP y MAC, y consultar el estado del sistema.

```text
▄████▄ ██  ██ ▄████▄ ███  ██ ▄████▄ ██▄  ▄██ ██
██▄▄██  ▀██▀  ██▄▄██ ██ ▀▄██ ██▄▄██ ██ ▀▀ ██ ██
██  ██   ██   ██  ██ ██   ██ ██  ██ ██    ██ ██
```

---

Herramienta en Python 3, diseñada para ejecutarse con permisos de root para la mayoría de sus funcionalidades (iptables, nmcli, sniffing).

---

## TUI — Interfaz de Texto (recomendada)

La TUI está construida con **Textual** y es la forma más completa y amigable de usar Ayanami. Incluye una barra lateral de navegación y **9 vistas**. La vista inicial es **Sistema**; las demás vistas se importan y montan bajo demanda la primera vez que se abren.

| Vista | Descripción |
|---|---|
| **Interfaces** | Lista las interfaces de red con tipo, estado, IPs y acciones. |
| **Hotspot** | Crea y gestiona un punto de acceso WiFi con `nmcli`. |
| **Scanner** | Detecta dispositivos en la LAN (`ip neigh`) con panel de detalles. |
| **Monitor** | Monitorea ancho de banda por host en tiempo real. |
| **Sniffer** | Captura paquetes con Scapy (todo el tráfico, por dispositivo, RAW). |
| **Firewall** | Control total del firewall con 5 pestañas (ver abajo). |
| **DHCP** | Estado, edición de `dnsmasq.conf` con resaltado de sintaxis, validación y confirmación antes de reiniciar `dnsmasq`; avisa si no hay cambios. |
| **Respaldos** | Copias manuales de la configuración y gestión de los backups automáticos: estado del timer, backup inmediato, restaurar y eliminar. |
| **Sistema** | Dashboard tipo *fastfetch*: CPU, memoria, disco, procesos, temperatura y red. |

### Pestañas del Firewall

- **Apps** — Registra aplicaciones con sus dominios, activa/desactiva su bloqueo con un switch, filtra y ordena. El bloqueo se aplica vía **dnsmasq** (`address=/{dominio}/0.0.0.0`) más **iptables** para QUIC/NAT.
- **Lista Blanca** — Exenta IPs, rangos (`10.0.0.1-10.0.0.255`), subredes CIDR (`192.168.1.0/24`) o **direcciones MAC** (`AA:BB:CC:DD:EE:FF`) de todas las reglas de bloqueo. Cada entrada tiene su propio **switch para activarla o desactivarla** sin borrarla; **Limpiar Firewall** apaga todos los switches y conserva las entradas. Las entradas activas resuelven DNS externamente (8.8.8.8) en vez del dnsmasq local, con aplicación automática de las reglas.
- **Config** — Configura el gateway/NAT, fuerza DNS local, muestra el estado de las reglas y limpia el firewall completo.
- **VPN Guard** — Detecta VPNs con `ndpiReader` y bloquea el dispositivo por MAC. Requiere el binario `ndpiReader` en la raíz del proyecto (biblioteca open source de **ntop**, https://github.com/ntop/nDPI) y ejecución como root.
- **Servicios** — Instala, desinstala, inicia, detiene y consulta los servicios systemd de AYANAMI (restore y VPN Guard).

### Vista Respaldos

- **Guardar/Cargar Copia** — Exporta lista blanca, apps, el gateway aplicado y persistido (no el seleccionado en la UI) y el contenido de `/etc/dnsmasq.conf`. Al cargar, la confirmación permite elegir con switches si restaurar lista blanca, apps, gateway guardado y `dnsmasq.conf`; todos empiezan apagados.
- **Backups automáticos** — Muestra el estado del timer de systemd, su programación (`OnCalendar`), el modo `Persistent` y la próxima ejecución. Permite ver el estado en el log, cambiar la frecuencia (mensual, semanal o diaria), instalar/desinstalar el timer y crear un backup inmediato.
- **Lista de backups** — Muestra las copias como tabla (año, mes, día, hora y tamaño), con acciones clicables **Restaurar** y **Eliminar**.

### Archivo de configuración y backups

Toda la configuración del firewall se resume en `backup.json` (raíz del proyecto): lista blanca, apps, gateway y contenido de `/etc/dnsmasq.conf`.

- **Guardar Copia** — exporta esa configuración y crea un backup inmediato.
- **Cargar Copia** — restaura componentes seleccionados mediante switches (todos apagados por defecto).
- `backup.json` se actualiza automáticamente al modificar lista blanca, apps o gateway.
- Los backups automáticos se guardan en `backups/backup-YYYY-MM-DD_HHMMSS_ffffff.json` y se conservan las **últimas 5 copias**.
- El timer de systemd permite elegir frecuencia y modo `Persistent`.

Instala el timer:

```bash
sudo systemd/install_backup_timer.sh
```

Desinstala:

```bash
sudo systemd/install_backup_timer.sh --uninstall
```

Verifica:

```bash
systemctl list-timers ayanami-backup.timer --no-pager
sudo systemctl start ayanami-backup.service
```

Más detalles: ver **Manual de Usuario** (operación) y **Manual del Programador** (estructura y validaciones).

### Atajos de teclado

| Tecla | Acción |
|---|---|
| `q` | Salir |
| `r` | Actualizar la vista actual |

### Ejecutar la TUI

```bash
sudo venv/bin/python tui/tui.py
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
sudo apt install -y network-manager iftop iptables dnsmasq nmap arp-scan conntrack iproute2 python3-venv
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

### nDPI (para VPN Guard)

VPN Guard necesita el binario `ndpiReader` en la raíz del proyecto. Es open source de **ntop** (https://github.com/ntop/nDPI). Para compilarlo:

```bash
git clone https://github.com/ntop/nDPI.git
cd nDPI
./autogen.sh
./configure
make
cp example/ndpiReader /ruta/al/proyecto/ndpiReader
chmod +x /ruta/al/proyecto/ndpiReader
```

Sustituye `/ruta/al/proyecto` por la ruta absoluta del repositorio. Para detectar WireGuard, el código fuente de `example/ndpiReader.c` debe incluir `NDPI_PROTOCOL_WIREGUARD` en `realtime_protos` (ver Manual del Programador).

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

## Inicio rápido

1. Ejecuta la TUI con privilegios administrativos:

   ```bash
   sudo venv/bin/python tui/tui.py
   ```

2. Selecciona la **interfaz LAN** en la barra lateral.
3. Accede a **Firewall → Config**.
4. Selecciona la **interfaz WAN** y pulsa **Configurar Gateway**.
5. Verifica en el log que IP Forward, NAT, DNS y DoT queden activos.
6. Configura DHCP y DNS según tu red.
7. Conecta un dispositivo cliente y comprueba la asignación de IP y el acceso a internet.
8. Activa las funciones de bloqueo necesarias (apps, lista blanca, VPN Guard).

### Servicios automáticos

Para instalar y habilitar los servicios de arranque:

```bash
sudo systemd/install_ayanami_services.sh
```

Comprueba su estado:

```bash
systemctl is-active ayanami-restore.service
systemctl is-active ayanami-vpn-guard.service
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


## Documentación

| Documento | Propósito |
|---|---|
| [Manual de Usuario](ManualUsuario.md) | Instalación, navegación, configuración y operación. |
| [Manual del Programador](ManualProgramador.md) | Arquitectura, módulos, persistencia y mantenimiento. |

## Depuración y problemas comunes

- **`nmcli` no disponible**: instala NetworkManager o ejecuta las funciones manualmente.
- **`scapy` falla**: verifica la instalación con `pip show scapy` y prueba `python3 -c "from scapy.all import sniff; print('OK')"`.
- **`iftop` no está instalado**: instálalo en tu distribución (ej. `sudo apt install iftop`).
- **Errores de permisos**: reintenta con `sudo`.
- **La TUI no arranca**: asegúrate de que `textual` está instalado y ejecuta desde la carpeta `tui/`.

---