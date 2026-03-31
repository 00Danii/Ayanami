import subprocess

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

    print("Interfaces disponibles:")
    for i, iface in enumerate(interfaces):
        print(f"{i+1}. {iface}")

    print(f"{len(interfaces)+1}. Cancelar")

    choice = int(input("Selecciona interfaz: ")) - 1

    # Opción cancelar
    if choice == len(interfaces):
        print("[!] Operación cancelada")
        return
    
    iface = interfaces[choice]

    subprocess.run(f"nmcli device disconnect {iface}", shell=True)
    print(f"[+] {iface} desconectada")


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