#!/usr/bin/env python3

import os
import sys

from colors import BLUE, BOLD, CYAN, ORANGE, PINK, PURPLE, RED, RESET, WHITE
from scanner import get_neighbors

# =========================================
# APPS PREDEFINIDAS - From reglasFirewall
# =========================================

APPS = {
    "tiktok": {
        "domains": [
            "tiktok.com",
            "www.tiktok.com",
            "vm.tiktok.com",
            "api.tiktokv.com",
            "tiktokcdn.com",
            "tiktokv.com",
            "byteoversea.com",
            "ibytedtos.com",
            "musical.ly",
        ],
        "block_quic": True
    },

    "clash_royale": {
        "domains": [
            "supercell.com",
            "clashroyale.com",
            "game.clashroyaleapp.com",
        ],
        "block_quic": False
    },

    "roblox": {
        "domains": [
            "roblox.com",
            "www.roblox.com",
            "rbxcdn.com",
            "rbx.com",
            "robloxlabs.com",
        ],
        "block_quic": True
    },

    "freefire": {
        "domains": [
            "garena.com",
            "freefiremobile.com",
            "ff.garena.com",
            "garena.live",
        ],
        "block_quic": True
    },

    "facebook": {
        "domains": [
            "facebook.com",
            "fb.com",
            "fbcdn.net",
            "fbsbx.com",
            "messenger.com",
            "m.me",
            "meta.com",
        ],
        "block_quic": True
    },

    "instagram": {
        "domains": [
            "instagram.com",
            "cdninstagram.com",
            "ig.me",
            "instagram.fdel1-1.fna.fbcdn.net",
            "fbcdn.net",
            "cdn.fbsbx.com",
        ],
        "block_quic": True
    },

    "youtube": {
        "domains": [
            "youtube.com",
            "www.youtube.com",
            "m.youtube.com",
            "youtu.be",
            "youtubei.googleapis.com",
            "ytimg.com",
            "googlevideo.com",
            "youtube.googleapis.com",
            "yt3.ggpht.com",
            "youtube.com/shorts"
        ],
        "block_quic": True
    }
}

# =========================================
# DATA FILE
# =========================================

DATA_FILE = os.path.join(os.path.dirname(__file__), "firewall_apps_state.json")

def load_data():
    if not os.path.exists(DATA_FILE):
        return {
            "global_blocked": [],
            "device_blocked": {}
        }
    try:
        import json
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"global_blocked": [], "device_blocked": {}}

def save_data(data):
    import json
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# =========================================
# HELPERS - From reglasFirewall
# =========================================

def run_quiet(cmd):
    import subprocess
    subprocess.run(cmd, shell=True)

def require_root():
    if os.geteuid() != 0:
        print("[!] Ejecuta este script como root")
        sys.exit(1)

# =========================================
# DNS BLOCKING - From reglasFirewall
# =========================================

DNSMASQ_CONF = (
    "/etc/NetworkManager/dnsmasq-shared.d/"
    "ayanami-block.conf"
)

def ensure_dnsmasq_shared_dir():
    from pathlib import Path
    Path("/etc/NetworkManager/dnsmasq-shared.d").mkdir(parents=True, exist_ok=True)

def write_domains(domains):
    ensure_dnsmasq_shared_dir()
    existing = ""
    if os.path.exists(DNSMASQ_CONF):
        with open(DNSMASQ_CONF, "r") as f:
            existing = f.read()
    with open(DNSMASQ_CONF, "a") as f:
        for domain in domains:
            line = f"address=/{domain}/0.0.0.0\n"
            if line not in existing:
                f.write(line)
    print("[+] Dominios agregados")

def remove_domains(domains):
    if not os.path.exists(DNSMASQ_CONF):
        return
    with open(DNSMASQ_CONF, "r") as f:
        lines = f.readlines()
    filtered = []
    for line in lines:
        keep = True
        for domain in domains:
            if f"/{domain}/" in line:
                keep = False
                break
        if keep:
            filtered.append(line)
    with open(DNSMASQ_CONF, "w") as f:
        f.writelines(filtered)
    print("[+] Dominios eliminados")

def restart_networkmanager():
    print("[+] REINICIAR EL HOTSPOT MANUALMENTE PARA APLICAR CAMBIOS")

def reset_connections():
    print("[+] Cerrando conexiones activas")
    run_quiet("conntrack -F")

# =========================================
# QUIC BLOCK - From reglasFirewall
# =========================================

def block_quic():
    print("[+] Bloqueando QUIC (UDP 443)")
    run_quiet(
        "iptables -C FORWARD -p udp --dport 443 -j DROP || "
        "iptables -I FORWARD 1 -p udp --dport 443 -j DROP"
    )

def unblock_quic():
    print("[+] Eliminando bloqueo QUIC")
    run_quiet(
        "iptables -D FORWARD -p udp --dport 443 -j DROP"
    )

# =========================================
# IP BLOCKING - From firewall.py
# =========================================

def block_app_ips_for_device(ips, src_ip):
    if not ips:
        return
    for ip in ips:
        print(f"{ORANGE}[+] Bloqueando {ip} para {src_ip}{RESET}")
        run_quiet(f"iptables -A FORWARD -s {src_ip} -d {ip} -j DROP")

def unblock_app_ips_for_device(ips, src_ip):
    if not ips:
        return
    for ip in ips:
        print(f"{ORANGE}[+] Eliminando bloqueo {ip} para {src_ip}{RESET}")
        run_quiet(f"iptables -D FORWARD -s {src_ip} -d {ip} -j DROP")

# =========================================
# APP BLOCKING
# =========================================

def block_app_global(app_name, data):
    app = APPS.get(app_name)
    if not app:
        print(f"[!] App no encontrada")
        return

    print(f"\n[+] Bloqueando {app_name} (global)")

    write_domains(app["domains"])

    if app.get("block_quic"):
        block_quic()

    restart_networkmanager()
    reset_connections()

    if app_name not in data["global_blocked"]:
        data["global_blocked"].append(app_name)
    save_data(data)

    print(f"[✓] {app_name} bloqueado globalmente")


def unblock_app_global(app_name, data):
    app = APPS.get(app_name)
    if not app:
        print(f"[!] App no encontrada")
        return

    print(f"\n[+] Desbloqueando {app_name} (global)")

    remove_domains(app["domains"])

    if app.get("block_quic"):
        unblock_quic()

    restart_networkmanager()
    reset_connections()

    if app_name in data["global_blocked"]:
        data["global_blocked"].remove(app_name)
    save_data(data)

    print(f"[✓] {app_name} desbloqueado globalmente")


def block_app_device(app_name, device_ip, data):
    app = APPS.get(app_name)
    if not app:
        print(f"[!] App no encontrada")
        return

    print(f"\n[+] Bloqueando {app_name} para {device_ip}")

    import firewall
    domains = [f"address=/{d}/127.0.0.1" for d in app["domains"]]
    firewall.write_domains_for_device(app["domains"], device_ip)

    block_app_ips_for_device(app.get("ips", []), device_ip)

    if app_name not in data["device_blocked"]:
        data["device_blocked"][app_name] = []
    if device_ip not in data["device_blocked"][app_name]:
        data["device_blocked"][app_name].append(device_ip)
    save_data(data)

    print(f"[✓] {app_name} bloqueado para {device_ip}")


def unblock_app_device(app_name, device_ip, data):
    app = APPS.get(app_name)
    if not app:
        print(f"[!] App no encontrada")
        return

    print(f"\n[+] Desbloqueando {app_name} para {device_ip}")

    import firewall
    firewall.remove_domains_for_device(app["domains"], device_ip)

    unblock_app_ips_for_device(app.get("ips", []), device_ip)

    if app_name in data["device_blocked"]:
        if device_ip in data["device_blocked"][app_name]:
            data["device_blocked"][app_name].remove(device_ip)
    save_data(data)

    print(f"[✓] {app_name} desbloqueado para {device_ip}")


def show_status(data):
    print("\n========== APP BLOCKING STATUS ==========\n")
    print(f"{CYAN}Bloqueos globales:{RESET}")
    if data["global_blocked"]:
        for app in data["global_blocked"]:
            print(f"  - {app}")
    else:
        print("  Ninguno")

    print(f"\n{BLUE}Bloqueos por dispositivo:{RESET}")
    if data["device_blocked"]:
        for app, devices in data["device_blocked"].items():
            if devices:
                print(f"  {app}: {', '.join(devices)}")
    else:
        print("  Ninguno")

    print("\n========== DNS RULES ==========\n")
    if os.path.exists(DNSMASQ_CONF):
        with open(DNSMASQ_CONF, "r") as f:
            print(f.read())
    else:
        print("Sin reglas DNS")

    print("\n========== IPTABLES ==========\n")
    run_quiet("iptables -L FORWARD -n --line-numbers")


# =========================================
# MENU
# =========================================

def main_menu():
    while True:
        data = load_data()
        print(f"\n{BOLD}{PINK}=== FIREWALL APPS (DNS Blocking) ==={RESET}")

        print(f"{PURPLE}--- BLOQUEAR ---{RESET}")
        print(f"{PURPLE}[1]{WHITE} TikTok (global){RESET}")
        print(f"{PURPLE}[2]{WHITE} Clash Royale (global){RESET}")
        print(f"{PURPLE}[3]{WHITE} Roblox (global){RESET}")
        print(f"{PURPLE}[4]{WHITE} Free Fire (global){RESET}")
        print(f"{PURPLE}[5]{WHITE} Facebook (global){RESET}")
        print(f"{PURPLE}[6]{WHITE} Instagram (global){RESET}")
        print(f"{PURPLE}[7]{WHITE} YouTube (global){RESET}")

        print(f"{ORANGE}--- BLOQUEAR POR DISPOSITIVO ---{RESET}")
        print(f"{ORANGE}[8]{WHITE} TikTok (dispositivo){RESET}")
        print(f"{ORANGE}[9]{WHITE} Clash Royale (dispositivo){RESET}")
        print(f"{ORANGE}[10]{WHITE} Roblox (dispositivo){RESET}")
        print(f"{ORANGE}[11]{WHITE} Free Fire (dispositivo){RESET}")
        print(f"{ORANGE}[12]{WHITE} Facebook (dispositivo){RESET}")
        print(f"{ORANGE}[13]{WHITE} Instagram (dispositivo){RESET}")
        print(f"{ORANGE}[14]{WHITE} YouTube (dispositivo){RESET}")

        print(f"{CYAN}--- DESBLOQUEAR ---{RESET}")
        print(f"{CYAN}[15]{WHITE} Desbloquear app (global){RESET}")
        print(f"{CYAN}[16]{WHITE} Desbloquear app (dispositivo){RESET}")

        print(f"{BLUE}--- SISTEMA ---{RESET}")
        print(f"{BLUE}[17]{WHITE} Ver estado{RESET}")
        print(f"{RED}[0] Salir{RESET}")

        choice = input(f"\n{PINK}Opción: {RESET}")

        app_map = {
            "1": "tiktok", "2": "clash_royale", "3": "roblox", "4": "freefire",
            "5": "facebook", "6": "instagram", "7": "youtube",
            "8": "tiktok", "9": "clash_royale", "10": "roblox", "11": "freefire",
            "12": "facebook", "13": "instagram", "14": "youtube"
        }

        if choice in app_map:
            app_name = app_map[choice]
            is_device = int(choice) >= 8 and int(choice) <= 14

            if is_device:
                devices = get_neighbors()
                if not devices:
                    print(f"{RED}[!] No hay dispositivos detectados{RESET}")
                    continue
                print(f"\n{PINK}Dispositivos:{RESET}")
                for i, d in enumerate(devices):
                    print(f"{BLUE}[{i+1}] {WHITE}{d['ip']} ({d['mac']}){RESET}")
                print(f"{RED}[0] Cancelar{RESET}")
                try:
                    sel = input(f"\n{PINK}Selecciona dispositivo: {RESET}")
                    if sel.strip() == "0":
                        continue
                    idx = int(sel) - 1
                    if idx < 0 or idx >= len(devices):
                        print(f"{RED}[!] Selección inválida{RESET}")
                        continue
                    device_ip = devices[idx]["ip"]
                    require_root()
                    block_app_device(app_name, device_ip, data)
                except Exception as e:
                    print(f"{RED}[!] Error: {e}{RESET}")
            else:
                require_root()
                block_app_global(app_name, data)
            continue

        if choice == "15":
            print(f"\n{PINK}Desbloquear app (global){RESET}")
            for i, (name, info) in enumerate(APPS.items(), start=1):
                status = "(BLOQUEADA)" if name in data["global_blocked"] else ""
                print(f"{BLUE}[{i}] {WHITE}{name} {status}{RESET}")
            print(f"{RED}[0] Cancelar{RESET}")
            try:
                sel = input(f"\n{PINK}Selecciona app: {RESET}")
                if sel.strip() == "0":
                    continue
                idx = int(sel) - 1
                app_names = list(APPS.keys())
                if 0 <= idx < len(app_names):
                    app_name = app_names[idx]
                    require_root()
                    unblock_app_global(app_name, data)
            except Exception as e:
                print(f"{RED}[!] Error: {e}{RESET}")
            continue

        if choice == "16":
            print(f"\n{PINK}Desbloquear app (dispositivo){RESET}")
            blocked_apps = [a for a in data["device_blocked"] if data["device_blocked"][a]]
            if not blocked_apps:
                print(f"{RED}[!] No hay bloqueos por dispositivo{RESET}")
                continue
            for i, name in enumerate(blocked_apps, start=1):
                print(f"{BLUE}[{i}] {WHITE}{name}{RESET}")
            print(f"{RED}[0] Cancelar{RESET}")
            try:
                sel = input(f"\n{PINK}Selecciona app: {RESET}")
                if sel.strip() == "0":
                    continue
                idx = int(sel) - 1
                if 0 <= idx < len(blocked_apps):
                    app_name = blocked_apps[idx]
                    devices = data["device_blocked"][app_name]
                    print(f"\n{PINK}Dispositivos bloqueados:{RESET}")
                    for i, d in enumerate(devices, start=1):
                        print(f"{BLUE}[{i}] {WHITE}{d}{RESET}")
                    print(f"{RED}[0] Cancelar{RESET}")
                    sel2 = input(f"\n{PINK}Selecciona dispositivo: {RESET}")
                    if sel2.strip() == "0":
                        continue
                    idx2 = int(sel2) - 1
                    if 0 <= idx2 < len(devices):
                        device_ip = devices[idx2]
                        require_root()
                        unblock_app_device(app_name, device_ip, data)
            except Exception as e:
                print(f"{RED}[!] Error: {e}{RESET}")
            continue

        if choice == "17":
            show_status(data)
            continue

        if choice == "0":
            break

        print("Opción inválida.")


if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print(f"\n{RED}Interrumpido. Saliendo.{RESET}")
        sys.exit(0)