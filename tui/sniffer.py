from scapy.all import sniff, IP, TCP, UDP, DNSQR
from network import get_interfaces_detailed
from scanner import get_neighbors
import subprocess


# =========================
# CORE FUNCTIONS (para TUI)
# =========================

def packet_full(pkt):
    result = []
    result.append("==============================")
    result.append(pkt.summary())

    if pkt.haslayer(IP):
        result.append(f"SRC: {pkt[IP].src}")
        result.append(f"DST: {pkt[IP].dst}")

    if pkt.haslayer(TCP):
        result.append(f"TCP {pkt[TCP].sport} → {pkt[TCP].dport}")

    if pkt.haslayer(UDP):
        result.append(f"UDP {pkt[UDP].sport} → {pkt[UDP].dport}")

    if pkt.haslayer(DNSQR):
        result.append(f"DNS: {pkt[DNSQR].qname.decode()}")

    return "\n".join(result)


def get_interfaces():
    return get_interfaces_detailed()


def start_sniff(iface, target=None, mode="all", callback=None):
    if mode == "raw":
        return sniff(iface=iface, prn=lambda pkt: pkt.show(), store=0)
    elif mode == "device" and target:
        return sniff(iface=iface, filter=f"host {target}", prn=callback or packet_full, store=0)
    else:
        return sniff(iface=iface, prn=callback or packet_full, store=0)


# =========================
# CLI MENU FUNCTIONS
# =========================

def select_interface():
    from colors import ORANGE, PINK, RED, RESET
    interfaces = get_interfaces_detailed()

    print(f"\n{PINK}Interfaces disponibles:{RESET}")
    for i, d in enumerate(interfaces):
        print(f"{i+1}.{d['iface']} ({d['type']} - {d['state']} - {d['connection']})")
    print(f"{RED}[0] Cancelar {RESET}")

    try:
        choice = int(input(f"\n{PINK}Selecciona la interfaz: {RESET}"))
    except:
        print(f"{RED}[!] Entrada inválida{RESET}")
        return

    if choice == 0:
        print(f"{ORANGE}[!] Operación cancelada{RESET}")
        return

    if choice < 1 or choice > len(interfaces):
        print(f"{RED}[!] Selección inválida{RESET}")
        return

    return interfaces[choice - 1]["iface"]


def sniff_all():
    from colors import ORANGE
    iface = select_interface()
    if not iface:
        return

    print(f"\n{ORANGE}[+] Sniffing toda la red...\n{RESET}")
    sniff(iface=iface, prn=lambda pkt: print(packet_full(pkt)), store=0)


def sniff_by_device():
    from colors import ORANGE, PINK, RED, RESET
    iface = select_interface()
    if not iface:
        return

    devices = get_neighbors()

    if not devices:
        print(f"{RED}[!] No hay dispositivos{RESET}")
        return

    print(f"\n{PINK}Dispositivos:{RESET}")
    for i, d in enumerate(devices):
        print(f"{i+1}. {d['ip']} ({d['mac']})")
    print(f"{RED}[0] Cancelar{RESET}")

    try:
        choice = int(input(f"\n{PINK}Selecciona dispositivo: {RESET}"))
    except:
        print(f"{RED}[!] Selección inválida{RESET}")
        return

    if choice == 0:
        print(f"{ORANGE}[!] Operación cancelada{RESET}")
        return

    if choice < 1 or choice > len(devices):
        print(f"{RED}[!] Selección inválida{RESET}")
        return

    target = devices[choice - 1]["ip"]

    print(f"\n{ORANGE}[+] Sniffing {target}...\n{RESET}")
    sniff(iface=iface, filter=f"host {target}", prn=lambda pkt: print(packet_full(pkt)), store=0)


def sniff_raw():
    from colors import ORANGE
    iface = select_interface()
    if not iface:
        return

    print(f"\n{ORANGE}[+] Modo RAW (muy detallado)\n{RESET}")
    sniff(iface=iface, prn=lambda pkt: pkt.show(), store=0)


def sniffer_menu():
    from colors import BOLD, ORANGE, PINK, RED, RESET
    while True:
        print(f"\n{BOLD}{ORANGE}=== SNIFFER ==={RESET}")
        print("[1] Ver todo el tráfico")
        print("[2] Ver tráfico por dispositivo")
        print("[3] Modo RAW (detallado)")
        print(f"{RED}[0] Cancelar{RESET}")

        choice = input(f"\n{PINK}Opción: {RESET}")

        if choice == "1":
            sniff_all()
        elif choice == "2":
            sniff_by_device()
        elif choice == "3":
            sniff_raw()
        elif choice == "0":
            break
        else:
            print(f"{RED}[!] Opción inválida{RESET}")