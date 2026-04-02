from scapy.all import sniff, IP, TCP, UDP, DNSQR
from colors import BOLD, CYAN, BLUE, ORANGE, PINK, RED, RESET, WHITE
from network import get_interfaces_detailed
from scanner import get_neighbors
import threading

# paused = False

# Listener de teclado
# def key_listener():
#     global paused
#     while True:
#         key = input()
#         if key.lower() == "p":
#             paused = not paused
#             print("\n[+] Pausa" if paused else "\n[+] Reanudado")

# Mostrar paquetes balanceado
def packet_full(pkt):
    #global paused

    # if paused:
    #     return

    print("\n==============================")
    print(pkt.summary())

    if pkt.haslayer(IP):
        print(f"SRC: {pkt[IP].src}")
        print(f"DST: {pkt[IP].dst}")

    if pkt.haslayer(TCP):
        print(f"TCP {pkt[TCP].sport} → {pkt[TCP].dport}")

    if pkt.haslayer(UDP):
        print(f"UDP {pkt[UDP].sport} → {pkt[UDP].dport}")

    if pkt.haslayer(DNSQR):
        print(f"DNS: {pkt[DNSQR].qname.decode()}")


# Selección de interfaz 
def select_interface():
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


# Sniffer general
def sniff_all():
    iface = select_interface()
    if not iface:
        return

    print(f"\n{ORANGE}[+] Sniffing toda la red...\n{RESET}")

    # threading.Thread(target=key_listener, daemon=True).start()

    sniff(
        iface=iface,
        prn=packet_full,
        store=0
    )


# Sniffer por dispositivo
def sniff_by_device():
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

    # threading.Thread(target=key_listener, daemon=True).start() 

    sniff(
        iface=iface,
        filter=f"host {target}",
        prn=packet_full,
        store=0
    )


# MODO RAW (tipo Wireshark CLI)
def sniff_raw():
    iface = select_interface()
    if not iface:
        return

    print(f"\n{ORANGE}[+] Modo RAW (muy detallado)\n{RESET}")

    # threading.Thread(target=key_listener, daemon=True).start()

    sniff(
        iface=iface,
        prn=lambda pkt: pkt.show(),
        store=0
    )


# MENÚ DEL SNIFFER
def sniffer_menu():
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