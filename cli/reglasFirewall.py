#!/usr/bin/env python3

import os
import subprocess
import sys
from pathlib import Path

# =========================================
# CONFIG
# =========================================

DNSMASQ_CONF = (
    "/etc/NetworkManager/dnsmasq-shared.d/"
    "ayanami-block.conf"
)

# =========================================
# APPS
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
    },
    
    "adguard": {
        "domains": [
            "adguard.com",
            "dns.adguard.com",
            "adguard-dns.com",
            "dns-unfiltered.adguard.com",
            "dns-unfiltered.adguard-dns.com",
            "dns-family.adguard.com",
            "dns-family.adguard-dns.com",
            "dns-crypto.adguard.com",
        ],
        "block_quic": True
    },
    
    "nextdns": {
        "domains": [
            "nextdns.io",
            "dns.nextdns.io",
            "dns.nextdns.com",
            "dns.nextdns.net",
        ],
        "block_quic": True,
    },
    
    "freedns": {
        "domains": [
            "freedns.afraid.org",
            "freedns.control.com",
            "freedns.com",
            "freedns.net",
        ],
        "block_quic": True,
    },
    
    "mulvanddns": {
        "domains": [
            "mulvanddns.com",
            "dns.mulvanddns.com",
            "adblock.dns.mullvanddns.net",
            "adblock.dns.mulvanddns.com",
        ],
        "block_quic": True,
    },
    
    "familyfilterdns": {
        "domains": [
            "familyfilterdns.com",
            "dns.familyfilterdns.com",
            "adblock.dns.familyfilterdns.com",
            "family-filter-dns.cleanbrowsing.org",
        ],
        "block_quic": True,
    }
}

# =========================================
# HELPERS
# =========================================

def run(cmd):
    print(f"\n[CMD] {cmd}")
    subprocess.run(cmd, shell=True)


def require_root():
    if os.geteuid() != 0:
        print("[!] Ejecuta este script como root")
        sys.exit(1)


# =========================================
# NETWORK
# =========================================

def enable_ip_forward():
    print("[+] Activando IP Forward")

    run("sysctl -w net.ipv4.ip_forward=1")

    try:
        with open("/etc/sysctl.conf", "r") as f:
            content = f.read()

        if "net.ipv4.ip_forward=1" not in content:
            with open("/etc/sysctl.conf", "a") as f:
                f.write("\nnet.ipv4.ip_forward=1\n")

    except Exception as e:
        print(f"[!] Error modificando sysctl.conf: {e}")
        
def force_dns():

    print("[+] Forzando DNS local")

    run(
        "iptables -t nat -C PREROUTING "
        "-p udp --dport 53 "
        "-j DNAT --to-destination 10.42.0.1 "
        "|| "
        "iptables -t nat -A PREROUTING "
        "-p udp --dport 53 "
        "-j DNAT --to-destination 10.42.0.1"
    )

    run(
        "iptables -t nat -C PREROUTING "
        "-p tcp --dport 53 "
        "-j DNAT --to-destination 10.42.0.1 "
        "|| "
        "iptables -t nat -A PREROUTING "
        "-p tcp --dport 53 "
        "-j DNAT --to-destination 10.42.0.1"
    )

def setup_nat():
    print("\n[+] Configuración NAT")
    print("[!] Necesitas la interfaz que tiene internet")
    print("[!] Ejemplo: wlan0, wlp2s0, eth0\n")

    run("ip route")

    interface = input("\nInterfaz internet: ").strip()

    if not interface:
        print("[!] Interfaz inválida")
        return

    print(f"[+] Configurando MASQUERADE en {interface}")

    run(
        f"iptables -t nat -C POSTROUTING -o {interface} "
        f"-j MASQUERADE || "
        f"iptables -t nat -A POSTROUTING -o {interface} "
        f"-j MASQUERADE"
    )
    
    force_dns()


# =========================================
# QUIC BLOCK
# =========================================

def block_quic():
    print("[+] Bloqueando QUIC (UDP 443)")

    run(
        "iptables -C FORWARD -p udp --dport 443 -j DROP || "
        "iptables -I FORWARD 1 -p udp --dport 443 -j DROP"
    )


def unblock_quic():
    print("[+] Eliminando bloqueo QUIC")

    run(
        "iptables -D FORWARD -p udp --dport 443 -j DROP"
    )


# =========================================
# DNS
# =========================================

def ensure_dnsmasq_shared_dir():
    Path(
        "/etc/NetworkManager/dnsmasq-shared.d"
    ).mkdir(parents=True, exist_ok=True)


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

# def get_hotspot_name():
#     result = subprocess.check_output(
#         "nmcli -t -f NAME,TYPE connection show",
#         shell=True,
#         text=True
#     )
#     for line in result.splitlines():
#         if ":wireless" in line.lower():
#             return line.split(":")[0]

#     return None

def restart_networkmanager():
    # hotspot = get_hotspot_name()

    # if not hotspot:
    #     print("[!] No se encontró hotspot")
    #     return

    # print(f"[+] Reiniciando hotspot {hotspot}")
    # run(f"nmcli connection down '{hotspot}'")
    # run(f"nmcli connection up '{hotspot}'")
    print("[+] REINICIAR EL HOSTSPOT MANUALMENTE PARA APLICAR CAMBIOS")


# =========================================
# CONNTRACK
# =========================================

def reset_connections():
    print("[+] Cerrando conexiones activas")
    run("conntrack -F")


# =========================================
# APP BLOCKING
# =========================================

def block_app(app_name):

    app = APPS.get(app_name)

    if not app:
        print("[!] App no encontrada")
        return

    print(f"\n[+] Bloqueando {app_name}")

    write_domains(app["domains"])

    if app.get("block_quic"):
        block_quic()

    restart_networkmanager()

    reset_connections()

    print(f"[✓] {app_name} bloqueado")


def unblock_app(app_name):

    app = APPS.get(app_name)

    if not app:
        print("[!] App no encontrada")
        return

    print(f"\n[+] Desbloqueando {app_name}")

    remove_domains(app["domains"])

    if app.get("block_quic"):
        unblock_quic()

    restart_networkmanager()

    reset_connections()

    print(f"[✓] {app_name} desbloqueado")


# =========================================
# STATUS
# =========================================

def show_status():

    print("\n========== DNS RULES ==========\n")

    if os.path.exists(DNSMASQ_CONF):

        with open(DNSMASQ_CONF, "r") as f:
            print(f.read())

    else:
        print("Sin reglas")

    print("\n========== IPTABLES ==========\n")

    run("iptables -L FORWARD -n --line-numbers")

    print("\n========== NAT ==========\n")

    run("iptables -t nat -L POSTROUTING -n --line-numbers")


# =========================================
# CLEANUP
# =========================================

def flush_all():

    print("[+] Eliminando reglas DNS")

    if os.path.exists(DNSMASQ_CONF):
        os.remove(DNSMASQ_CONF)

    print("[+] Limpiando iptables")

    run("iptables -F FORWARD")

    run("iptables -t nat -F POSTROUTING")

    restart_networkmanager()

    reset_connections()

    print("[✓] Firewall limpiado")


# =========================================
# MENU
# =========================================

def menu():

    while True:

        print("\n========== AYANAMI FIREWALL ==========")

        print("\n--- BLOQUEAR ---")
        print("[1] TikTok")
        print("[2] Clash Royale")
        print("[3] Roblox")
        print("[4] Free Fire")
        print("[5] Facebook")
        print("[6] Instagram")
        print("[7] YouTube")

        print("\n--- DESBLOQUEAR ---")
        print("[8] TikTok")
        print("[9] Clash Royale")
        print("[10] Roblox")
        print("[11] Free Fire")
        print("[12] Facebook")
        print("[13] Instagram")
        print("[14] YouTube")

        print("\n--- SISTEMA ---")
        print("[15] Ver reglas")
        print("[16] Configurar gateway")
        print("[17] Flush conexiones")
        print("[18] Limpiar firewall")

        print("\n[0] Salir")

        op = input("\nOpción: ").strip()

        # =====================
        # BLOQUEAR
        # =====================

        if op == "1":
            block_app("tiktok")

        elif op == "2":
            block_app("clash_royale")
            
        elif op == "3":
            block_app("roblox")
        
        elif op == "4":
            block_app("freefire")

        elif op == "5":
            block_app("facebook")

        elif op == "6":
            block_app("instagram")
            
        elif op == "7":
            block_app("youtube")
            
        elif op == "100":
            block_app("adguard")
            
        elif op == "101":
            block_app("nextdns")
            
        elif op == "102":
            block_app("freedns")
            
        elif op == "103":
            block_app("mulvanddns")
            
        elif op == "104":
            block_app("familyfilterdns")
            

        # =====================
        # DESBLOQUEAR
        # =====================

        elif op == "8":
            unblock_app("tiktok")

        elif op == "9":
            unblock_app("clash_royale")
            
        elif op == "10":
            unblock_app("roblox")
            
        elif op == "11":
            unblock_app("freefire")
            
        elif op == "12":
            unblock_app("facebook")
        
        elif op == "13":
            unblock_app("instagram")
            
        elif op == "14":
            unblock_app("youtube")

        # =====================
        # SISTEMA
        # =====================

        elif op == "15":
            show_status()

        elif op == "16":

            enable_ip_forward()

            setup_nat()

            print("\n[✓] Gateway configurado")

        elif op == "17":
            reset_connections()

        elif op == "18":
            flush_all()

        elif op == "0":
            break

        else:
            print("[!] Opción inválida")


# =========================================
# MAIN
# =========================================

if __name__ == "__main__":

    require_root()

    menu()