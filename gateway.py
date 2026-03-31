import subprocess
from network import get_interfaces

def run(cmd):
    subprocess.run(cmd, shell=True)

def create_hotspot():
    interfaces = get_interfaces()

    print("Interfaces disponibles:")
    for i, iface in enumerate(interfaces):
        print(f"{i+1}. {iface}")

    print(f"{len(interfaces)+1}. Cancelar")

    choice = int(input("Selecciona interfaz WiFi: ")) - 1

    # Opción cancelar
    if choice == len(interfaces):
        print("[!] Operación cancelada")
        return
    
    iface = interfaces[choice]

    ssid = input("SSID: ")
    password = input("Password (mín 8): ")

    print("\n[+] Creando hotspot...\n")

    run(f"nmcli dev wifi hotspot ifname {iface} ssid {ssid} password {password}")

    print("\n[+] Hotspot creado")
    show_hotspot_password()

def show_hotspot_password():
    print("[+] Mostrando contraseña:\n")
    subprocess.run("nmcli dev wifi show-password", shell=True)