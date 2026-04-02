import subprocess

from colors import ORANGE, PINK, RED, RESET

def run(cmd):
    return subprocess.check_output(cmd, shell=True).decode()

def show_devices():
    print(run("nmcli device status"))

def get_interfaces():
    output = run("nmcli device status")
    interfaces = []

    for line in output.split("\n")[1:]:
        if line:
            iface = line.split()[0]
            interfaces.append(iface)

    return interfaces

def disconnect_interface():
    interfaces = get_interfaces()

    print(f"{PINK}Interfaces disponibles: {RESET}")
    for i, iface in enumerate(interfaces):
        print(f"[{i+1}] {iface}")
    print(f"{RED}[0] Cancelar {RESET}")
    choice = int(input(f"{PINK}Selecciona interfaz: {RESET}"))

    # Opción cancelar
    if choice == 0:
        print(f"{ORANGE}[!] Operación cancelada {RESET}")
        return
    
    if choice < 1 or choice > len(interfaces):
        print(f"{RED}[!] Selección inválida{RESET}")
        return

    iface = interfaces[choice - 1]

    subprocess.run(f"nmcli device disconnect {iface}", shell=True)
    print(f"{ORANGE}[+] {iface} desconectada {RESET}")


def get_interfaces_detailed():
    output = run("nmcli device status")
    interfaces = []

    for line in output.split("\n")[1:]:
        if line:
            parts = line.split()
            iface = parts[0]
            dev_type = parts[1]
            state = parts[2]
            connection = " ".join(parts[3:]) if len(parts) > 3 else ""

            interfaces.append({
                "iface": iface,
                "type": dev_type,
                "state": state,
                "connection": connection
            })

    return interfaces