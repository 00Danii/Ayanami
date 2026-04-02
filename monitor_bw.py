import subprocess
from colors import ORANGE, PINK, RED, RESET, WHITE
from network import get_interfaces_detailed
from scanner import get_neighbors


def monitor_bandwidth():
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

    iface = interfaces[choice - 1]["iface"]

    print(f"\n{PINK}Dispositivos en la red:{RESET}")
    print(f"1. Monitorear toda la red")
    # obtener dispositivos
    devices = get_neighbors()

    for i, d in enumerate(devices):
        print(f"{i+2}. {d['ip']} ({d['mac']})")
    print(f"{RED}[0] Cancelar {RESET}")

    try:
        choice = int(input(f"\n{PINK}Selecciona el dispositivo: {RESET}"))
    except:
        print(f"{RED}[!] Entrada inválida{RESET}")
        return

    if choice == 0:
        print(f"{ORANGE}[!] Operación cancelada{RESET}")
        return

    if choice == 1:
        print(f"\n{ORANGE}[+] Monitoreando toda la red en {iface}...\n {RESET}")
        subprocess.run(f"iftop -i {iface}", shell=True)
        return

    idx = choice - 2
    if idx < 0 or idx >= len(devices):
        print(f"{RED}[!] Selección inválida{RESET}")
        return

    target = devices[idx]["ip"]

    print(f"\n{ORANGE}[+] Monitoreando {target}...\n{RESET}")
    subprocess.run(f"iftop -i {iface} -f 'host {target}'", shell=True)