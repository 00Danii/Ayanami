# Ayanami

Ayanami es una herramienta CLI para inspección, monitoreo y control básico de una red local desde Linux. Agrupa utilidades para listar interfaces, crear un hotspot, detectar vecinos (ARP/ip neigh), esnifar tráfico con Scapy, monitorear ancho de banda e imponer bloqueos simples con iptables. 

```text
▄████▄ ██  ██ ▄████▄ ███  ██ ▄████▄ ██▄  ▄██ ██ 
██▄▄██  ▀██▀  ██▄▄██ ██ ▀▄██ ██▄▄██ ██ ▀▀ ██ ██ 
██  ██   ██   ██  ██ ██   ██ ██  ██ ██    ██ ██

```
---

**Estado:** herramienta en Python 3, pensada para ejecutarse con permisos de root para la mayoría de sus funcionalidades (iptables, iftop, nmcli, sniffing).

## Contenido del repositorio

- `ayanami.py`: Entrada principal; menú interactivo que orquesta las opciones.
- `colors.py`: Constantes ANSI para colorear la salida.
- `network.py`: Funciones para listar interfaces (`nmcli`), desconectar y obtener detalles.
- `gateway.py`: Crear un hotspot con `nmcli` y mostrar contraseña.
- `scanner.py`: Detectar vecinos en la LAN usando `ip neigh`.
- `monitor_bw.py`: Interfaz para lanzar `iftop` y monitorear ancho de banda.
- `sniffer.py`: Sniffer basado en Scapy (varios modos: whole, por dispositivo, RAW).
- `firewall.py`: Funciones para aplicar reglas `iptables` (bloquear IPs, listar, borrar, flush) y menú de firewall.
- `firewall_apps.py`: Gestión simple de aplicaciones con IPs asociadas (persistencia en `firewall_apps.json`).
- `firewall_apps.json`: Archivo de datos (registro de apps/ips).

## Requisitos

- Sistema Linux con NetworkManager (`nmcli`).
- `iptables` disponible en el sistema.
- `iftop` para el monitoreo de ancho de banda (opcional pero recomendado).
- Python 3.8+.
- Módulo Python `scapy` para el sniffer: `pip3 install scapy`.
- Ejecutar la mayoría de comandos con privilegios de root (sudo) para que `iptables`, `nmcli` y `sniff` funcionen correctamente.

Instalación (ejemplo):

```bash
sudo apt update
sudo apt install -y network-manager iftop iptables
pip3 install scapy
```

Ejecución:

```bash
sudo python3 ayanami.py
```

> Nota: Ejecutar con `sudo` o como root es necesario para manipular reglas de firewall, crear hotspots y capturar paquetes.

## Uso / Menú principal

Al ejecutar `ayanami.py` verás un menú con secciones claras:

- RED / INTERFACES
  - Ver Interfaces de Red (nmcli) — muestra `nmcli device status`.
  - Desconectar interfaz — desconecta una interfaz seleccionada con `nmcli device disconnect`.

- HOTSPOT / GATEWAY
  - Crear hotspot — lanza `nmcli dev wifi hotspot ifname <iface> ssid <ssid> password <pwd>`.
  - Ver detalles de hotspot — muestra la contraseña vía `nmcli dev wifi show-password`.

- ESCANEO / MONITOREO
  - Ver dispositivos en la red — usa `ip neigh` para listar vecinos (IPs/MACs/interfaces).
  - Monitorear ancho de banda — lanza `iftop` en una interfaz, con opción de filtrar por host.

- ANÁLISIS / SEGURIDAD
  - Sniffer de paquetes — menú con 3 modos: todo el tráfico, por dispositivo (filtro `host`), RAW (pkt.show()).
  - Firewall — menú para aplicar bloqueos con `iptables` (bloquear dispositivo, bloqueo global, bloquear IP destino sólo para un origen, bloquear apps por IPs, ver reglas, eliminar regla, limpiar todo).

## Detalle por módulo

- `network.py`
  - `show_devices()`: imprime salida de `nmcli device status`.
  - `get_interfaces()`, `get_interfaces_detailed()`: devuelven listas para selección en otros menús.
  - `disconnect_interface()`: interacción para desconectar.

- `gateway.py`
  - `create_hotspot()`: pide interfaz, SSID y contraseña; crea hotspot con `nmcli`.
  - `show_hotspot_password()`: muestra la contraseña del hotspot.

- `scanner.py`
  - `get_neighbors()`: parsea `ip neigh` buscando entradas REACHABLE/STALE y devuelve lista de dicts `{ip, mac, iface}`.
  - `show_neighbors()`: imprime la lista.

- `monitor_bw.py`
  - Usa `iftop` para monitorear tráfico en la interfaz elegida. Puede monitorear toda la red o filtrar por un host detectado.

- `sniffer.py`
  - Requiere `scapy`.
  - `sniff_all()`: sniff en la interfaz seleccionada, muestra resumen y detalles básicos (IP/TCP/UDP/DNS).
  - `sniff_by_device()`: aplica filtro BPF `host <IP>` para capturar sólo tráfico del objetivo.
  - `sniff_raw()`: muestra `pkt.show()` para cada paquete.
  - Atención: capturar tráfico puede requerir privilegios y puede violar políticas de uso en redes que no administras.

- `firewall.py`
  - Funciones de alto nivel que ejecutan comandos `iptables` vía shell.
  - Bloqueos soportados:
    - `block_device(ip)`: añade regla DROP para todo tráfico desde la IP origen.
    - `block_global(ip)`: añade regla DROP hacia la IP destino.
    - `block_ip_for_device(src, dst)`: bloquea dst sólo cuando el origen es src.
    - `block_app_ips(ips)`, `block_app_ips_for_device(ips, src_ip)`: aplican reglas para una lista de IPs (útil con `firewall_apps`).
  - Gestión de reglas: listar (`iptables -L FORWARD -n --line-numbers`), eliminar por número, vaciar (`-F`).

- `firewall_apps.py` (registro de apps)
  - Permite registrar aplicaciones con una lista de IPs asociadas.
  - Soporte para bloquear/desbloquear apps globalmente o por dispositivo (usa funciones de `firewall.py`).
  - Persistencia en `firewall_apps.json`.



## Permisos y seguridad

- Muchas funciones requieren privilegios de administrador: ejecutar la herramienta con `sudo` o como root.
- Manipular `iptables` afecta la conectividad; úsalo con cuidado y sólo en entornos de prueba o con autorización.
- El sniffer captura paquetes — evita usarlo en redes que no administras o sin permisos.

## Depuración y problemas comunes

- `nmcli` no disponible: instala NetworkManager o ejecuta las funciones manualmente.
- `scapy` falla: instala con `pip3 install scapy` y prueba `python3 -c "from scapy.all import sniff; print('OK')"`.
- `iftop` no está instalado: instala `iftop` en tu distribución (ej. `sudo apt install iftop`).
- Errores de permisos: reintenta con `sudo`.

---
