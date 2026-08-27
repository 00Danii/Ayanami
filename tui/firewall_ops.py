import json
import os
import re
import subprocess
from pathlib import Path


DNSMASQ_CONF = "/etc/NetworkManager/dnsmasq-shared.d/ayanami-block.conf"
WHITELIST_FILE = str(Path(__file__).resolve().parent.parent / "whitelist.json")

IP_RE = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")
CIDR_RE = re.compile(r"^(\d{1,3}\.){3}\d{1,3}/\d{1,2}$")
RANGE_RE = re.compile(r"^(\d{1,3}\.){3}\d{1,3}-(\d{1,3}\.){3}\d{1,3}$")


def _run(cmd: str):
    subprocess.run(cmd, shell=True)


def _ensure_dnsmasq_shared_dir():
    Path("/etc/NetworkManager/dnsmasq-shared.d").mkdir(parents=True, exist_ok=True)


def is_valid_ip(ip: str) -> bool:
    if not IP_RE.match(ip):
        return False
    return all(0 <= int(octet) <= 255 for octet in ip.split("."))


def is_valid_cidr(cidr: str) -> bool:
    if not CIDR_RE.match(cidr):
        return False
    ip, mask = cidr.split("/")
    return is_valid_ip(ip) and 0 <= int(mask) <= 32


def is_valid_range(r: str) -> bool:
    if not RANGE_RE.match(r):
        return False
    start, end = r.split("-")
    return is_valid_ip(start) and is_valid_ip(end)


def is_valid_whitelist_entry(entry: str) -> bool:
    return is_valid_ip(entry) or is_valid_cidr(entry) or is_valid_range(entry)


def load_whitelist() -> list[str]:
    if not os.path.exists(WHITELIST_FILE):
        return []
    try:
        with open(WHITELIST_FILE) as f:
            data = json.load(f)
        return data.get("whitelist", [])
    except (json.JSONDecodeError, OSError):
        return []


def save_whitelist(entries: list[str]):
    with open(WHITELIST_FILE, "w") as f:
        json.dump({"whitelist": entries}, f, indent=2)


def add_whitelist_ip(entry: str) -> bool:
    whitelist = load_whitelist()
    if entry in whitelist:
        return False
    whitelist.append(entry)
    save_whitelist(whitelist)
    return True


def remove_whitelist_ip(entry: str) -> bool:
    whitelist = load_whitelist()
    if entry not in whitelist:
        return False
    whitelist.remove(entry)
    save_whitelist(whitelist)
    return True


def apply_whitelist():
    _remove_all_whitelist_rules()
    whitelist = load_whitelist()
    for entry in whitelist:
        if is_valid_range(entry):
            for chain, table_flag in [("FORWARD", ""), ("PREROUTING", "-t nat")]:
                _run(
                    f"iptables {table_flag} -I {chain} 1 -m iprange "
                    f"--src-range {entry} -m comment --comment 'ayanami-wl' -j ACCEPT 2>/dev/null"
                )
                _run(
                    f"iptables {table_flag} -I {chain} 1 -m iprange "
                    f"--dst-range {entry} -m comment --comment 'ayanami-wl' -j ACCEPT 2>/dev/null"
                )
            for proto in ("udp", "tcp"):
                _run(
                    f"iptables -t nat -I PREROUTING 1 -m iprange --src-range {entry} "
                    f"-p {proto} --dport 53 -m comment --comment 'ayanami-wl-dns' "
                    f"-j DNAT --to-destination 8.8.8.8:53 2>/dev/null"
                )
        else:
            for flag in ("-s", "-d"):
                _run(
                    f"iptables -I FORWARD 1 {flag} {entry} "
                    f"-m comment --comment 'ayanami-wl' -j ACCEPT 2>/dev/null"
                )
            for proto in ("udp", "tcp"):
                _run(
                    f"iptables -t nat -I PREROUTING 1 -s {entry} "
                    f"-p {proto} --dport 53 -m comment --comment 'ayanami-wl-dns' "
                    f"-j DNAT --to-destination 8.8.8.8:53 2>/dev/null"
                )
    if whitelist:
        _run("conntrack -F 2>/dev/null")


def _remove_all_whitelist_rules():
    for chain in ("FORWARD", "PREROUTING"):
        table = "-t nat" if chain == "PREROUTING" else ""
        result = subprocess.run(
            f"iptables {table} -S {chain} 2>/dev/null",
            shell=True, capture_output=True, text=True
        )
        for line in result.stdout.strip().split("\n"):
            if "ayanami-wl" in line:
                rule = line.replace("-A", "-D", 1)
                _run(f"iptables {table} {rule} 2>/dev/null")


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
