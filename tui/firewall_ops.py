import os
import subprocess
from pathlib import Path


DNSMASQ_CONF = "/etc/NetworkManager/dnsmasq-shared.d/ayanami-block.conf"


def _run(cmd: str):
    subprocess.run(cmd, shell=True)


def _ensure_dnsmasq_shared_dir():
    Path("/etc/NetworkManager/dnsmasq-shared.d").mkdir(parents=True, exist_ok=True)


def write_block_domains(domains: list[str]):
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


def remove_block_domains(domains: list[str]):
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


def apply_changes():
    _run("systemctl restart NetworkManager 2>/dev/null")
    _run("conntrack -F 2>/dev/null")


def block_quic():
    _run(
        "iptables -C FORWARD -p udp --dport 443 -j DROP || "
        "iptables -I FORWARD 1 -p udp --dport 443 -j DROP"
    )


def unblock_quic():
    _run("iptables -D FORWARD -p udp --dport 443 -j DROP 2>/dev/null")


def get_dns_block_file() -> str:
    return DNSMASQ_CONF


def reset_apps_state():
    import json
    apps_file = Path(__file__).resolve().parent.parent / "apps_firewall.json"
    if not apps_file.exists():
        return
    data = json.loads(apps_file.read_text())
    changed = False
    for info in data.values():
        if info.get("blocked"):
            info["blocked"] = False
            changed = True
    if changed:
        apps_file.write_text(json.dumps(data, indent=2) + "\n")
