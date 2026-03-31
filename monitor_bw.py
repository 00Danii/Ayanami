import subprocess
from network import get_interfaces_detailed
from scanner import get_neighbors

def monitor_bandwidth():
    interfaces = get_interfaces_detailed()

    print("\nInterfaces disponibles:")
    for i, d in enumerate(interfaces):
        print(f"{i+1}. {d['iface']} ({d['type']} - {d['state']} - {d['connection']})")

    try:
        idx = int(input("\nSelecciona interfaz: ")) - 1
        iface = interfaces[idx]["iface"]
    except:
        print("[!] Selección inválida")
        return

    print("\n1. Monitorear toda la red")
    # obtener dispositivos
    devices = get_neighbors()

    for i, d in enumerate(devices):
        print(f"{i+2}. {d['ip']} ({d['mac']})")

    try:
        choice = int(input("\nSelecciona el dispositivo a monitorear: "))
    except:
        print("[!] Entrada inválida")
        return

    # opción 1 toda la red
    if choice == 1:
        print(f"\n[+] Monitoreando toda la red en {iface}...\n")
        subprocess.run(f"iftop -i {iface}", shell=True)

    # dispositivos
    else:
        idx = choice - 2

        if idx < 0 or idx >= len(devices):
            print("[!] Selección inválida")
            return

        target = devices[idx]["ip"]

        print(f"\n[+] Monitoreando {target}...\n")
        subprocess.run(f"iftop -i {iface} -f 'host {target}'", shell=True)