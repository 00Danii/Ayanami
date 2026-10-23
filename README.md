# Ayanami

**Ayanami** es una herramienta de control de red con **Interfaz de Texto (TUI)** y una versión CLI, ambas pensadas para Linux. Permite inspeccionar interfaces, crear un hotspot, detectar dispositivos, monitorear tráfico en tiempo real, esnifar paquetes con Scapy, gestionar un firewall con bloqueo por apps y una lista blanca de IPs y MACs, y consultar el estado del sistema.

```text
▄████▄ ██  ██ ▄████▄ ███  ██ ▄████▄ ██▄  ▄██ ██
██▄▄██  ▀██▀  ██▄▄██ ██ ▀▄██ ██▄▄██ ██ ▀▀ ██ ██
██  ██   ██   ██  ██ ██   ██ ██  ██ ██    ██ ██
```

---

Herramienta en Python 3, diseñada para ejecutarse con permisos de root para la mayoría de sus funcionalidades (iptables, nmcli, sniffing).

---

## TUI — Interfaz de Texto (recomendada)

La TUI está construida con **Textual** y es la forma más completa y amigable de usar Ayanami. Incluye una barra lateral de navegación y **9 vistas**. Las vistas se importan y montan bajo demanda: el arranque solo construye **Interfaces** y las demás aparecen la primera vez que se abren.

| Vista | Descripción |
|---|---|
| **Interfaces** | Lista las interfaces de red con tipo, estado, IPs y acciones. |
| **Hotspot** | Crea y gestiona un punto de acceso WiFi con `nmcli`. |
| **Scanner** | Detecta dispositivos en la LAN (`ip neigh`) con panel de detalles. |
| **Monitor** | Monitorea ancho de banda por host en tiempo real. |
| **Sniffer** | Captura paquetes con Scapy (todo el tráfico, por dispositivo, RAW). |
| **Firewall** | Control total del firewall con 3 pestañas (ver abajo). |
| **DHCP** | Estado, edición de `dnsmasq.conf` con resaltado de sintaxis, validación y confirmación antes de reiniciar `dnsmasq`; avisa si no hay cambios. |
| **Respaldos** | Copias manuales de la configuración y gestión de los backups automáticos: estado del timer, backup inmediato, restaurar y eliminar. |
| **Sistema** | Dashboard tipo *fastfetch*: CPU, memoria, disco, procesos, temperatura y red. |

### Pestañas del Firewall

- **Apps** — Registra aplicaciones con sus dominios, activa/desactiva su bloqueo con un switch, filtra y ordena. El bloqueo se aplica vía **dnsmasq** (`address=/{dominio}/0.0.0.0`) más **iptables** para QUIC/NAT.
- **Lista Blanca** — Exenta IPs, rangos (`10.0.0.1-10.0.0.255`), subredes CIDR (`192.168.1.0/24`) o **direcciones MAC** (`AA:BB:CC:DD:EE:FF`) de todas las reglas de bloqueo. Cada entrada tiene su propio **switch para activarla o desactivarla** sin borrarla; **Limpiar Firewall** apaga todos los switches y conserva las entradas. Las entradas activas resuelven DNS externamente (8.8.8.8) en vez del dnsmasq local, con aplicación automática de las reglas.
- **Config** — Configura el gateway/NAT, fuerza DNS local, muestra el estado de las reglas y limpia el firewall completo.

### Vista Respaldos

- **Guardar/Cargar Copia** — Exporta lista blanca, apps, el gateway aplicado y persistido (no el seleccionado en la UI) y el contenido de `/etc/dnsmasq.conf`. Al cargar, la confirmación permite elegir con switches si restaurar lista blanca, apps, gateway guardado y `dnsmasq.conf`; todos empiezan apagados.
- **Backups automáticos** — Muestra el estado del timer de systemd, su programación (`OnCalendar`), el modo `Persistent` y la próxima ejecución. Permite ver el estado en el log, cambiar la frecuencia (mensual, semanal o diaria), instalar/desinstalar el timer y crear un backup inmediato.
- **Lista de backups** — Muestra las copias como tabla (año, mes, día, hora y tamaño), con acciones clicables **Restaurar** y **Eliminar**.

### Archivo de configuración y backups

Toda la configuración del firewall se resume en un solo archivo, `backup.json` (en la raíz del proyecto):

```json
{
  "version": 1,
  "exported_at": "2026-09-25T12:00:00",
  "hostname": "ayanami",
  "gateway": {
    "wan_iface": "eth0",
    "lan_iface": "wlan0",
    "dns_target": "10.42.0.1",
    "applied_at": "2026-09-25T12:00:00"
  },
  "dnsmasq": {
    "path": "/etc/dnsmasq.conf",
    "included_at": "2026-09-25T12:00:00",
    "available": true,
    "encoding": "utf-8",
    "size": 482,
    "content": "interface=wlan0\ndhcp-range=10.42.0.10,10.42.0.200,12h\n"
  },
  "stats": {
    "whitelist_count": 3,
    "apps_count": 22,
    "blocked_count": 5,
    "domains_count": 120
  },
  "whitelist_disabled": [],
  "whitelist": ["10.0.0.5", "192.168.1.0/24"],
  "apps": { "...": { "domains": [], "blocked": false, "type": "Videojuegos" } }
}
```

- **Guardar Copia** (vista Respaldos) — abre un **selector de rutas** (o escribe la ruta a mano) para exportar lista blanca, apps, datos de referencia del gateway y el contenido actual de `/etc/dnsmasq.conf`. También crea un backup inmediato.
- **Cargar Copia** — selecciona el archivo y muestra switches para elegir qué restaurar: lista blanca, apps/bloqueos, gateway guardado y, si está incluido, `dnsmasq.conf`. Todos empiezan apagados; activa los que quieras aplicar. Solo se aplican los componentes marcados y al final se actualiza la copia canónica `backup.json`. El gateway solo se persiste, no se reaplican reglas NAT automáticamente: para eso usa **Configurar Gateway**. Las copias antiguas sin el bloque `dnsmasq` siguen funcionando.
- El gateway se guarda automáticamente cada vez que se configura con "Configurar Gateway". Al restaurar, `dns_target` se conserva tal cual en `backup.json`; las reglas NAT no se reaplican hasta que uses **Configurar Gateway**.
- En el bloque `dnsmasq`, `content` es el texto del archivo y `encoding` indica cómo decodificarlo (`utf-8` o `latin-1`, para no corromper bytes no UTF-8). El campo `path` es informativo: si activas el switch, la restauración siempre escribe en `/etc/dnsmasq.conf`.

#### Backups automáticos (systemd timer)

Los backups se guardan en `backups/backup-YYYY-MM-DD_HHMMSS_ffffff.json` (la copia canónica siempre es la raíz del repo) y se conservan las **últimas 5 copias**; al crear una nueva se elimina la más antigua. Cada copia incluye el contenido actual de `/etc/dnsmasq.conf` aunque la copia canónica sea antigua. La vista **Respaldos** permite crear uno ahora, actualizar el estado del timer, editarlo, instalarlo/desinstalarlo y restaurar o eliminar cada copia. El gateway se toma del último aplicado y guardado en `backup.json`, no de la interfaz seleccionada en la UI; cerrar Ayanami no cambia lo que respalda el timer. Si la copia canónica falta o está corrupta, el backup se reconstruye desde los archivos vivos y se escribe de forma atómica, sin dejar archivos parciales.

Si activas el switch para restaurar `dnsmasq` en una copia que lo incluye, Ayanami escribe primero un temporal, lo valida con `dnsmasq --test`, guarda la versión actual en `/etc/dnsmasq.conf.ayanami.bak` y solo entonces reemplaza el archivo y reinicia `dnsmasq`. Si la validación falla, el archivo real no se modifica. El switch está apagado por defecto: si no lo activas, `/etc/dnsmasq.conf` no se toca. El servicio de backup corre como root, por lo que el timer también puede leer el contenido.

El timer usa por defecto `OnCalendar=monthly` y `Persistent=true`, pero **se ejecuta según la programación configurada**: mensual, semanal, diaria o una expresión `OnCalendar` personalizada. La vista muestra siempre el `OnCalendar` real del timer instalado. Cada ejecución crea un archivo nuevo con fecha y hora; no se agrupan por mes. Los backups con formato corto `backup-YYYY-MM.json` también aparecen en la lista y se pueden restaurar o eliminar.

Con `Persistent=true`, si el equipo estaba apagado cuando tocaba ejecutar, systemd recupera **una vez** la ejecución atrasada al volver a encenderse. Con `Persistent=false`, la ejecución perdida se descarta y se espera a la próxima fecha programada.

Instalación del timer — **las rutas se detectan automáticamente** (usa `AYANAMI_DIR=/ruta` si el repo no está junto al script). También se puede instalar desde la vista Respaldos:

```bash
sudo systemd/install_backup_timer.sh

# Personalizar la programación:
sudo systemd/install_backup_timer.sh --calendar "Mon..Fri 03:00" --persistent false
```

Desinstalación:

```bash
sudo systemd/install_backup_timer.sh --uninstall
```

Verificación:

```bash
systemctl list-timers ayanami-backup.timer --no-pager
sudo systemctl start ayanami-backup.service   # ejecutar el backup ahora mismo
```

El servicio corre `tui/firewall_config.py`, que crea una copia con marca de tiempo y conserva solo las 5 más recientes. Si `backup.json` aún no existe, lo genera con el estado actual antes de respaldarlo.

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