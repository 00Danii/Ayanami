#!/usr/bin/env python3
"""
Captura con ndpiReader -R y, cuando nDPI emite una detección configurada,
bloquea el dispositivo por MAC.

IMPORTANTE:
- Por defecto funciona en simulación. Para aplicar reglas se requiere --apply.
- Requiere root (captura + iptables + ARP/neighbor).
- El bloqueo es por MAC en FORWARD; efectivo mientras el dispositivo siga
  en la misma L2 (mismo AP/switch) del gateway.
"""

import argparse
import ipaddress
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import threading
from vpn_supervisor import VPNBlockSupervisor
import time
from datetime import datetime

DEFAULT_VPN_NAMES = ("wireguard", "protonvpn", "openvpn", "nordvpn",
                     "expressvpn", "privateinternetaccess", "tunnelbear")

DETECTION_RE = re.compile(
    r"\[(?P<transport>TCP|UDP)\]\s+"
    r"(?P<ip1>\[[0-9a-fA-F:.]+\]|[0-9.]+):(?P<port1>\d+)\s+"
    r"<-->\s+"
    r"(?P<ip2>\[[0-9a-fA-F:.]+\]|[0-9.]+):(?P<port2>\d+)\s+"
    r"app=(?P<app>[A-Za-z0-9_. -]+?)\s+<",
    re.IGNORECASE,
)


def log(message):
    print(f"[{datetime.now():%y-%m-%d %H:%M:%S}] {message}", flush=True)


def normalize_ip(value):
    return value.strip("[]")


def parse_line(line, vpn_names):
    if "Detected Realtime protocol" not in line:
        return None
    match = DETECTION_RE.search(line)
    if not match:
        return None

    app = match.group("app").strip()
    app_lower = app.lower()
    if not any(name in app_lower for name in vpn_names):
        return None

    ip1 = normalize_ip(match.group("ip1"))
    ip2 = normalize_ip(match.group("ip2"))
    try:
        ipaddress.ip_address(ip1)
        ipaddress.ip_address(ip2)
    except ValueError:
        return None

    return {
        "app": app,
        "transport": match.group("transport").lower(),
        "ip1": ip1,
        "port1": int(match.group("port1")),
        "ip2": ip2,
        "port2": int(match.group("port2")),
    }


def iptables_rule_exists(rule):
    result = subprocess.run(
        ["iptables", "-C", "FORWARD"] + rule,
        text=True, capture_output=True, check=False,
    )
    return result.returncode == 0


def get_subnet(iface):
    try:
        out = subprocess.run(
            ["ip", "-4", "-o", "addr", "show", iface],
            text=True, capture_output=True, check=False,
        )
    except FileNotFoundError:
        return None
    for line in out.stdout.splitlines():
        m = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+/\d+)", line)
        if m:
            try:
                return ipaddress.ip_network(m.group(1), strict=False)
            except ValueError:
                continue
    return None


def conntrack_vpn_active(client_ip, remote_ip, transport, min_remaining=10):
    """Comprueba si hay una conexión reciente del cliente al endpoint VPN.

    Se exige que el timeout restante sea >= min_remaining para evitar
    renovar por entradas conntrack viejas que aún no han expirado.
    """
    proto = "udp" if transport == "udp" else "tcp"
    try:
        with open("/proc/net/nf_conntrack") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 5 or parts[2] != proto:
                    continue
                try:
                    timeout = int(parts[4])
                except ValueError:
                    continue
                if timeout < min_remaining:
                    continue
                if f"src={client_ip}" in line and f"dst={remote_ip}" in line:
                    return True
    except OSError:
        pass
    # Fallback: conntrack CLI (sin info de timeout -> considerar activa)
    try:
        out = subprocess.run(
            ["conntrack", "-L", "-s", client_ip, "-d", remote_ip, "-p", proto],
            text=True, capture_output=True, check=False, timeout=5,
        )
        if out.returncode == 0 and out.stdout.strip():
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return False


def get_mac(ip):
    try:
        out = subprocess.run(["ip", "neigh", "show", ip],
                             text=True, capture_output=True, check=False)
        m = re.search(r"lladdr\s+([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})", out.stdout)
        if m:
            return m.group(1).lower()
    except FileNotFoundError:
        pass
    try:
        with open("/proc/net/arp") as f:
            for line in f.readlines()[1:]:
                parts = line.split()
                if len(parts) >= 4 and parts[0] == ip:
                    mac = parts[3]
                    if re.fullmatch(r"[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5}", mac):
                        return mac.lower()
    except OSError:
        pass
    try:
        subprocess.run(["ping", "-c", "1", "-W", "1", ip],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    except FileNotFoundError:
        pass
    try:
        out = subprocess.run(["ip", "neigh", "show", ip],
                             text=True, capture_output=True, check=False)
        m = re.search(r"lladdr\s+([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})", out.stdout)
        if m:
            return m.group(1).lower()
    except FileNotFoundError:
        pass
    return None


def ensure_chain(name):
    subprocess.run(["iptables", "-N", name], text=True, capture_output=True, check=False)


def install_watcher(mac, remote_ip, transport, remote_port, apply):
    """Regla de conteo no bloqueante para el flujo VPN (salta a AYANAMI_CNT)."""
    proto = transport  # "tcp"/"udp" ya en minúsculas
    rule = [
        "-m", "mac", "--mac-source", mac,
        "-d", remote_ip,
        "-p", proto,
        "--dport", str(remote_port),
        "-j", "AYANAMI_CNT",
    ]
    cmd = ["iptables", "-I", "FORWARD", "1"] + rule
    if not apply:
        log("[SIMULACIÓN] " + shlex.join(cmd) + "   # watcher VPN")
        return False, [rule]
    if iptables_rule_exists(rule):
        return False, [rule]
    result = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        log(f"ERROR al instalar watcher: {(result.stderr or '').strip()}")
        return False, []
    log("Watcher de conteo instalado para flujo VPN.")
    return True, [rule]


def get_watcher_packet_count(mac, remote_ip, transport, remote_port, watcher_rule=None):
    """Devuelve los paquetes contabilizados por el watcher VPN."""

    if watcher_rule is None:
        return 0

    try:
        result = subprocess.run(
            ["iptables", "-L", "FORWARD", "-v", "-n", "-x"],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return 0

    if result.returncode != 0:
        return 0

    target = "AYANAMI_CNT" if "-j" in watcher_rule and (
        watcher_rule[watcher_rule.index("-j") + 1] == "AYANAMI_CNT"
    ) else "REJECT"

    for line in result.stdout.splitlines():
        parts = line.split()

        if len(parts) < 10:
            continue

        if parts[2] != target:
            continue

        if mac.lower() not in line.lower():
            continue

        if parts[8] != remote_ip:
            continue

        protocol_number = {
            "tcp": "6",
            "udp": "17",
        }.get(transport.lower(), transport.lower())

        if parts[3].lower() not in (transport.lower(), protocol_number):
            continue

        if f"dpt:{remote_port}" not in line:
            continue

        try:
            return int(parts[0])
        except ValueError:
            return 0

    return 0


def install_mac_rule(mac, remote_ip, transport, remote_port, apply, flow_only):
    """Instala regla iptables basada solo en MAC. Devuelve (instalada_ahora, [regla])."""
    if flow_only:
        rule = [
            "-m", "mac", "--mac-source", mac,
            "-d", remote_ip,
            "-p", transport,
            "--dport", str(remote_port),
            "-j", "REJECT",
        ]
        label = f"MAC {mac} -> {remote_ip}:{remote_port}/{transport}"
    else:
        rule = [
            "-m", "mac", "--mac-source", mac,
            "-j", "DROP",
        ]
        label = f"dispositivo completo MAC {mac}"

    cmd = ["iptables", "-I", "FORWARD", "1"] + rule
    if not apply:
        log("[SIMULACIÓN] " + shlex.join(cmd) + f"   # {label}")
        return False, [rule]
    if iptables_rule_exists(rule):
        log(f"Regla ya existe, no se duplica: {label}")
        return False, [rule]
    result = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        log(f"ERROR al instalar regla ({label}): {(result.stderr or '').strip()}")
        return False, []
    log(f"Regla instalada ({label}) en posición 1 de FORWARD.")
    return True, [rule]


def create_block_timer(
    rules,
    watcher_rule,
    dedup_key,
    mac,
    label,
    duration,
    client_ip,
    remote_ip,
    remote_port,
    transport,
    flow_only,
    active_blocks,
):
    last = [
        get_watcher_packet_count(
            mac,
            remote_ip,
            transport,
            remote_port,
            watcher_rule=watcher_rule,
        )
    ]

    def renew_or_unblock():
        current = get_watcher_packet_count(
            mac,
            remote_ip,
            transport,
            remote_port,
            watcher_rule=watcher_rule,
        )

        log(
            f"[DEBUG TIMER] MAC={mac} | "
            f"Anterior={last[0]} | Actual={current}"
        )

        if current > last[0]:
            last[0] = current

            log(
                f"Tráfico VPN aún presente para MAC {mac} "
                f"({current} pkts); renovando bloqueo {duration}s."
            )

            new_timer = threading.Timer(
                duration,
                renew_or_unblock,
            )
            new_timer.daemon = True

            active_blocks[dedup_key] = (
                new_timer,
                rules,
                watcher_rule,
                client_ip,
                remote_ip,
                transport,
                flow_only,
                last,
            )

            new_timer.start()
            return

        for rule in rules:
            subprocess.run(
                ["iptables", "-D", "FORWARD"] + rule,
                text=True,
                capture_output=True,
                check=False,
            )

        if watcher_rule is not None:
            subprocess.run(
                ["iptables", "-D", "FORWARD"] + watcher_rule,
                text=True,
                capture_output=True,
                check=False,
            )

        active_blocks.pop(dedup_key, None)

        log(
            f"Desbloqueo automático: sin tráfico VPN "
            f"para MAC {mac} ({label})"
        )

    timer = threading.Timer(duration, renew_or_unblock)
    timer.daemon = True

    active_blocks[dedup_key] = (
        timer,
        rules,
        watcher_rule,
        client_ip,
        remote_ip,
        transport,
        flow_only,
        last,
    )

    timer.start()

    log(
        f"Bloqueo temporal programado: "
        f"{duration}s para MAC {mac}."
    )



def _set_process_name():
    try:
        import ctypes

        libc = ctypes.CDLL("libc.so.6")
        # PR_SET_NAME = 15 (máximo 16 bytes incluyendo el \0 final).
        libc.prctl(15, b"ayanami-vpn", 0, 0, 0)
    except Exception:
        pass


def main():
    _set_process_name()
    parser = argparse.ArgumentParser(
        description="Detecta VPN con nDPI Reader y bloquea el dispositivo por MAC."
    )
    parser.add_argument("--interface", required=True,
                        help="Interfaz donde se capturará el tráfico.")
    parser.add_argument("--lan-iface", required=True,
                        help="Interfaz LAN por la que entran los paquetes del cliente.")
    parser.add_argument("--subnet", default=None,
                        help="Subred LAN a vigilar, ej. 10.0.0.1/21. Si se omite, se auto-detecta de --lan-iface.")
    parser.add_argument("--ndpi-reader", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ndpiReader"),
                        help="Ruta al ejecutable ndpiReader compilado (por defecto en la raíz del proyecto).")
    parser.add_argument("--vpn-name", action="append", default=[],
                        help="Nombre de app que se tratará como VPN; se puede repetir.")
    parser.add_argument("--block-device", action="store_true",
                        help="Bloquea TODO el tráfico del dispositivo (por MAC), no solo el flujo VPN. Recomendado para DHCP reciclado.")
    parser.add_argument("--block-duration", type=int, default=60,
                        help="Segundos que dura cada bloqueo antes de desbloquear automáticamente (0 = permanente). Por defecto 60.")
    parser.add_argument("--apply", action="store_true",
                        help="Aplica realmente las reglas. Sin esta opción solo muestra lo que haría.")
    args = parser.parse_args()

    if os.geteuid() != 0:
        sys.exit("Ejecuta con sudo: se requieren privilegios para capturar tráfico.")
    if not shutil.which("iptables"):
        sys.exit("No se encontró iptables.")

    reader = os.path.abspath(args.ndpi_reader)
    if not os.path.isfile(reader) or not os.access(reader, os.X_OK):
        sys.exit(f"ndpiReader no existe o no es ejecutable: {reader}")

    vpn_names = {name.lower() for name in DEFAULT_VPN_NAMES}
    vpn_names.update(name.lower() for name in args.vpn_name)

    subnet = None
    if args.subnet:
        try:
            subnet = ipaddress.ip_network(args.subnet, strict=False)
        except ValueError:
            sys.exit("--subnet no es una subred válida.")
    else:
        subnet = get_subnet(args.lan_iface)
        if subnet is None:
            sys.exit("No se pudo auto-detectar la subred de " + args.lan_iface +
                     ". Pásala con --subnet, ej. 10.42.0.0/24")

    server_ips = set()
    try:
        out = subprocess.run(["ip", "-4", "-o", "addr", "show", args.lan_iface],
                             text=True, capture_output=True, check=False)
        for m in re.finditer(r"inet\s+(\d+\.\d+\.\d+\.\d+)", out.stdout):
            server_ips.add(m.group(1))
    except Exception:
        pass

    command = [reader, "-i", args.interface, "-R"]
    if shutil.which("stdbuf"):
        command = ["stdbuf", "-oL", "-eL"] + command

    log("Comando de captura: " + shlex.join(command))
    log(f"Interfaz de captura: {args.interface}; interfaz LAN de bloqueo: {args.lan_iface}")
    log(f"Subred vigilada: {subnet}")
    log(f"Modo de bloqueo: {'DISPOSITIVO completo por MAC' if args.block_device else 'flujo VPN por MAC'}")
    log(f"Duración de bloqueo: {'permanente' if args.block_duration == 0 else str(args.block_duration) + 's (auto-desbloqueo)'}")
    log(f"Aplicar: {'SÍ' if args.apply else 'NO (simulación)'}")
    log("Detecciones habilitadas: " + ", ".join(sorted(vpn_names)))

    recent = {}
    active_blocks = {}  # Conservado por compatibilidad; ya no se usa en modo temporal.
    supervisor = None
    if args.apply and args.block_duration > 0:
        supervisor = VPNBlockSupervisor(
            duration=args.block_duration, log=log, interval=1.0,
            block_device=args.block_device,
        )
        supervisor.start()
    process = None

    try:
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        assert process.stdout is not None

        for raw_line in process.stdout:
            line = raw_line.rstrip()
            det = parse_line(line, vpn_names)
            if det is None:
                if any(w in line.lower() for w in ("permission denied", "error", "failed")):
                    log("ndpiReader: " + line)
                continue

            # Determinar cuál de las dos IPs es el cliente (la que está en la subred)
            client_ip = None
            client_port = None
            remote_ip = None
            remote_port = None
            for ip, port, other, other_port in (
                (det["ip1"], det["port1"], det["ip2"], det["port2"]),
                (det["ip2"], det["port2"], det["ip1"], det["port1"]),
            ):
                try:
                    if ipaddress.ip_address(ip) in subnet and ip not in server_ips:
                        client_ip = ip
                        client_port = port
                        remote_ip = other
                        remote_port = other_port
                        break
                except ValueError:
                    continue

            if client_ip is None:
                continue

            mac = get_mac(client_ip)
            if not mac:
                log(f"VPN detectada ({det['app']}) en {client_ip} pero no se pudo obtener la MAC; no se puede bloquear por MAC. (IP: {client_ip})")
                continue
            log(f"[DEBUG] Flujo detectado: {det['app']}")
            log(f"[DEBUG] Cliente: {client_ip}")
            log(f"[DEBUG] MAC obtenida: {mac}")
            log(f"[DEBUG] Destino VPN: {remote_ip}:{remote_port}/{det['transport']}")
            # Deduplicación con TTL: evita spam si ndpiReader repite la misma
            # detección, pero permite re-detectar tras una reconexión (nuevo
            # flujo / nuevo puerto de cliente) pasados unos segundos.
            DEDUP_TTL = 5
            if supervisor is not None:
                # Una clave por endpoint VPN.
                # El supervisor mantiene un único bloqueo por MAC.
                dedup_key = (
                    "vpn",
                    mac,
                    remote_ip,
                    remote_port,
                    det["transport"],
                )
            elif args.block_device:
                dedup_key = ("dev", mac)
            else:
                dedup_key = (
                    "flow",
                    mac,
                    client_port,
                    remote_ip,
                    remote_port,
                    det["transport"],
                )
            now = time.time()
            last = recent.get(dedup_key, 0)
            if now - last < DEDUP_TTL:
                continue
            recent[dedup_key] = now

            log(
                f"VPN detectada: app={det['app']} | "
                f"{det['ip1']}:{det['port1']} <-> {det['ip2']}:{det['port2']} | "
                f"cliente_ip={client_ip} MAC={mac}"
            )
            flow_only = not args.block_device
            if supervisor is not None:
                try:
                    supervisor.register(
                        mac=mac, client_ip=client_ip, remote_ip=remote_ip,
                        remote_port=remote_port, transport=det["transport"],
                    )
                except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
                    log(f"[VPN] Error al instalar bloqueo para {mac}: {exc}")
            else:
                # Simulación (--apply ausente) o bloqueo permanente (duration=0).
                installed, rules = install_mac_rule(
                    mac=mac, remote_ip=remote_ip, transport=det["transport"],
                    remote_port=remote_port, apply=args.apply, flow_only=flow_only,
                )
                if args.block_device:
                    if args.apply:
                        ensure_chain("AYANAMI_CNT")
                    install_watcher(
                        mac=mac, remote_ip=remote_ip, transport=det["transport"],
                        remote_port=remote_port, apply=args.apply,
                    )

        code = process.wait()
        if code:
            log(f"ndpiReader terminó con código {code}.")
    except KeyboardInterrupt:
        log("Interrupción solicitada; deteniendo captura.")
    finally:
        if process and process.poll() is None:
            process.send_signal(signal.SIGINT)
            try:
                process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait()
        # Detener el supervisor antes de retirar las reglas que administra.
        if supervisor is not None:
            supervisor.stop()
            log("Reglas de bloqueo temporal retiradas al salir.")


if __name__ == "__main__":
    main()
