# Análisis Completo del Proyecto Ayanami

## 1. Información General

| Campo | Valor |
|---|---|
| **Nombre** | Ayanami |
| **Repositorio** | https://github.com/00Danii/Ayanami.git |
| **Propósito** | Herramienta de inspección, monitoreo y control básico de redes locales en Linux |
| **Lenguaje** | Python 3.12+ / 3.13 |
| **Licencia** | No especificada |

---

## 2. Stack Tecnológico

| Categoría | Tecnología |
|---|---|
| **Lenguaje** | Python 3 |
| **CLI** | Python puro con códigos de color ANSI |
| **TUI** | [Textual](https://textual.textualize.io/) (framework de terminal) |
| **Sniffer de paquetes** | Scapy |
| **Escaneo de red** | Nmap (python-nmap) |
| **Códigos QR** | Librería `qrcode` |
| **Gestión de red** | NetworkManager CLI (`nmcli`) |
| **Firewall** | iptables |
| **Monitor de ancho de banda** | iftop (opcional) + sniffer propio |
| **Bloqueo DNS** | dnsmasq (integrado con NetworkManager) |
| **Persistencia** | Archivos JSON |
| **Estilos TUI** | Textual CSS (`app.css`) |

---

## 3. Estructura del Proyecto

```
ayanami/
├── .git/                          # Repositorio Git
├── .gitignore                     # Ignora solo __pycache__/
├── README.md                      # Documentación del proyecto (español)
├── PROBLEMAS.txt                  # Guía de solución de problemas para hotspot
├── cli/                           # === VERSIÓN CLI (interfaz de texto) ===
│   ├── ayanami.py                 # Punto de entrada principal (menú interactivo)
│   ├── colors.py                  # Constantes de color ANSI
│   ├── network.py                 # Listado/desconexión de interfaces de red
│   ├── gateway.py                 # Creación de hotspot y mostrar contraseña
│   ├── scanner.py                 # Descubrimiento de vecinos LAN (ip neigh)
│   ├── monitor_bw.py              # Monitoreo de ancho de banda (iftop)
│   ├── sniffer.py                 # Sniffer de paquetes (Scapy, 3 modos)
│   ├── firewall.py                # Firewall basado en iptables (787 líneas)
│   ├── firewall_apps.py           # Gestión de bloqueo por apps (DNS + iptables)
│   ├── reglasFirewall.py          # Script de firewall independiente (versión anterior)
│   ├── firewall_apps.json         # Datos: apps registradas con IPs
│   ├── firewall_apps_state.json   # Estado: apps bloqueadas global/por dispositivo
│   └── __pycache__/               # Caché de bytecode
├── tui/                           # === VERSIÓN TUI (Textual) ===
│   ├── tui.py                     # Aplicación Textual principal (AyanamiApp)
│   ├── colors.py                  # Constantes de color ANSI (duplicado)
│   ├── network.py                 # Listado de interfaces (simplificado)
│   ├── scanner.py                 # Scanner mejorado (nmap + arp-scan)
│   ├── monitor_bw.py              # Monitoreo de ancho de banda (wrapper)
│   ├── sniffer.py                 # Sniffer de paquetes (compartido con CLI)
│   ├── firewall.py                # Firewall iptables adaptado para TUI
│   ├── firewall_apps.py           # Gestión de apps adaptada para TUI
│   ├── styles/
│   │   └── app.css                # Estilos Textual CSS (724 líneas)
│   ├── widgets/
│   │   ├── sidebar.py             # Barra lateral de navegación
│   │   └── interface_row.py       # Widget de fila de interfaz
│   ├── views/
│   │   ├── interfaces.py          # Vista de interfaces de red
│   │   ├── hostspot.py            # Vista de creación de hotspot con QR
│   │   ├── scanner.py             # Vista de escáner de red con nmap
│   │   ├── monitor.py             # Monitor de tráfico en tiempo real (972 líneas)
│   │   └── sniffer.py             # Inspector profundo de paquetes (848 líneas)
│   └── venv/                      # Entorno virtual Python 3.13
└── analisis.md                    # Este archivo
```

---

## 4. Arquitectura General

El proyecto tiene **dos frontends independientes** que comparten lógica de backend similar pero no idéntica:

### CLI (`cli/`)
- Bucle infinito con menú de texto y arte ASCII
- Cada módulo es un conjunto autocontenido de funciones
- Usa `subprocess` extensivamente para comandos del sistema (`nmcli`, `iptables`, `iftop`, `ip neigh`, `conntrack`)
- Scapy se usa directamente para sniffing
- Códigos de color ANSI para estilizar la salida
- Sin dependencias externas de UI

### TUI (`tui/`)
- Aplicación Textual de pantalla completa
- **Arquitectura:** App estándar de Textual con:
  - `AyanamiApp` (hereda de `App`) — clase principal con atajos de teclado, acciones y workers
  - `Sidebar` — navegación lateral y selector de interfaz global
  - 6 vistas en un `ContentSwitcher`
  - Workers de Textual para hilos de sniffing asíncronos
  - CSS para estilos (tema oscuro Tokyo Night)

### Módulos compartidos (duplicados entre CLI y TUI)
- `colors.py` — idéntico en ambos
- `network.py` — TUI tiene versión simplificada
- `scanner.py` — TUI tiene nmap + arp-scan (CLI no)
- `sniffer.py` — TUI reexporta funciones para compatibilidad con CLI
- `firewall.py` — TUI devuelve strings en vez de imprimir
- `firewall_apps.py` — TUI usa diferente formato de JSON

---

## 5. Descripción Detallada de Módulos

### 5.1 CLI

#### `cli/ayanami.py` (67 líneas)
Punto de entrada. Bucle infinito con menú de 9 opciones:
1. Mostrar dispositivos de red
2. Desconectar interfaz
3. Crear hotspot
4. Mostrar contraseña del hotspot
5. Mostrar vecinos (ip neigh)
6. Monitorear ancho de banda (iftop)
7. Menú de sniffer (3 sub-modos)
8. Menú de firewall (sub-menú con NAT, IPs, CIDR, rangos, DNS, apps)
0. Salir

#### `cli/colors.py` (14 líneas)
Define códigos ANSI: `BLUE`, `RED`, `WHITE`, `CYAN`, `BOLD`, `PINK`, `PURPLE`, `LIGHT_GREEN`, `LIME`, `GOLD`, `ORANGE`, `RESET`.

#### `cli/network.py` (65 líneas)
- `run(cmd)` — ejecuta comando shell
- `show_devices()` — imprime `nmcli device status`
- `get_interfaces()` — lista nombres de interfaces
- `disconnect_interface()` — desconexión interactiva
- `get_interfaces_detailed()` — lista de dicts con iface, type, state, connection

#### `cli/gateway.py` (44 líneas)
- `create_hotspot()` — solicita interfaz, SSID, contraseña; ejecuta `nmcli dev wifi hotspot`
- `show_hotspot_password()` — ejecuta `nmcli dev wifi show-password`

#### `cli/scanner.py` (29 líneas)
- `get_neighbors()` — parsea `ip neigh` para entradas REACHABLE/STALE
- `show_neighbors()` — imprime vecinos con índice, IP, MAC, interfaz

#### `cli/monitor_bw.py` (63 líneas)
- `monitor_bandwidth()` — seleccionar interfaz, filtrar por host, ejecuta `iftop`

#### `cli/sniffer.py` (171 líneas)
Usa Scapy:
- `packet_full(pkt)` — imprime resumen, IP src/dst, puertos TCP/UDP, consultas DNS
- `select_interface()` — selección interactiva de interfaz
- `sniff_all()` — captura todo el tráfico
- `sniff_by_device()` — filtro BPF `host <IP>`
- `sniff_raw()` — `pkt.show()` para cada paquete
- `sniffer_menu()` — sub-menú para los 3 modos

#### `cli/firewall.py` (787 líneas — el módulo más grande)
**Gateway/NAT:**
- `enable_ip_forward()` — activa IP forwarding
- `force_dns()` — DNAT hacia 10.42.0.1
- `setup_nat()` — MASQUERADE
- `configure_gateway()` — configuración completa de gateway

**Bloqueo QUIC:**
- `block_quic()` / `unblock_quic()` — DROP UDP 443

**Bloqueo DNS vía dnsmasq:**
- Escribe en `/etc/NetworkManager/dnsmasq-shared.d/ayanami-block.conf`
- `write_domains(domains)` / `remove_domains(domains)`
- `write_domains_for_device(domains, device_ip)` / `remove_domains_for_device(domains, device_ip)`

**Validación:**
- `is_valid_cidr()` / `is_valid_ip_range()`

**Bloqueo por IP:**
- `block_device(ip)` — DROP todo desde source
- `block_global(ip)` — DROP todo hacia destination
- `block_ip_for_device(src, dst)` — DROP src->dst específico
- `block_app_ips(ips)` / `unblock_app_ips(ips)` — bloqueo/desbloqueo por lista de IPs
- `block_app_ips_for_device(ips, src_ip)` / `unblock_app_ips_for_device(ips, src_ip)`
- `block_network(cidr)` / `unblock_network(cidr)` — bloqueo de red
- `block_ip_range(range)` / `unblock_ip_range(range)` — bloqueo por rango
- `block_ip_for_device_range(dst_ip, device_range)` / `unblock_ip_for_device_range(dst_ip, device_range)`
- `block_app_ips_for_device_range(ips, device_range)` / `unblock_app_ips_for_device_range(ips, device_range)`

**Gestión de reglas:**
- `list_rules()` / `delete_rule()` / `flush_rules()` / `flush_dns_rules()` / `reset_connections()`

**Menú:** 12 opciones de firewall

#### `cli/firewall_apps.py` (489 líneas)
- **Apps predefinidas:** tiktok, clash_royale, roblox, freefire, facebook, instagram, youtube (cada una con dominios y flag block_quic)
- **Persistencia:** `firewall_apps_state.json` con listas `global_blocked` y dict `device_blocked`
- `load_data()` / `save_data()` — I/O JSON
- `block_app_global(app_name, data)` / `unblock_app_global(app_name, data)`
- `block_app_device(app_name, device_ip, data)` / `unblock_app_device(app_name, device_ip, data)`
- `main_menu()` — 17 opciones (7 bloquear global, 7 bloquear dispositivo, desbloquear, ver estado)

#### `cli/reglasFirewall.py` (599 líneas)
Script independiente (versión anterior). Define sus propias apps (incluye adguard, nextdns, freedns, mulvanddns, familyfilterdns). Menú de bloqueo para 7+5 apps, configuración de gateway, flush. Se ejecuta como `__main__`.

### 5.2 TUI

#### `tui/tui.py` (451 líneas)
Clase `AyanamiApp` extendiendo `App` de Textual:
- `CSS_PATH = "styles/app.css"`
- `ENABLE_COMMAND_PALETTE = False`
- Key bindings: `q` (salir), `r` (refrescar)
- `selected_interface` — estado global
- `compose()`: Header, Horizontal(Sidebar, ContentSwitcher con 6 vistas), Footer
- `on_list_view_selected()` — cambia la vista activa
- `on_button_pressed()` — despacha a ~15 métodos de acción
- **Acciones de firewall:** block_global, block_device, block_device_ip, list, delete_rule, flush, app_block, app_unblock, app_block_device, app_unblock_device, app_register, app_modify, app_delete
- **Sniffer:** `start_sniffing()`, `do_sniffing()` (worker asíncrono con scapy), `append_log()`, `stop_sniffing()`
- `action_refresh()` — refresca la vista actual
- `FirewallView` (en el mismo archivo): panel de firewall con inputs, botones, DataTable de apps, RichLog de salida

#### `tui/network.py` (25 líneas)
- `get_interfaces_detailed()` — versión simplificada parseando nmcli

#### `tui/scanner.py` (145 líneas)
**Mejorado sobre CLI:**
- `get_neighbors()` — igual que CLI
- `get_neighbors_simple()` — parseo más robusto, añade `state` y `vendor`
- `enrich_devices(devices, iface)` — ejecuta `arp-scan` para obtener vendor MAC
- `fingerprint_host(ip)` — usa `python-nmap` con `-Pn -T4 -F --version-light`

#### `tui/sniffer.py` (152 líneas)
Funciones de sniffing reutilizables:
- `packet_full(pkt)` — devuelve string formateado
- `get_interfaces()` — lista interfaces
- `start_sniff(iface, target, mode, callback)` — inicia captura con callback
- Funciones compatibles con CLI: `select_interface()`, `sniff_all()`, `sniff_by_device()`, `sniff_raw()`, `sniffer_menu()`

#### `tui/monitor_bw.py` (76 líneas)
- `get_interfaces()` / `get_devices()`
- `run_iftop(iface, target)` — ejecuta iftop
- `monitor_bandwidth_cli()` — menú de ancho de banda compatible con CLI

#### `tui/firewall.py` (513 líneas)
Firewall adaptado para TUI (devuelve strings en vez de imprimir). Mismas funciones de bloqueo que CLI firewall pero retornan mensajes de resultado.
- `list_rules()` / `delete_rule(num)` / `firewall_menu()` (10 opciones, más simple que CLI)

#### `tui/firewall_apps.py` (363 líneas)
- **Usa `firewall_apps.json`** en `tui/` (no `firewall_apps_state.json`)
- Datos: dict de app -> `{"ips": [], "blocked": bool, "blocked_devices": []}`
- `load_data()` / `save_data()` — normaliza datos al cargar
- CRUD completo: `register_app()`, `modify_app()`, `delete_app_or_ip()`
- `set_block_state()` / `block_app_on_device()` / `unblock_app_on_device()`
- `main_menu()` — 8 opciones

### 5.3 Vistas TUI

#### `tui/views/interfaces.py` (88 líneas)
`InterfacesView`: muestra interfaces con botones "Global" y "X". `refresh_data()` remonta widgets. `set_global_interface()` y `disconnect_interface()`.

#### `tui/views/hostspot.py` (301 líneas)
`HotspotView`: formulario con SSID y Password, validación, creación de hotspot. `show_hotspot_password()` parsea `nmcli dev wifi show-password`, muestra SSID, contraseña y **código QR** en ASCII.

#### `tui/views/scanner.py` (267 líneas)
`ScannerView`: DataTable con columnas IP, Hostname, MAC, Vendor, State, Interface. Usa `get_neighbors_simple()` y `enrich_devices()`. Barra de estadísticas. Al seleccionar una fila: `fingerprint_host(ip)` y muestra OS, servicios, puertos.

#### `tui/views/monitor.py` (972 líneas)
**Monitor de tráfico en tiempo real.** Usa Textual workers y AsyncSniffer de Scapy:
- Barra superior: filtro de host, botones refresh/start/pause
- Barra de estadísticas: interfaz, flujos, paquetes, última actualización
- DataTable: Source, Destination, Service, Proto, Rate (coloreado KB/s o MB/s), barra gráfica, paquetes, MB totales
- Panel lateral: inspector de flujo al seleccionar fila (hostname, detalles de conexión, tráfico, timeline)
- Almacenamiento interno: dict clave `(src, dst, proto)` con contadores de bytes/paquetes, cálculo de tasa, dirección, tipo de red (LAN/Internet)
- Actualiza cada 1 segundo via `set_interval`
- Filtra por host seleccionado

#### `tui/views/sniffer.py` (848 líneas)
**Inspector profundo de paquetes.**
- Selector de modo: "All traffic", "Per device", "RAW mode"
- Selector de dispositivo (solo en modo device)
- Botones START/PAUSE/STOP
- Estadísticas: paquetes, TCP, UDP, DNS, interfaz
- RichLog principal: resúmenes de paquetes con timestamp y color
- Panel de inspección: detalles completos del paquete (IP, TCP/UDP, DNS, payload raw, hexadecimal)
- Usa AsyncSniffer con soporte de filtro BPF

### 5.4 Widgets TUI

#### `tui/widgets/sidebar.py` (52 líneas)
`Sidebar`: título "AYANAMI", selector de interfaz global, ListView de navegación (Interfaces, Hotspot, Scanner, Monitor, Sniffer, Firewall). Auto-selecciona primera interfaz al montar.

#### `tui/widgets/interface_row.py` (41 líneas)
`InterfaceRow`: widget horizontal con nombre, tipo, estado y dos botones ("Global" y "X" para desconectar).

### 5.5 Estilos

#### `tui/styles/app.css` (724 líneas)
Stylesheet completo de Textual CSS. Tema oscuro inspirado en Tokyo Night:
- Fondo: `#1a1b26`
- Bordes: `#3b4261`
- Acentos: `#7aa2f7`, `#ff007c`
- Estilos para: Screen, Sidebar, DataTable, RichLog, Input, Button, Select, Label
- Estilos específicos por vista
- Barras de estadísticas, paneles, botones, scrollbars, colores de tasa

---

## 6. Archivos de Datos

### `cli/firewall_apps.json`
Apps registradas con listas de IPs para bloqueo por iptables. Estructura:
```json
{
  "TikTok": {"ips": ["189.247.197.48", ...], "blocked": false, "blocked_devices": []},
  "WhatsApp": {"ips": ["31.13.89.54", ...], "blocked": false, "blocked_devices": ["10.42.0.232"]},
  ...
}
```

### `cli/firewall_apps_state.json`
Estado de bloqueo de apps basado en DNS:
```json
{"global_blocked": [], "device_blocked": {"tiktok": ["10.42.0.132"]}}
```

---

## 7. Dependencias

### Del Sistema
- `NetworkManager` (nmcli) — interfaces y hotspot
- `iptables` — firewall
- `iftop` — monitoreo de ancho de banda (opcional)
- `conntrack` — reseteo de conexiones
- `dnsmasq` (via NetworkManager) — bloqueo DNS
- `arp-scan` — vendor MAC (TUI scanner)
- `nmap` — fingerprinting de host (TUI scanner)

### De Python
- `scapy` — captura y manipulación de paquetes
- `textual` — framework TUI
- `python-nmap` — integración con nmap
- `qrcode` — generación de códigos QR

---

## 8. Cómo Ejecutar

### Versión CLI:
```bash
sudo python3 cli/ayanami.py
```

### Versión TUI:
```bash
cd tui
python3 tui.py
# O con el venv:
source venv/bin/activate && python3 tui.py
```

**Nota:** La mayoría de funcionalidades requieren privilegios de root (iptables, hotspot nmcli, sniffing de paquetes).

---

## 9. Notas Arquitectónicas Importantes

1. **Doble interfaz:** El proyecto tiene dos UIs independientes (CLI y TUI) que comparten lógica similar pero no idéntica. Hay duplicación de código con variaciones (ej: scanner.py TUI tiene nmap/arp-scan que CLI no tiene).

2. **Firewall:** Usa la cadena FORWARD de iptables para todas las reglas de bloqueo. El bloqueo a nivel DNS funciona escribiendo líneas `address=/dominio/0.0.0.0` en archivos de configuración de dnsmasq bajo `/etc/NetworkManager/dnsmasq-shared.d/`, requiriendo reinicio del hotspot.

3. **Sniffer:** CLI usa `scapy.sniff()` bloqueante; TUI usa `AsyncSniffer` dentro de workers de Textual para captura no bloqueante.

4. **Estado:** El estado de bloqueo de apps se persiste en JSON. CLI usa `firewall_apps_state.json`, TUI usa `firewall_apps.json` (formatos diferentes).

5. **Seguridad:** Casi toda la funcionalidad requiere root. La función `require_root()` verifica `os.geteuid() != 0`.

6. **Manejo de errores:** Mínimo — la mayoría de funciones usa `try/except` básico o ignora excepciones. CLI usa print; TUI usa `self.notify()`.

7. **Hotspot y dnsmasq:** Hay problemas documentados en `PROBLEMAS.txt` sobre corrupción de configuración de dnsmasq al escribir reglas DNS del hotspot, con uso de archivos temporales y validación via `dnsmasq --test`.

---

## 10. Resumen de Archivos Fuente

| # | Archivo | Líneas | Propósito |
|---|---|---|---|
| 1 | `cli/ayanami.py` | 67 | Menú principal CLI |
| 2 | `cli/colors.py` | 14 | Colores ANSI |
| 3 | `cli/network.py` | 65 | Operaciones de interfaz de red |
| 4 | `cli/gateway.py` | 44 | Creación de hotspot |
| 5 | `cli/scanner.py` | 29 | Descubrimiento de vecinos |
| 6 | `cli/monitor_bw.py` | 63 | Monitoreo de ancho de banda |
| 7 | `cli/sniffer.py` | 171 | Sniffer de paquetes |
| 8 | `cli/firewall.py` | 787 | Firewall completo |
| 9 | `cli/firewall_apps.py` | 489 | Bloqueo por apps |
| 10 | `cli/reglasFirewall.py` | 599 | Script firewall independiente |
| 11 | `cli/firewall_apps.json` | 82 | Registro de IPs de apps |
| 12 | `cli/firewall_apps_state.json` | 8 | Estado de bloqueo de apps |
| 13 | `tui/tui.py` | 451 | Aplicación TUI principal |
| 14 | `tui/colors.py` | 14 | Colores ANSI (dup) |
| 15 | `tui/network.py` | 25 | Listado de interfaces (simplif.) |
| 16 | `tui/scanner.py` | 145 | Scanner mejorado |
| 17 | `tui/monitor_bw.py` | 76 | Wrapper de ancho de banda |
| 18 | `tui/sniffer.py` | 152 | Sniffer (compartido CLI/TUI) |
| 19 | `tui/firewall.py` | 513 | Firewall adaptado TUI |
| 20 | `tui/firewall_apps.py` | 363 | Gestión de apps TUI |
| 21 | `tui/styles/app.css` | 724 | Estilos Textual CSS |
| 22 | `tui/views/interfaces.py` | 88 | Vista de interfaces |
| 23 | `tui/views/hostspot.py` | 301 | Vista de hotspot con QR |
| 24 | `tui/views/scanner.py` | 267 | Vista de escáner con nmap |
| 25 | `tui/views/monitor.py` | 972 | Monitor de tráfico en tiempo real |
| 26 | `tui/views/sniffer.py` | 848 | Inspector profundo de paquetes |
| 27 | `tui/widgets/sidebar.py` | 52 | Barra lateral de navegación |
| 28 | `tui/widgets/interface_row.py` | 41 | Widget de fila de interfaz |
| 29 | `README.md` | 127 | Documentación del proyecto |
| 30 | `PROBLEMAS.txt` | 130 | Solución de problemas hotspot |
| 31 | `.gitignore` | 1 | Reglas de Git |
| | **Total** | **~6,824** | |
