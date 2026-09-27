# Manual de Usuario — Ayanami

> Herramienta de control de red y firewall con **Interfaz de Texto (TUI)** y una versión **CLI** para Linux.

Este manual explica la funcionalidad completa del programa, con **especial énfasis en el módulo de firewall**, que es el corazón de Ayanami: bloqueo por aplicaciones (dominios), lista blanca de IPs, gateway/NAT y backups de configuración.

```
▄████▄ ██  ██ ▄████▄ ███  ██ ▄████▄ ██▄  ▄██ ██
██▄▄██  ▀██▀  ██▄▄██ ██ ▀▄██ ██▄▄██ ██ ▀▀ ██ ██
██  ██   ██   ██  ██ ██   ██ ██  ██ ██    ██ ██
```

---

## Contenido

1. [Qué es Ayanami](#1-qué-es-ayanami)
2. [Requisitos e instalación](#2-requisitos-e-instalación)
3. [Cómo ejecutar el programa](#3-cómo-ejecutar-el-programa)
4. [Navegación de la TUI](#4-navegación-de-la-tui)
5. [Las vistas de la TUI](#5-las-vistas-de-la-tui)
6. [El Firewall](#6-el-firewall)
7. [Guardar y Cargar configuración](#7-guardar-y-cargar-configuración)
8. [Backups mensuales automaticos](#8-backups-mensuales-automáticos)
9. [Versión CLI](#9-versión-cli)
10. [Archivos de datos](#10-archivos-de-datos)
11. [Solución de problemas](#11-solución-de-problemas)
12. [Advertencias de seguridad](#12-advertencias-de-seguridad)

---

## 1. Qué es Ayanami

Ayanami es una herramienta de **control de red y firewall** escrita en Python 3, pensada para Linux. Combina:

- **TUI** (interfaz de texto con ratón y teclado, construida con Textual) — la forma recomendada y más completa de uso.
- **CLI** (menús interactivos por consola) — alternativa ligera.

Funcionalidades principales:

| Módulo | Qué hace |
|---|---|
| **Interfaces** | Lista interfaces de red, estados, IPs, tipo (WiFi/ethernet) y acciones. |
| **Hotspot** | Crea un punto de acceso WiFi con `nmcli` y muestra su contraseña (QR incluido). |
| **Scanner** | Detecta dispositivos en la red LAN y muestra detalles (MAC, fabricante, puertos). |
| **Monitor** | Monitorea ancho de banda por host en tiempo real. |
| **Sniffer** | Captura y analiza paquetes con Scapy (todo el tráfico, por dispositivo o RAW). |
| **Firewall** | Bloqueo por apps (dominios), lista blanca de IPs, gateway/NAT, backups. |
| **Sistema** | Dashboard tipo *fastfetch*: CPU, memoria, disco, procesos, temperatura y red. |

> ⚠️ **Permisos**: la mayoría de las funciones (firewall, hotspot, sniffer, scanner) requieren ejecutarse con **root** (`sudo`).

---

## 2. Requisitos e instalación

### Dependencias del sistema

- Linux con **NetworkManager** (`nmcli`).
- `iptables` (motor de reglas del firewall).
- `dnsmasq` (el bloqueo de aplicaciones usa el dnsmasq compartido de NetworkManager).
- `iftop` para el monitoreo de ancho de banda (opcional pero recomendado).
- `nmap` / `arp-scan` para el scanner (detección de fabricantes y puertos).

```bash
sudo apt update
sudo apt install -y network-manager iftop iptables dnsmasq nmap arp-scan
```

> En otras distribuciones usa tu gestor de paquetes (`pacman`, `dnf`, etc.).

### Dependencias de Python

Las dependencias están fijadas en `requirements.txt`. Se recomienda un entorno virtual:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Dependencias incluidas: `textual` (TUI), `scapy` (sniffer), `python-nmap`, `qrcode`, `rich`.

---

## 3. Cómo ejecutar el programa

### TUI (recomendada)

```bash
cd tui
sudo venv/bin/python tui.py
```

O activando el entorno:

```bash
source venv/bin/activate
sudo python tui/tui.py
```

### CLI

```bash
sudo python3 cli/ayanami.py
```

> Nota: la TUI también permite ejecutarse desde la raíz con `sudo venv/bin/python tui/tui.py`.

---

## 4. Navegación de la TUI

### Barra lateral

La barra lateral contiene:

- **Interfaz Global**: un selector (`Select`) con todas las interfaces de red. La interfaz elegida aquí es la "global" que usan otros módulos (scanner, monitor, sniffer y el gateway como **LAN**). Si se cambia la interfaz aquí, todos los módulos la usan.
- **Navegación** con 7 botones: Interfaces, Hotspot, Scanner, Monitor, Sniffer, Firewall y Sistema.

### Atajos de teclado

| Tecla | Acción |
|---|---|
| `q` | Salir |
| `r` | Actualizar la vista actual (no refresca el Firewall) |
| `Tab` / `Shift+Tab` | Navegar entre controles |
| `Esc` | Cerrar ventanas modales / salir de combos |
| `Ctrl+Q` | Salir (Textual) |

Dentro del programa también puedes usar el **ratón** (Textual lo soporta): clic en botones, switches, filas de tablas, etc.

> Nota: los modales (confirmaciones, registro de apps, selector de rutas) **no** se confirman con `Enter`; hay que hacer clic en el botón correspondiente (o Tab y Enter sobre él).

---

## 5. Las vistas de la TUI

> En esta sección, para cada vista se explica **qué muestra** (cada columna, panel y contador) y **qué hace cada botón**. Todas las vistas usan la **interfaz global** elegida en la barra lateral, así que si ves datos vacíos o de la interfaz equivocada, revisa primero ese selector.

---

### 5.1 Interfaces

Muestra las interfaces de red del equipo, tal como las reporta `nmcli device status`.

#### Qué muestra

| Columna | Significado |
|---|---|
| **Interfaz** | Nombre de la interfaz (`wlan0`, `eth0`, `lo`...). |
| **Tipo** | El icono indica el tipo físico: `◈` WiFi, `┃` cable (**ethernet**), `◇` otros (lo, bridge, etc.). |
| **Estado** | `●` **verde** = conectada; `●` **rojo** = desconectada o no disponible. |
| **Acciones** | Botones **Global** y **X** de cada fila (ver abajo). |

> El dato más importante aquí es cuál interfaz está marcada como **global**: es la que después usan Scanner, Monitor, Sniffer, Hotspot y el gateway (como LAN). En la tabla **no hay marca visible**; se ve en la barra lateral.

#### Botones

| Botón | Dónde | Qué hace |
|---|---|---|
| **Refresh** | Arriba, junto al título | Vuelve a consultar las interfaces y repinta la lista. |
| **Global** (verde) | Por fila | Marca esa interfaz como **global** (sincroniza el selector de la barra lateral). |
| **X** (rojo) | Por fila | **Desconecta** la interfaz con `nmcli device disconnect` (p.ej. corta el WiFi). |

#### Cómo interpretarla

- Para usar Ayanami como **router (gateway)**, la interfaz global debe ser la **LAN** (la que apunta a tus dispositivos), y la **WAN** (la que tiene internet) se elige aparte en la pestaña Config del Firewall.
- Una interfaz "desconectada" puede estar sin cable/WiFi, apagada por software, o sin configuración de red (`unavailable` en NetworkManager).

---

### 5.2 Hotspot

Crea un punto de acceso WiFi en la interfaz global con `nmcli dev wifi hotspot` y muestra sus credenciales (incluido un QR).

#### Qué muestra

| Zona | Contenido |
|---|---|
| **Banner** | Interfaz en uso (`◉ wlan0`) y estado del AP: `● Activo` (verde) / `○ Inactivo` (gris). |
| **Configuración** | Campos **SSID** (nombre de la red) y **PASSWORD** (se escribe oculto, mínimo 8 caracteres). |
| **Actividad** | Bitácora (log) con los pasos y mensajes de error. |

#### Botones

| Botón | Qué hace |
|---|---|
| **CREAR HOTSPOT** (verde) | Valida los campos (SSID no vacío + contraseña ≥ 8), crea el AP en la interfaz global y muestra las credenciales. |
| **MOSTRAR CONTRASEÑA** | Consulta `nmcli dev wifi show-password` y muestra **SSID, contraseña, seguridad y frecuencia** de las redes, junto con su **código QR ASCII** escaneable. |

#### Cómo interpretar el log

Los mensajes del log usan colores: **amarillo** = paso en curso, **rojo** = error (SSID vacío, contraseña corta, sin interfaz global, fallo de `nmcli`). Al final, si todo salió bien, verás la contraseña y el QR.

> Consejos útiles:
> - El AP se crea sobre la **interfaz global**: elegir en la barra lateral antes de pulsar CREAR.
> - Si un hotspot ya está activo y se crea otro, `nmcli` reemplaza la configuración actual.
> - Después de **bloquear/desbloquear apps** (Firewall), NetworkManager se reinicia y **el hotspot se corta**; hay que recrearlo.

---

### 5.3 Scanner

Detecta los dispositivos visibles en la red usando `ip neigh` (tabla de vecinos ARP) y enriquece los datos con `arp-scan` (fabricante MAC).

#### Qué muestra

**Barra de estadísticas** (arriba):

| Contador | Significado |
|---|---|
| **Interfaz** | Sobre qué interfaz se escaneó (la global). |
| **Dispositivos** | Cantidad de hosts encontrados en el último escaneo. |
| **Último Escaneo** | Hora del último barrido (HH:MM:SS). |

**Tabla de dispositivos** — columnas:

| Columna | Significado |
|---|---|
| **IP** | Dirección IP del dispositivo. |
| **HOSTNAME** | Nombre de host (resolución inversa). Si no se puede resolver, sale `unknown`. |
| **MAC** | Dirección física (`?` si no se pudo leer la tabla ARP). |
| **VENDOR** | Fabricante según el prefijo MAC (`arp-scan`). `Unknown` si no coincide en la base. |
| **STATE** | Estado del vecino ARP: `REACHABLE` (responde ahora), `STALE`/`DELAY`/`PROBE` (visto hace poco, quizá dormido), `FAILED` (no contesta), `INCOMPLETE`. |
| **INTERFACE** | Por qué interfaz se ve el dispositivo. |

**Panel lateral** (al seleccionar una fila): análisis de ese host con `nmap`:

| Sección | Qué muestra |
|---|---|
| **INFORMACIÓN GENERAL** | IP, hostname, MAC, fabricante, estado (up/down) e interfaz. |
| **FINGERPRINT** | **Sistema Operativo** estimado por nmap (`Unknown` si no se pudo deducir). |
| **SERVICIOS DETECTADOS** | Puertos abiertos con `puerto/protocolo`, servicio (`http`, `ssh`...), producto, versión y estado (`open`). Si no hay ninguno: "No se detectaron puertos abiertos". |

#### Botones

| Botón | Qué hace |
|---|---|
| **ESCANEAR** | Relanza `ip neigh` + `arp-scan` y actualiza la tabla y los contadores. |

#### Cómo interpretarla

- **Un dispositivo `REACHABLE`** está conectado y activo ahora mismo; **`STALE`** significa "visto hace poco" (móviles en reposo suelen aparecer así). No confundir con una falla.
- **VENDOR `Unknown`** no es un error: significa que el prefijo MAC no está en la base de `arp-scan`.
- Seleccionar una fila lanza un **nmap** (tarda unos segundos): verás "Analizando host..." mientras corre.
- El **panel de detalle** siempre muestra el último dispositivo seleccionado; hay que volver a pulsar ESCANEAR para redescubrir hosts nuevos.

---

### 5.4 Monitor

Muestra el **tráfico de red en tiempo real** de la interfaz global, agrupado por flujos (origen + destino + protocolo).

#### Qué muestra

**Barra de estadísticas:**

| Contador | Significado |
|---|---|
| **Interfaz** | Interfaz capturada (la global). |
| **Flows** | Cantidad de flujos distintos vistos hasta ahora. |
| **Packets** | Paquetes totales procesados. |
| **Actualización** | Hora del último refresco de la tabla (cada 1 s). |

**Tabla de flujos** (ordenada de mayor a menor velocidad):

| Columna | Significado |
|---|---|
| **SOURCE** | IP de origen del flujo. |
| **DESTINATION** | IP de destino (si es un host remoto, abajo verás su nombre en el inspector). |
| **SERVICE** | Servicio según el **puerto de destino**: HTTP(80), HTTPS(443), DNS(53), SSH(22), FTP(21), SMTP(25), NTP(123), HTTP-ALT(8080), MYSQL(3306), MONGODB(27017)... `UNKNOWN` si el puerto no está mapeado. |
| **PROTO** | `TCP`, `UDP` o `IP` (otros protocolos). |
| **RATE** | Velocidad actual: **verde** < 100 KB/s, **amarillo** < 1 MB/s, **rojo** ≥ 1 MB/s. |
| **GRAPH** | Barra visual de la velocidad (máx. 10 bloques ≈ 100 KB/s; más rápido → más rellena). |
| **PACKETS** | Paquetes acumulados en el flujo. |
| **TOTAL** | Bytes acumulados del flujo (en MB). |

**Panel FLOW INSPECTOR** (al seleccionar una fila):

| Sección | Qué muestra |
|---|---|
| **REMOTE HOST** | Nombre de host del destino (resolución inversa). |
| **CONNECTION** | SRC, DST, SERVICE, PROTO, puertos origen (SPORT) y destino (DPORT), dirección del flujo (**FLOW**: `OUTBOUND`, o `UPLOAD`/`DOWNLOAD` si filtrás por un host) y tipo de red (**NETWORK**: `LAN` si el destino es IP privada, `INTERNET` si es pública). También el **TTL** inicial del paquete. |
| **TRAFFIC** | RATE (KB/s), PACKETS y TOTAL (MB) del flujo. |
| **TIMELINE** | FIRST (cuándo se vio el flujo por primera vez) y LAST (último paquete). |

#### Controles

| Control | Qué hace |
|---|---|
| **Selector de host** | Filtra la vista a un dispositivo concreto (`hostname (IP)`) o **Toda la red**. Con un host elegido, el inspector marca cada flujo como **UPLOAD** (el host envía) o **DOWNLOAD** (el host recibe). |
| **↻** | Recarga la lista de dispositivos del selector (útil cuando aparece un host nuevo). |
| **INICIAR** (verde) | Empieza a capturar en la interfaz global y activa el refresco cada 1 s. |
| **PAUSAR** | Detiene la captura y *congela* la tabla (la última actualización queda fija y el botón **INICIAR** se habilita de nuevo para retomar). |

#### Cómo interpretarla

- **Un flujo a una IP privada (`192.168.x`, `10.x`, `172.16-31.x`) = tráfico LAN**; una IP pública = salida a **INTERNET**.
- Ver mucho tráfico a `53/DNS` o `UNKNOWN/UDP` en el `RATE` alto suele indicar resolución DNS o aplicaciones que usan puertos no estándar.
- El RATE se calcula sobre la última ventana de 1 segundo: es una **instantánea**, no un promedio acumulado.

---

### 5.5 Sniffer

Captura paquetes de la interfaz global con Scapy y muestra el **último paquete** en detalle, con contadores por protocolo.

#### Qué muestra

**Indicador de estado** (junto al título): `DETENIDO` (rojo) → `CAPTURANDO` (verde) → `PAUSADO` (amarillo).

**Barra de información:**

| Contador | Significado |
|---|---|
| **Paquetes** | Total capturado desde el INICIAR. |
| **TCP / UDP / DNS** | Desglose por protocolo (un paquete puede sumar a varios, p.ej. un DNS sobre UDP). |
| **Interfaz** | Interfaz en la que se captura (la global). |

**Línea del último paquete** (formato que conviene saber leer):

```
14:32:05 192.168.1.5 > 8.8.8.8 TCP/HTTPS 51234->443 F=PA [1200B]
```

| Parte | Significado |
|---|---|
| `14:32:05` | Hora de captura. |
| `192.168.1.5 > 8.8.8.8` | Origen **>** destino. |
| `TCP/HTTPS` | Protocolo y servicio del puerto de destino (HTTP, HTTPS, DNS, SSH, FTP, SMTP, POP3, IMAP, NTP, HTTP-ALT, MYSQL, MONGO). |
| `51234->443` | Puerto origen -> puerto destino. |
| `F=PA` | Banderas TCP (S=SIN, A=ACK, P=PSH, F=FIN, R=RST). |
| `[1200B]` | Tamaño del paquete. |

**Panel de detalle** — tablas por capa del paquete:

| Tabla | Campos que muestra |
|---|---|
| **ETHER** | MAC de origen (src) y destino (dst) — quién lo emite y a qué dispositivo va. |
| **IP** | De, Para, Protocolo (`TCP`/`UDP`/`IP`) y Tamaño en bytes. |
| **TCP** | Puertos origen → destino (con el servicio entre paréntesis), Banderas y Datos (bytes de carga útil). |
| **UDP** | Puertos origen → destino (con servicio si es conocido). |
| **DNS** | Tipo (`Consulta`/`Respuesta`), la Consulta (nombre de dominio) y hasta 3 Respuestas (IPs/registros). |

#### Controles

| Control | Qué hace |
|---|---|
| **Selector de captura** | Muestra "Toda la red" o los dispositivos detectados (`IP (MAC)`). El botón **↻** vuelve a escanear la red para actualizarlo. |
| **INICIAR** (verde) | Empieza la captura en la interfaz global y activa los contadores (los botones PAUSAR/DETENER se habilitan). |
| **PAUSAR** (amarillo) | Congela la captura; el botón cambia a **CONTINUAR** (verde) para reanudar. |
| **DETENER** (rojo) | Corta la captura, apaga los contadores y borra el detalle. |

#### Cómo interpretarla

- **La captura lee toda la interfaz global**: los paquetes mostrados no distinguen entre tráfico de la máquina y tráfico en tránsito (por eso la vista es útil incluso si Ayanami actúa de router).
- Si solo se va a analizar **un dispositivo**, elegirlo en el selector antes de INICIAR y tener ese host en mente al leer la tabla (mostrará su IP como origen o destino).
- Un paquete **DNS** suma al contador UDP (va por UDP normalmente) **y** al contador DNS: los desgloses no suman "limpio".
- Capturar en una red muy cargada es normal ver cientos de paquetes por segundo; la tabla solo muestra el **último** paquete.

---

### 5.6 Sistema

Dashboard tipo *fastfetch* que se **auto-refresca cada 1 segundo** (no tiene botones). Es la vista de estado general de la máquina.

#### Qué muestra por sección y cómo leerla

| Sección | Contenido | Cómo interpretarla |
|---|---|---|
| **Cabecera** | `AYANAMI | usuario | hostname | OS | kernel | uptime | N proc | N users | fecha/hora` | Resumen de identidad del equipo. |
| **SISTEMA** | User, Shell, Host, GPU, OS, Kernel, Uptime, Date. | GPU aparece `---` si no se detectó. |
| **CPU** | Modelo, Cores, **Temp** y **Load** (1/5/15 min) + barra de uso. | La **barra** = carga actual vs núcleos (load de 1 min / nº de núcleos). El load se colorea como semáforo (verde < 50 %, ámbar 50–79 %, rojo ≥ 80 %). |
| **MEMORIA RAM** | Usado de total + barra; líneas **Buffer** y **Cached**. | La **barra** marca el porcentaje usado. Buffer/Cached no son "memoria ocupada por apps": Linux los usa de caché de disco y se libera bajo presión. |
| **MEMORIA SWAP** | (solo si existe) Usado de total + barra. | Swap en uso alto → el equipo está quedándose sin RAM. |
| **DISCO** | Por cada partición: punto de montaje, Total, Usado, Libre + barra. | Cada fila es una partición (o `/` y `/home` si son separadas). Color según % usado. |
| **NETWORK** | Hasta 3 interfaces con icono (`≈≈` wifi, `↑↓` cable), tipo, IP; **Gateway**; **DNS**; **RX ↓ / TX ↑ / Total**. | Solo muestra interfaces **conectadas**. Gateway/DNS vacíos (`---`) = sin salida configurada. RX = tráfico recibido acumulado, TX = enviado. |
| **PROCESOS** | Total de procesos, **TOP 8 por CPU** (con % y punto de semáforo) y **TOP 3 por memoria**. | Útil para detectar qué proceso consume el equipo. |

#### Semaforización (vale para todas las barras)

- **Verde** → uso < 50 % — normal.
- **Ámbar** → uso entre 50 % y 80 % — atención.
- **Rojo** → uso ≥ 80 % — alto; revisá qué está consumiendo.

---

### 5.7 Firewall
Se explora en detalle en la [sección 6](#6-el-firewall).

---

## 6. El Firewall 

La vista **Firewall** tiene **3 pestañas**: **Apps**, **Lista Blanca** y **Config**. Se navega haciendo clic en las pestañas superiores.

**Cómo funciona el firewall por dentro:**

- El **bloqueo de aplicaciones** se hace por **dominios** usando el dnsmasq compartido de NetworkManager: cada dominio bloqueado se escribe como `address=/{dominio}/0.0.0.0` en `/etc/NetworkManager/dnsmasq-shared.d/ayanami-block.conf`. Al cambiar el estado se **reinicia NetworkManager** (para que dnsmasq recargue) y se vacían las conexiones con `conntrack -F`.
- La **lista blanca** se aplica con **iptables** insertando reglas `ACCEPT` en la **primera posición** (`-I ... 1`) de las cadenas `FORWARD` y `PREROUTING` (las reglas blancas ganan a cualquier `DROP`). Además, para las IPs exentas el DNS se **fuerza a 8.8.8.8** (DNAT a puerto 53) para que no pasen por el dnsmasq de Ayanami.
- El **gateway/NAT** habilita el reenvío de IP (`net.ipv4.ip_forward=1`), hace `MASQUERADE` por la interfaz WAN y redirige el DNS (puerto 53) hacia la IP de la LAN.

> 💡 **Orden de aplicación**: primero se configura el gateway (si se usa Ayanami como router) y luego el bloqueo de apps / lista blanca.

---

### 6.1 Pestaña Apps — bloqueo por aplicaciones

Esta pestaña te permite registrar "aplicaciones" (cada una con su lista de dominios) y bloquearlas/desbloquearlas con un interruptor.

#### Barra de herramientas

| Control | Función |
|---|---|
| **Buscar app...** (Input) | Filtra por nombre de app **o por dominio**. |
| **Filtrar** (Select) | `Todas` · `Bloqueadas` · `Desbloqueadas` · o por tipo: `Videojuegos`, `Plataforma`, `Social`, `DNS`, `Otro`. |
| **Ordenar** (Select) | Nombre A-Z o Z-A. |
| **Registrar** (botón) | Abre el modal para dar de alta una app nueva. |
| **Acciones rápidas** (Select) | `Bloquear todo` / `Desbloquear todo` — **solo afecta a las apps visibles con el filtro/búsqueda actual**, no a todas. |

#### Registrar / Modificar una app

El modal pide:

| Campo | Detalle |
|---|---|
| **Nombre** | Ej: `tiktok`. Obligatorio y no puede repetirse. |
| **Tipo** | `Videojuegos`, `Plataforma`, `Social`, `DNS` u `Otro`. Se muestra como etiqueta de color en la fila y se puede filtrar por él. |
| **Dominios** | Uno por línea. Al menos uno. Validados con un patrón de dominio (ej: `example.com`). |
| **Bloqueada** | Interruptor: al registrar sale **activado** por defecto (así creas la app ya bloqueada). |

Botones **Guardar** y **Cancelar**.

En la lista, cada fila muestra:

- Barra de acento (roja = bloqueada, verde = desbloqueada).
- Nombre, tipo (tag de color) y número de dominios.
- Estado (`BLOQUEADA` / `DESBLOQUEADA`).
- Los dominios asociados.
- Acciones: **Switch** (bloquear/desbloquear), **Modificar** y **Eliminar** (con confirmación).

#### Comportamiento del bloqueo

- Al activar el switch de una app: guarda el estado, escribe los dominios en el archivo de dnsmasq, y tras **1.5 segundos sin más cambios** (debounce) reinicia NetworkManager y limpia `conntrack -F`. Esto evita reiniciar la red de forma continua mientras editas varias apps.
- **Desbloquear todo** elimina el archivo `ayanami-block.conf` completo (desbloquea todas las apps de una vez).
- Las operaciones largas corren en segundo plano (workers) para no congelar la interfaz.

> ⚠️ Al reiniciar NetworkManager, la red **se corta momentáneamente** (incluido el hotspot). Es el mecanismo que hace efectivas las reglas.

---

### 6.2 Pestaña Lista Blanca — exención de IPs

Sirve para **exentar** dispositivos (o redes) de todas las reglas de bloqueo.

#### Formatos aceptados

| Formato | Ejemplo |
|---|---|
| **IP** | `192.168.1.100` |
| **CIDR** | `192.168.1.0/24` |
| **Rango** | `10.0.0.1-10.0.0.255` |

El input muestra el placeholder con los tres formatos; se agrega con el botón **Agregar** o con **Enter**.

#### Cómo funciona

- La lista se guarda en `whitelist.json` (formato `{"whitelist": [...]}`).
- Al agregar/quitar una entrada, las reglas **se aplican automáticamente** (no hay botón "Aplicar"): se borran todas las reglas anteriores marcadas con el comentario `ayanami-wl` y se insertan de nuevo las ACCEPT y el DNAT de DNS.
- Las IPs exentas **resuelven DNS externamente (8.8.8.8)**, saltándose el dnsmasq de Ayanami, de modo que no les afectan los bloqueos por dominio.
- Cada entrada tiene un botón **Quitar** (con confirmación).
- Los formatos se validan y el tag muestra el tipo de entrada (IP azul, CIDR violeta, RANGO ámbar).

> 💡 El orden de las reglas importa: las reglas de la lista blanca se insertan en la posición 1, por encima de cualquier bloqueo, por eso siempre "ganan".

---

### 6.3 Pestaña Config — Gateway, estado y limpieza

#### Configurar el Gateway (NAT)

Convierte al equipo en **router/gateway** de la red:

1. En el selector elige la **interfaz con internet** (WAN).
2. Pulsa **Configurar Gateway**. La **LAN** se toma de la interfaz global (barra lateral).
3. Ayanami hace:
   - Habilita `net.ipv4.ip_forward=1` (y lo persiste en `/etc/sysctl.conf`).
   - Añade la regla `MASQUERADE` en `POSTROUTING` por la WAN.
   - Redirige el DNS (puerto 53 TCP/UDP) de toda la LAN hacia la **IP dinámica** de la interfaz LAN (se calcula en vivo en cada configuración).
   - Guarda los datos de referencia en `firewall_config.json` (`wan_iface`, `lan_iface`, `dns_target`) para poder restaurarlos después.

#### Ver Estado

Muestra en el log las 4 secciones de diagnóstico:

- **IP FORWARD** → valor actual de `net.ipv4.ip_forward`.
- **REGLAS DNS** → contenido actual de `ayanami-block.conf` (dominios bloqueados).
- **FORWARD** → `iptables -L FORWARD` con números de línea.
- **NAT** → `iptables -t nat -L` con números de línea.

#### Limpiar Firewall

Borra **todo** el estado del firewall:

- Elimina el archivo de bloqueo de dnsmasq.
- `iptables -F FORWARD` y `iptables -t nat -F` (flush total).
- Desbloquea **todas** las apps en `apps_firewall.json`.
- `conntrack -F`.

> ⚠️ Pide confirmación explícita. No borra `whitelist.json` ni `firewall_config.json` (la configuración guardada se conserva), pero **sí se borra la configuración del gateway**: se debe configurar de nuevo.

#### Copia de Seguridad (Guardar/Cargar)

El selector **Copia de Seguridad** (en la misma sección Config) ofrece **Guardar Config** y **Cargar Config**. Se explica en detalle en la [sección 7](#7-guardar-y-cargar-configuración).

---

## 7. Guardar y Cargar configuración

Toda la configuración del firewall se guarda en **un único archivo**: `firewall_config.json` (en la raíz del proyecto). Contiene:

```json
{
  "version": 1,
  "exported_at": "2026-09-25T12:00:00",
  "hostname": "ayanami",
  "gateway": { "wan_iface": "eth0", "lan_iface": "wlan0", "dns_target": "10.42.0.1", "applied_at": "..." },
  "stats": { "whitelist_count": 3, "apps_count": 22, "blocked_count": 5, "domains_count": 120 },
  "whitelist": ["10.0.0.5", "192.168.1.0/24"],
  "apps": { "...": { "domains": [], "blocked": false, "type": "Videojuegos" } }
}
```

> El campo de **gateway** (`wan_iface`, `lan_iface`, `dns_target`) es **información de referencia**: al restaurar no se usa tal cual, sino que se **recalcula** la IP de la LAN dinámicamente (con respaldo al valor guardado si no se puede).

### Guardar Config

1. En la pestaña Config → selector **Copia de Seguridad** → **Guardar Config**.
2. Se abre un **selector de rutas** donde puedes navegar el árbol de directorios (con `⬆ Subir` o tecla `b`) o escribir la ruta a mano.
3. Al confirmar, exporta lista blanca + apps + datos de referencia del gateway:
   - Si se selecciona solo una **carpeta** (sin nombre de archivo), se guarda `firewall_config.json` dentro de esa carpeta (no se puede escribir sobre un directorio).
   - Si el destino es diferente al canónico, **también se actualiza la copia canónica** de la raíz para que el backup mensual funcione.
   - Además crea un **backup mensual inmediato** (`backups/firewall_config-AAAA-MM.json`) y limpia los backups viejos.

### Cargar Config

1. **Copia de Seguridad** → **Cargar Config**.
2. Seleccionar el archivo en el selector de rutas (o escríbelo).
3. El archivo se **valida** antes de confirmar:
   - Debe ser un JSON de configuración real (con `version`, `apps` y `whitelist`). Cualquier otro archivo (imagen, texto, JSON random) se rechaza con un aviso y **no se toca nada**.
4. Tras confirmar, se **reaplica todo**:
   - Escribe `whitelist.json` y `apps_firewall.json`.
   - Regenera las reglas iptables de la lista blanca.
   - Regenera el bloqueo de dominios en dnsmasq.
   - Reconfigura el gateway/NAT si había uno guardado.
   - Reinicia NetworkManager y refresca las listas en pantalla.

> 💡 Los **backups mensuales** (`backups/firewall_config-AAAA-MM.json`) también se pueden cargar: ya que tienen la misma estructura.

---

## 8. Backups mensuales automáticos

Ayanami conserva **backups mensuales** con retención de los **últimos 3 meses** (los más viejos se borran de forma programada).

- **Dónde**: `backups/firewall_config-AAAA-MM.json`.
- **Cuándo**: una vez al mes vía un **timer de systemd** (no dentro de la app).
- **Cómo**: copia el `firewall_config.json` al bucket del mes. Si el archivo canónico aún no existe, lo genera con el estado actual antes de respaldarlo.
- La copia canónica siempre se mantiene al día (al exportar a otra ruta y al configurar el gateway se actualiza automáticamente).

### Instalar el timer

```bash
sudo systemd/install_backup_timer.sh
```

El instalador detecta automáticamente la raíz del repo y el Python del venv (puedes forzar con las variables `AYANAMI_DIR` y `AYANAMI_VENV`). Genera:

- `/etc/systemd/system/ayanami-backup.service` — ejecuta `tui/firewall_config.py`.
- `/etc/systemd/system/ayanami-backup.timer` — `OnCalendar=monthly`, con `Persistent=true` (si el equipo estaba apagado, corre al encender).

### Desinstalar

```bash
sudo systemd/install_backup_timer.sh --uninstall
```

### Verificar / ejecutar a mano

```bash
systemctl list-timers ayanami-backup.timer --no-pager   # ¿cuándo se hace el sig respaldo?
sudo systemctl start ayanami-backup.service             # backup ahora mismo
```

Al ejecutar el servicio se mostrará en consola algo como:

```
[ayanami-backup] backup: /ruta/backups/firewall_config-2026-09.json
[ayanami-backup] eliminados: firewall_config-2026-06.json
```

---

## 9. Versión CLI

La versión CLI (`cli/`) es una alternativa por menús de texto. Ejecución:

```bash
sudo python3 cli/ayanami.py
```

### Menú principal

| Opción | Acción |
|---|---|
| 1 | Ver interfaces de red |
| 2 | Desconectar interfaz |
| 3 | Crear hotspot |
| 4 | Ver detalles del hotspot |
| 5 | Ver dispositivos en la red |
| 6 | Monitorear ancho de banda (`iftop`) |
| 7 | Sniffer de paquetes |
| 8 | **Firewall** |
| 0 | Salir |

### Menú Firewall (CLI) — 12 opciones

| # | Opción | Regla |
|---|---|---|
| 1 | **Configurar gateway (NAT)** | IP forward + `MASQUERADE` por la interfaz elegida + DNAT DNS a `10.42.0.1`. |
| 2 | Bloquear dispositivo (IP) | `-s <ip> -j DROP` en FORWARD. |
| 3 | **Bloqueo global (IP destino)** | `-d <ip> -j DROP`. |
| 4 | Bloquear IP destino a dispositivo | `-s <src> -d <dst> -j DROP`. |
| 5 | Bloquear red completa (CIDR) | `-d <cidr> -j DROP`. |
| 6 | Bloquear rango de IPs | Expande rango (ej: `192.168.1.100-200`) IP por IP. |
| 7 | Bloquear IP para rango de dispositivos | Combina rango de dispositivos + IP destino. |
| 8 | Gestionar apps (bloqueo por dominio) | Menú `firewall_apps.py` (bloqueo global o por dispositivo). |
| 9 | Ver reglas | `iptables -L FORWARD -n --line-numbers`. |
| 10 | Eliminar regla | `iptables -D FORWARD <número>`. |
| 11 | Flush de conexiones | `conntrack -F`. |
| 12 | **Limpiar todo** | Flush FORWARD + borra `ayanami-block.conf` + flush POSTROUTING + conntrack. |

> La CLI soporta además el **bloqueo por dispositivo vía dnsmasq** (`address=/dominio/0.0.0.0#source=IP`) y el bloqueo de **QUIC/UDP 443** (funciones que la TUI no expone todavía).

---

## 10. Archivos de datos

| Ruta | Contenido |
|---|---|
| `whitelist.json` | Lista blanca: `{"whitelist": ["10.0.0.5", ...]}` |
| `apps_firewall.json` | Apps de la TUI: `{"App": {"type": ..., "domains": [...], "blocked": bool}}` |
| `firewall_config.json` | Configuración unificada (whitelist + apps + gateway + stats). Es la copia canónica. |
| `backups/firewall_config-AAAA-MM.json` | Backups mensuales (retención: 3 meses). |
| `/etc/NetworkManager/dnsmasq-shared.d/ayanami-block.conf` | Dominios bloqueados: `address=/{dominio}/0.0.0.0` |
| `/etc/NetworkManager/dnsmasq-shared.d/ayanami-device-block.conf` | Bloqueo por dispositivo (solo CLI). |
| `/etc/sysctl.conf` | Persistencia de `net.ipv4.ip_forward=1`. |
| `cli/firewall_apps_state.json` | Estado de bloqueos de la CLI: `{"global_blocked": [], "device_blocked": {...}}` |

---

## 11. Solución de problemas

| Problema | Solución |
|---|---|
| **`nmcli` no disponible** | Instalar NetworkManager o ejecuta las funciones manualmente. |
| **`scapy` falla (sniffer)** | `pip show scapy` y probar co: `python3 -c "from scapy.all import sniff; print('OK')"`. |
| **`iftop` no está instalado** | `sudo apt install iftop`. |
| **Errores de permisos** | Reintentar con `sudo` (iptables, sysctl, hotspot, arp-scan necesitan root). |
| **La TUI no arranca** | Verificar que `textual` esté instalado y ejecuta desde la carpeta `tui/`. |
| **Cargo un archivo y dice "no es válido"** | El archivo debe ser una configuración de Ayanami exportada (JSON con `version`, `apps`, `whitelist`). Los backups del mes sirven. |
| **Al desbloquear apps la red se corta** | Es normal: reiniciar NetworkManager es lo que aplica las reglas DNS. |
| **El hotspot falla ("IP config unavailable")** | Revisar que no haya un `.conf` malformado en `/etc/NetworkManager/dnsmasq-shared.d/`. Consulta `PROBLEMAS.txt` del proyecto. |
| **La lista de apps no se refresca** | Cambiar de pestaña dentro de Firewall o hacer una acción (la tecla `r` no refresca el panel Firewall). |

---

## 12. Advertencias de seguridad

- Muchas funciones requieren **root** y manipulan `iptables` y `dnsmasq`: **afectan la conectividad de la red**. Usar Ayanami solo en redes que administras o con autorización.
- El **sniffer** captura paquetes: evítar en redes ajenas.
- **Reiniciar NetworkManager** (consecuencia de bloquear/desbloquear apps) corta momentáneamente la red, incluido el hotspot.
- **Limpiar Firewall** elimina el gateway configurado: se tiene que configurar de nuevo.
- Antes de **cerrar** sesiones o firewalls críticos, considerar exportar la configuración (Copia de Seguridad → Guardar Config) para poder recuperarla con Cargar Config.