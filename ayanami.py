from network import show_devices, disconnect_interface
from gateway import create_hotspot, show_hotspot_password
from scanner import show_neighbors
from monitor_bw import monitor_bandwidth
from sniffer import sniffer_menu

def menu():
    while True:
        print("\n=== AYANAMI ===")
        print("1. Ver Interfaces de Red (nmcli)")
        print("2. Desconectar interfaz")
        print("3. Crear hotspot")
        print("4. Ver detalles de hotspot")
        print("5. Ver dispositivos en la red (ip neigh)")
        print("6. Monitorear ancho de banda")
        print("7. Sniffer de paquetes")
        print("0. Salir")

        choice = input("\nOpción: ")
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

        elif choice == "0":
            print("Saliendo...")
            break

        else:
            print("Opción inválida")

if __name__ == "__main__":
    menu()