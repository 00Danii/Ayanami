import os
import subprocess
from pathlib import Path


DNSMASQ_CONF = "/etc/NetworkManager/dnsmasq-shared.d/ayanami-block.conf"


def _run(cmd: str):
    subprocess.run(cmd, shell=True)


def _ensure_dnsmasq_shared_dir():
    Path("/etc/NetworkManager/dnsmasq-shared.d").mkdir(parents=True, exist_ok=True)


def _write_domains(domains: list[str]):
    _ensure_dnsmasq_shared_dir()
    existing = ""
    if os.path.exists(DNSMASQ_CONF):
        with open(DNSMASQ_CONF) as f:
            existing = f.read()
    with open(DNSMASQ_CONF, "a") as f:
        for domain in domains:
            line = f"address=/{domain}/0.0.0.0\n"
            if line not in existing:
                f.write(line)


def _remove_domains(domains: list[str]):
    if not os.path.exists(DNSMASQ_CONF):
        return
    with open(DNSMASQ_CONF) as f:
        lines = f.readlines()
    filtered = [
        line
        for line in lines
        if not any(f"/{d}/" in line for d in domains)
    ]
    with open(DNSMASQ_CONF, "w") as f:
        f.writelines(filtered)


def _block_quic():
    _run(
        "iptables -C FORWARD -p udp --dport 443 -j DROP || "
        "iptables -I FORWARD 1 -p udp --dport 443 -j DROP"
    )


def _unblock_quic():
    _run("iptables -D FORWARD -p udp --dport 443 -j DROP 2>/dev/null")


def _restart_dnsmasq():
    _run("systemctl restart NetworkManager 2>/dev/null || nmcli connection reload 2>/dev/null")


def reset_connections():
    _run("conntrack -F 2>/dev/null")


def get_dns_block_file() -> str:
    return DNSMASQ_CONF


def get_dns_block_file() -> str:
    return DNSMASQ_CONF


def block_app(name: str, domains: list[str], block_quic: bool = False):
    _write_domains(domains)
    if block_quic:
        _block_quic()
    _restart_dnsmasq()
    reset_connections()


def unblock_app(name: str, domains: list[str], block_quic: bool = False):
    _remove_domains(domains)
    if block_quic:
        _unblock_quic()
    _restart_dnsmasq()
    reset_connections()
