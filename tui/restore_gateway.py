#!/usr/bin/env python3
"""Restaura las reglas permanentes del gateway AYANAMI."""

import ipaddress
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tui"))

from firewall_config import get_saved_gateway
from firewall_ops import apply_whitelist
import network


def run(*args):
    return subprocess.run(
        list(args),
        text=True,
        capture_output=True,
        check=False,
    )


def required(*args):
    result = run(*args)
    if result.returncode != 0:
        raise RuntimeError(
            f"Error: {' '.join(args)}\n{result.stderr.strip()}"
        )
    return result.stdout.strip()


def ensure_rule(check, add):
    """Añade una regla si no existe ya."""
    result = run(*check)
    if result.returncode != 0:
        required(*add)


def main():
    gateway = get_saved_gateway()
    wan = (gateway.get("wan_iface") or "").strip()
    lan = (gateway.get("lan_iface") or "").strip()
    dns_target = (gateway.get("dns_target") or "").strip()

    if not wan:
        raise RuntimeError("No hay interfaz WAN guardada en backup.json")

    if not dns_target and lan:
        dns_target = network.get_iface_ip(lan)

    # Reenvio IPv4
    required("sysctl", "-w", "net.ipv4.ip_forward=1")

    # NAT (MASQUERADE)
    ensure_rule(
        ["iptables", "-t", "nat", "-C", "POSTROUTING", "-o", wan, "-j", "MASQUERADE"],
        ["iptables", "-t", "nat", "-A", "POSTROUTING", "-o", wan, "-j", "MASQUERADE"],
    )

    if lan:
        # Reenvio LAN -> WAN
        ensure_rule(
            ["iptables", "-C", "FORWARD", "-i", lan, "-o", wan, "-j", "ACCEPT"],
            ["iptables", "-A", "FORWARD", "-i", lan, "-o", wan, "-j", "ACCEPT"],
        )
        # Respuestas WAN -> LAN
        ensure_rule(
            ["iptables", "-C", "FORWARD", "-i", wan, "-o", lan, "-m", "state",
             "--state", "ESTABLISHED,RELATED", "-j", "ACCEPT"],
            ["iptables", "-A", "FORWARD", "-i", wan, "-o", lan, "-m", "state",
             "--state", "ESTABLISHED,RELATED", "-j", "ACCEPT"],
        )

    if lan and dns_target:
        # Redireccion DNS (puerto 53)
        for proto in ("udp", "tcp"):
            ensure_rule(
                ["iptables", "-t", "nat", "-C", "PREROUTING", "-i", lan, "-p", proto,
                 "--dport", "53", "-j", "DNAT", "--to-destination", dns_target],
                ["iptables", "-t", "nat", "-A", "PREROUTING", "-i", lan, "-p", proto,
                 "--dport", "53", "-j", "DNAT", "--to-destination", dns_target],
            )

    if lan:
        # Bloqueo DoT (puerto 853) en posicion 1
        for proto in ("udp", "tcp"):
            check = run("iptables", "-C", "FORWARD", "-i", lan, "-p", proto,
                        "--dport", "853", "-j", "DROP")
            if check.returncode != 0:
                required("iptables", "-I", "FORWARD", "1", "-i", lan, "-p", proto,
                         "--dport", "853", "-j", "DROP")

    # Lista blanca
    apply_whitelist()

    print("[OK] Gateway AYANAMI restaurado")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
