import subprocess
from scanner import get_neighbors

def run(cmd):
    subprocess.run(cmd, shell=True)


# =========================
# BLOQUEOS
# =========================

# Bloquear TODO el tráfico de un dispositivo
def block_device(ip):
    print(f"[+] Bloqueando dispositivo {ip}")
    run(f"iptables -A FORWARD -s {ip} -j DROP")


# Bloqueo global hacia una IP
def block_global(ip):
    print(f"[+] Bloqueo global hacia {ip}")
    run(f"iptables -A FORWARD -d {ip} -j DROP")

# Bloqueo una IP SOLO para dispositivo especifico
def block_ip_for_device(src_ip, dst_ip):
    print(f"[+] Bloqueando {dst_ip} para {src_ip}")

    run(f"iptables -A FORWARD -s {src_ip} -d {dst_ip} -j DROP")

# Bloqueo por app (básico pero efectivo)
def block_app(app):
    print(f"[+] Bloqueando app: {app}")

    if app == "youtube":
        run("iptables -A FORWARD -p udp --dport 443 -j DROP")  # QUIC
        run("iptables -A FORWARD -d 173.194.0.0/16 -j DROP")  # Google
        run("iptables -A FORWARD -d 142.250.0.0/15 -j DROP")

    elif app == "instagram":
        run("iptables -A FORWARD -d 31.13.0.0/16 -j DROP")  # Meta

    elif app == "facebook":
        run("iptables -A FORWARD -d 31.13.0.0/16 -j DROP")

    else:
        print("[!] App no soportada")


# =========================
# GESTIÓN DE REGLAS
# =========================

def list_rules():
    print("\n[+] Reglas activas:\n")
    run("iptables -L FORWARD -n --line-numbers")


def delete_rule():
    list_rules()
    num = input("\nNúmero de regla a eliminar: ")
    run(f"iptables -D FORWARD {num}")


def flush_rules():
    print("[+] Eliminando todas las reglas...")
    run("iptables -F FORWARD")


# =========================
# MENÚ FIREWALL
# =========================

def firewall_menu():
    while True:
        print("\n=== FIREWALL ===")
        print("1. Bloquear dispositivo (IP)")
        print("2. Bloqueo global (IP destino)")
        print("3. Bloquear IP destino a dispositivo")
        print("4. Bloquear app")
        print("5. Ver reglas")
        print("6. Eliminar regla")
        print("7. Limpiar todo")
        print("0. Volver")

        op = input("\nOpción: ")

        if op == "1":
            devices = get_neighbors()

            if not devices:
                print("[!] No hay dispositivos detectados")
                continue

            print("\nDispositivos:")
            for i, d in enumerate(devices):
                print(f"{i+1}. {d['ip']} ({d['mac']})")

            try:
                idx = int(input("\nSelecciona el dispositivo: ")) - 1

                if idx < 0 or idx >= len(devices):
                    print("[!] Selección inválida")
                    continue

                ip = devices[idx]["ip"]

                block_device(ip)

            except:
                print("[!] Entrada inválida")
            
        elif op == "2":
            ip = input("IP destino: ")
            block_global(ip)

        elif op == "3":
            devices = get_neighbors()

            if not devices:
                print("[!] No hay dispositivos")
                continue

            print("\nDispositivos:")
            for i, d in enumerate(devices):
                print(f"{i+1}. {d['ip']} ({d['mac']})")

            try:
                idx = int(input("\nSelecciona dispositivo: ")) - 1

                if idx < 0 or idx >= len(devices):
                    print("[!] Selección inválida")
                    continue

                src_ip = devices[idx]["ip"]

                dst_ip = input("IP a bloquear: ")

                block_ip_for_device(src_ip, dst_ip)

            except:
                print("[!] Error en entrada")

        elif op == "4":
            app = input("App (youtube/instagram/facebook): ")
            block_app(app)

        elif op == "5":
            list_rules()

        elif op == "6":
            delete_rule()

        elif op == "7":
            flush_rules()

        elif op == "0":
            break

        else:
            print("Opción inválida")