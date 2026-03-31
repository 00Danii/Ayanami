from scapy.all import sniff, IP, TCP, UDP, DNSQR
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


# Selección de interfaz (PRO)
def select_interface():
    interfaces = get_interfaces_detailed()

    print("\nInterfaces:")
    for i, d in enumerate(interfaces):
        print(f"{i+1}. {d['iface']} ({d['type']} - {d['state']} - {d['connection']})")

    try:
        idx = int(input("\nSelecciona interfaz: ")) - 1
        return interfaces[idx]["iface"]
    except:
        print("[!] Selección inválida")
        return None


# Sniffer general
def sniff_all():
    iface = select_interface()
    if not iface:
        return

    print("\n[+] Sniffing toda la red...\n")

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
        print("[!] No hay dispositivos")
        return

    print("\nDispositivos:")
    for i, d in enumerate(devices):
        print(f"{i+1}. {d['ip']} ({d['mac']})")

    try:
        idx = int(input("\nSelecciona: ")) - 1
        target = devices[idx]["ip"]
    except:
        print("[!] Selección inválida")
        return

    print(f"\n[+] Sniffing {target}...\n")

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

    print("\n[+] Modo RAW (muy detallado)\n")

    # threading.Thread(target=key_listener, daemon=True).start()

    sniff(
        iface=iface,
        prn=lambda pkt: pkt.show(),
        store=0
    )


# MENÚ DEL SNIFFER
def sniffer_menu():
    while True:
        print("\n=== SNIFFER ===")
        print("1. Ver todo el tráfico")
        print("2. Ver tráfico por dispositivo")
        print("3. Modo RAW (ultra detallado)")
        print("4. Volver")

        choice = input("\nOpción: ")

        if choice == "1":
            sniff_all()

        elif choice == "2":
            sniff_by_device()

        elif choice == "3":
            sniff_raw()

        elif choice == "4":
            break

        else:
            print("Opción inválida")