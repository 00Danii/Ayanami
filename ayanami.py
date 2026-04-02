from colors import BLUE, BOLD, LIME, ORANGE, PINK, PURPLE, RED, RESET, WHITE
from network import show_devices, disconnect_interface
from gateway import create_hotspot, show_hotspot_password
from scanner import show_neighbors
from monitor_bw import monitor_bandwidth
from sniffer import sniffer_menu
from firewall import firewall_menu



def menu():
    while True:
        print(f"\n{BOLD}{LIME}╔══════════════════════════════════════╗{RESET}")
        print(f"{BOLD}{PINK}║      AYANAMI (REI HACKER RAINBOW)     ║")
        print(f"{BOLD}{LIME}╚══════════════════════════════════════╝{RESET}")

        print(f"{PINK}--- RED / INTERFACES ---{RESET}")
        print(f"{PINK}[1] {WHITE} Ver Interfaces de Red (nmcli){RESET}")
        print(f"{PINK}[2] {WHITE} Desconectar interfaz{RESET}")

        print(f"{BLUE}--- HOTSPOT / GATEWAY ---{RESET}")
        print(f"{BLUE}[3] {WHITE} Crear hotspot{RESET}")
        print(f"{BLUE}[4] {WHITE} Ver detalles de hotspot{RESET}")

        print(f"{PURPLE}--- ESCANEO / MONITOREO ---{RESET}")
        print(f"{PURPLE}[5] {WHITE} Ver dispositivos en la red (ip neigh){RESET}")
        print(f"{PURPLE}[6] {WHITE} Monitorear ancho de banda{RESET}")

        print(f"{ORANGE}--- ANALISIS / SEGURIDAD ---{RESET}")
        print(f"{ORANGE}[7] {WHITE} Sniffer de paquetes{RESET}")
        print(f"{ORANGE}[8] {WHITE} Firewall{RESET}")

        print(f"{RED}[0] Salir{RESET}")

        choice = input(f"\n{PINK}Opción: {RESET}")
        print()
        if choice == "1":
            show_devices()

        elif choice == "2":
            disconnect_interface()

        elif choice == "3":
            create_hotspot()

        elif choice == "4":
            show_hotspot_password()

        elif choice == "5":
            show_neighbors()
        
        elif choice == "6":
            monitor_bandwidth()
        
        elif choice == "7":
            sniffer_menu()

        elif choice == "8":
            firewall_menu()

        elif choice == "0":
            print("Saliendo...")
            break

        else:
            print("Opción inválida")

if __name__ == "__main__":
    menu()