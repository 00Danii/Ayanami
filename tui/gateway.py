import subprocess
from network import get_interfaces

def run(cmd):
    subprocess.run(cmd, shell=True)


def create_hotspot(iface, ssid, password):
    run(f"nmcli dev wifi hotspot ifname {iface} ssid {ssid} password {password}")
    return show_hotspot_password()


def show_hotspot_password():
    result = subprocess.check_output("nmcli dev wifi show-password", shell=True).decode()
    return result


def create_hotspot_cli():
    from colors import BOLD, CYAN, BLUE, ORANGE, PINK, RED, RESET, WHITE
    interfaces = get_interfaces()

    print(f"{BOLD}{PINK}Interfaces disponibles:{RESET}")
    for i, iface in enumerate(interfaces):
        print(f"[{i+1}] {iface}")

    print(f"{RED}[0] Cancelar{RESET}")

    
    choice = int(input(f"{PINK}Selecciona interfaz WiFi: {RESET}"))


    if choice == 0:
        print(f"{ORANGE}[!] Operación cancelada {RESET}")
        return
    
    if choice < 1 or choice > len(interfaces):
        print(f"{RED}[!] Selección inválida{RESET}")
        return

    iface = interfaces[choice - 1]

    ssid = input("SSID: ")
    password = input("Password: ")

    print(f"\n{ORANGE}[+] Creando hotspot...\n{RESET}")

    create_hotspot(iface, ssid, password)

    print(f"{ORANGE}\n[+] Hotspot creado{RESET}")