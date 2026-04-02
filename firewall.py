import subprocess
from colors import BLUE, BOLD, CYAN, ORANGE, PINK, PURPLE, RED, RESET, WHITE
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

# Bloqueo por nombre de app 
def block_app_ips(ips):
    if not ips:
        return
    for ip in ips:
        print(f"{ORANGE}[+] Bloqueando tráfico hacia {ip}{RESET}")
        run(f"iptables -A FORWARD -d {ip} -j DROP")

# Desbloqueo por nombre de app 
def unblock_app_ips(ips):
    if not ips:
        return
    for ip in ips:
        print(f"{ORANGE}[+] Eliminando bloqueo hacia {ip}{RESET}")
        run(f"iptables -D FORWARD -d {ip} -j DROP")


# Bloquear una lista de IPs SOLO para un dispositivo fuente específico
def block_app_ips_for_device(ips, src_ip):
    if not ips:
        return
    for ip in ips:
        print(f"{ORANGE}[+] Bloqueando {ip} para {src_ip}{RESET}")
        run(f"iptables -A FORWARD -s {src_ip} -d {ip} -j DROP")


# Desbloquear una lista de IPs SOLO para un dispositivo fuente específico
def unblock_app_ips_for_device(ips, src_ip):
    if not ips:
        return
    for ip in ips:
        print(f"{ORANGE}[+] Eliminando bloqueo {ip} para {src_ip}{RESET}")
        run(f"iptables -D FORWARD -s {src_ip} -d {ip} -j DROP")


# =========================
# GESTIÓN DE REGLAS
# =========================

def list_rules():
    print(f"\n{ORANGE}[+] Reglas activas:{RESET}\n")
    run("iptables -L FORWARD -n --line-numbers")


def delete_rule():
    list_rules()
    print(f"{RED}[0] Cancelar{RESET}")
    num = input(f"\n{PINK}Número de regla a eliminar: {RESET}")
    if num.strip() == "0":
        print(f"{ORANGE}[!] Operación cancelada{RESET}")
        return
    run(f"iptables -D FORWARD {num}")


def flush_rules():
    print(f"{ORANGE}[+] Eliminando todas las reglas...{RESET}")
    run("iptables -F FORWARD")


# =========================
# MENÚ FIREWALL
# =========================

def firewall_menu():
    while True:
        print(f"\n{BOLD}{PINK}=== FIREWALL ==={RESET}")
        print(f"{ORANGE}--- BLOQUEOS ---{RESET}")
        print(f"{ORANGE}[1]{WHITE} Bloquear dispositivo (IP){RESET}")
        print(f"{ORANGE}[2]{WHITE} Bloqueo global (IP destino){RESET}")
        print(f"{ORANGE}[3]{WHITE} Bloquear IP destino a dispositivo{RESET}")

        print(f"{PURPLE}--- APPs / REGLAS ---{RESET}")
        print(f"{PURPLE}[4]{WHITE} Bloquear app{RESET}")
        print(f"{PURPLE}[5]{WHITE} Ver reglas{RESET}")
        print(f"{PURPLE}[6]{WHITE} Eliminar regla{RESET}")
        print(f"{PURPLE}[7]{WHITE} Limpiar todo{RESET}")
        print(f"{RED}[0] Cancelar{RESET}")

        op = input(f"\n{PINK}Opción: {RESET}")

        if op == "1":
            devices = get_neighbors()

            if not devices:
                print(f"{RED}[!] No hay dispositivos detectados{RESET}")
                continue

            print(f"\n{PINK}Dispositivos:{RESET}")
            for i, d in enumerate(devices):
                print(f"{i+1}. {d['ip']} ({d['mac']})")
            print(f"{RED}[0] Cancelar{RESET}")

            try:
                choice = int(input(f"\n{PINK}Selecciona el dispositivo (0 cancelar): {RESET}"))
            except:
                print(f"{RED}[!] Entrada inválida{RESET}")
                continue

            if choice == 0:
                print(f"{ORANGE}[!] Operación cancelada{RESET}")
                continue

            idx = choice - 1
            if idx < 0 or idx >= len(devices):
                print(f"{RED}[!] Selección inválida{RESET}")
                continue

            ip = devices[idx]["ip"]
            block_device(ip)
            
        elif op == "2":
            dst_ip = input(f"{PINK}IP a bloquear (0 cancelar): {RESET}")
            if dst_ip.strip() == "0":
                print(f"{ORANGE}[!] Operación cancelada{RESET}")
                continue
            block_global(dst_ip)

        elif op == "3":
            devices = get_neighbors()

            if not devices:
                print(f"{RED}[!] No hay dispositivos{RESET}")
                continue

            print(f"\n{PINK}Dispositivos:{RESET}")
            for i, d in enumerate(devices):
                print(f"{i+1}. {d['ip']} ({d['mac']})")
            print(f"{RED}[0] Cancelar{RESET}")

            try:
                choice = int(input(f"\n{PINK}Selecciona dispositivo (0 cancelar): {RESET}"))
            except:
                print(f"{RED}[!] Entrada inválida{RESET}")
                continue

            if choice == 0:
                print(f"{ORANGE}[!] Operación cancelada{RESET}")
                continue

            idx = choice - 1
            if idx < 0 or idx >= len(devices):
                print(f"{RED}[!] Selección inválida{RESET}")
                continue

            src_ip = devices[idx]["ip"]

            dst_ip = input(f"{PINK}IP a bloquear (0 cancelar): {RESET}")
            if dst_ip.strip() == "0":
                print(f"{ORANGE}[!] Operación cancelada{RESET}")
                continue

            block_ip_for_device(src_ip, dst_ip)

        elif op == "4":
            try:
                import firewall_apps
                firewall_apps.main_menu()
            except Exception as e:
                print(f"{RED}[!] No se pudo abrir el submenu: {e}{RESET}")

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