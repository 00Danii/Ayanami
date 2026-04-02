import subprocess
from colors import BLUE, BOLD, CYAN, ORANGE, PINK, RED, RESET, WHITE
from scanner import get_neighbors

def run(cmd):
    subprocess.run(cmd, shell=True)


# =========================
# BLOQUEOS
# =========================

# Bloquear TODO el tráfico de un dispositivo
def block_device(ip):
    print(f"{ORANGE}[+] Bloqueando dispositivo {ip}{RESET}")
    run(f"iptables -A FORWARD -s {ip} -j DROP")


# Bloqueo global hacia una IP
def block_global(ip):
    print(f"{ORANGE}[+] Bloqueo global hacia {ip}{RESET}")
    run(f"iptables -A FORWARD -d {ip} -j DROP")

# Bloqueo una IP SOLO para dispositivo especifico
def block_ip_for_device(src_ip, dst_ip):
    print(f"{ORANGE}[+] Bloqueando {dst_ip} para {src_ip}{RESET}")

    run(f"iptables -A FORWARD -s {src_ip} -d {dst_ip} -j DROP")

# Bloqueo por app (básico pero efectivo)
def block_app(app):
    print(f"{ORANGE}[+] Bloqueando app: {app}{RESET}")

    if app == "youtube":
        run("iptables -A FORWARD -p udp --dport 443 -j DROP")  # QUIC
        run("iptables -A FORWARD -d 173.194.0.0/16 -j DROP")  # Google
        run("iptables -A FORWARD -d 142.250.0.0/15 -j DROP")

    elif app == "instagram":
        run("iptables -A FORWARD -d 31.13.0.0/16 -j DROP")  # Meta

    elif app == "facebook":
        run("iptables -A FORWARD -d 31.13.0.0/16 -j DROP")

    else:
        print(f"{RED}[!] App no soportada{RESET}")


# =========================
# GESTIÓN DE REGLAS
# =========================

def list_rules():
    print(f"\n{ORANGE}[+] Reglas activas:{RESET}\n")
    run("iptables -L FORWARD -n --line-numbers")


def delete_rule():
    list_rules()
    num = input(f"\n{PINK}Número de regla a eliminar: {RESET}")
    run(f"iptables -D FORWARD {num}")


def flush_rules():
    print(f"{ORANGE}[+] Eliminando todas las reglas...{RESET}")
    run("iptables -F FORWARD")


# =========================
# MENÚ FIREWALL
# =========================

def firewall_menu():
    while True:
        print(f"\n{BOLD}{CYAN}=== FIREWALL ==={RESET}")
        print(f"{RED}--- BLOQUEOS ---{RESET}")
        print(f"{BLUE}[1]{WHITE} Bloquear dispositivo (IP){RESET}")
        print(f"{BLUE}[2]{WHITE} Bloqueo global (IP destino){RESET}")
        print(f"{BLUE}[3]{WHITE} Bloquear IP destino a dispositivo{RESET}")

        print(f"{CYAN}--- APPs / REGLAS ---{RESET}")
        print(f"{BLUE}[4]{WHITE} Bloquear app{RESET}")
        print(f"{BLUE}[5]{WHITE} Ver reglas{RESET}")
        print(f"{BLUE}[6]{WHITE} Eliminar regla{RESET}")
        print(f"{BLUE}[7]{WHITE} Limpiar todo{RESET}")
        print(f"{RED}[0] Cancelar{RESET}")

        op = input(f"\n{CYAN}Opción: {RESET}")

        if op == "1":
            devices = get_neighbors()

            if not devices:
                print(f"{RED}[!] No hay dispositivos detectados{RESET}")
                continue

            print(f"\n{PINK}Dispositivos:{RESET}")
            for i, d in enumerate(devices):
                print(f"{i+1}. {d['ip']} ({d['mac']})")

            try:
                idx = int(input(f"\n{PINK}Selecciona el dispositivo: {RESET}")) - 1

                if idx < 0 or idx >= len(devices):
                    print(f"{RED}[!] Selección inválida{RESET}")
                    continue

                ip = devices[idx]["ip"]

                block_device(ip)

            except:
                print(f"{RED}[!] Entrada inválida{RESET}")
            
        elif op == "2":
            ip = input("IP destino: ")
            block_global(ip)

        elif op == "3":
            devices = get_neighbors()

            if not devices:
                print(f"{RED}[!] No hay dispositivos{RESET}")
                continue

            print(f"\n{PINK}Dispositivos:{RESET}")
            for i, d in enumerate(devices):
                print(f"{i+1}. {d['ip']} ({d['mac']})")

            try:
                idx = int(input(f"\n{PINK}Selecciona dispositivo: {RESET}")) - 1

                if idx < 0 or idx >= len(devices):
                    print(f"{RED}[!] Selección inválida{RESET}")
                    continue

                src_ip = devices[idx]["ip"]

                dst_ip = input("IP a bloquear: ")

                block_ip_for_device(src_ip, dst_ip)

            except:
                print(f"{RED}[!] Error en entrada{RESET}")

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
            print(f"{RED}[!] Opción inválida{RESET}")