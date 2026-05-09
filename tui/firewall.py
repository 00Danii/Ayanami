import subprocess
import ipaddress
from colors import BLUE, BOLD, CYAN, ORANGE, PINK, PURPLE, RED, RESET, WHITE
from scanner import get_neighbors

def run(cmd):
    subprocess.run(cmd, shell=True)


# =========================
# VALIDACIONES
# =========================

def is_valid_cidr(cidr):
    try:
        ipaddress.ip_network(cidr, strict=False)
        return True
    except ValueError:
        return False


def is_valid_ip_range(ip_range):
    try:
        parts = ip_range.split('-')
        if len(parts) != 2:
            return False
        
        start_ip = parts[0].strip()
        end_part = parts[1].strip()
        
        ipaddress.ip_address(start_ip)
        
        try:
            ipaddress.ip_address(end_part)
            return True
        except ValueError:
            base_parts = start_ip.split('.')
            if len(base_parts) == 4:
                try:
                    end_ip = '.'.join(base_parts[:3]) + '.' + end_part
                    ipaddress.ip_address(end_ip)
                    return True
                except ValueError:
                    return False
        return False
    except Exception:
        return False


# =========================
# BLOQUEOS (CORE - retornan resultado)
# =========================

def block_device(ip):
    run(f"iptables -A FORWARD -s {ip} -j DROP")
    return f"Bloqueando dispositivo {ip}"


def block_global(ip):
    run(f"iptables -A FORWARD -d {ip} -j DROP")
    return f"Bloqueo global hacia {ip}"


def block_ip_for_device(src_ip, dst_ip):
    run(f"iptables -A FORWARD -s {src_ip} -d {dst_ip} -j DROP")
    return f"Bloqueando {dst_ip} para {src_ip}"


def block_app_ips(ips):
    if not ips:
        return "No hay IPs para bloquear"
    for ip in ips:
        run(f"iptables -A FORWARD -d {ip} -j DROP")
    return f"Bloqueando tráfico hacia {len(ips)} IPs"


def unblock_app_ips(ips):
    if not ips:
        return "No hay IPs para desbloquear"
    for ip in ips:
        run(f"iptables -D FORWARD -d {ip} -j DROP")
    return f"Eliminando bloqueo hacia {len(ips)} IPs"


def block_app_ips_for_device(ips, src_ip):
    if not ips:
        return "No hay IPs para bloquear"
    for ip in ips:
        run(f"iptables -A FORWARD -s {src_ip} -d {ip} -j DROP")
    return f"Bloqueando {len(ips)} IPs para {src_ip}"


def unblock_app_ips_for_device(ips, src_ip):
    if not ips:
        return "No hay IPs para desbloquear"
    for ip in ips:
        run(f"iptables -D FORWARD -s {src_ip} -d {ip} -j DROP")
    return f"Eliminando bloqueo {len(ips)} IPs para {src_ip}"


# =========================
# BLOQUEOS POR REDES Y RANGOS
# =========================

def block_network(network_cidr):
    if not is_valid_cidr(network_cidr):
        return f"Formato CIDR inválido. Usa: 192.168.1.0/24"
    
    run(f"iptables -A FORWARD -d {network_cidr} -j DROP")
    return f"Red {network_cidr} bloqueada exitosamente"


def unblock_network(network_cidr):
    if not is_valid_cidr(network_cidr):
        return f"Formato CIDR inválido. Usa: 192.168.1.0/24"
    
    run(f"iptables -D FORWARD -d {network_cidr} -j DROP")
    return f"Red {network_cidr} desbloqueada exitosamente"


def block_ip_range(ip_range):
    if not is_valid_ip_range(ip_range):
        return f"Formato de rango inválido. Usa: 192.168.1.100-200"
    
    try:
        parts = ip_range.split('-')
        start_ip = parts[0].strip()
        end_part = parts[1].strip()
        
        if '.' not in end_part:
            base_parts = start_ip.split('.')
            end_ip = '.'.join(base_parts[:3]) + '.' + end_part
        else:
            end_ip = end_part
        
        start = ipaddress.ip_address(start_ip)
        end = ipaddress.ip_address(end_ip)
        
        if start > end:
            return "El IP inicial debe ser menor al final"
        
        current = start
        count = 0
        while current <= end:
            run(f"iptables -A FORWARD -d {current} -j DROP")
            current += 1
            count += 1
            
            if count % 50 == 0:
                pass
        
        return f"Rango bloqueado exitosamente ({count} IPs)"
        
    except Exception as e:
        return f"Error al procesar el rango: {e}"


def unblock_ip_range(ip_range):
    if not is_valid_ip_range(ip_range):
        return f"Formato de rango inválido. Usa: 192.168.1.100-200"
    
    try:
        parts = ip_range.split('-')
        start_ip = parts[0].strip()
        end_part = parts[1].strip()
        
        if '.' not in end_part:
            base_parts = start_ip.split('.')
            end_ip = '.'.join(base_parts[:3]) + '.' + end_part
        else:
            end_ip = end_part
        
        start = ipaddress.ip_address(start_ip)
        end = ipaddress.ip_address(end_ip)
        
        if start > end:
            return "El IP inicial debe ser menor al final"
        
        current = start
        count = 0
        while current <= end:
            run(f"iptables -D FORWARD -d {current} -j DROP")
            current += 1
            count += 1
            
            if count % 50 == 0:
                pass
        
        return f"Rango desbloqueado exitosamente ({count} IPs)"
        
    except Exception as e:
        return f"Error al procesar el rango: {e}"


def block_ip_for_device_range(dst_ip, device_range):
    if not is_valid_ip_range(device_range):
        return f"Formato de rango inválido"
    
    try:
        parts = device_range.split('-')
        start_ip = parts[0].strip()
        end_part = parts[1].strip()
        
        if '.' not in end_part:
            base_parts = start_ip.split('.')
            end_ip = '.'.join(base_parts[:3]) + '.' + end_part
        else:
            end_ip = end_part
        
        start = ipaddress.ip_address(start_ip)
        end = ipaddress.ip_address(end_ip)
        
        if start > end:
            return "El IP inicial debe ser menor al final"
        
        current = start
        count = 0
        while current <= end:
            run(f"iptables -A FORWARD -s {current} -d {dst_ip} -j DROP")
            current += 1
            count += 1
        
        return f"IP bloqueada para {count} dispositivos"
        
    except Exception as e:
        return f"Error al procesar el rango: {e}"


def unblock_ip_for_device_range(dst_ip, device_range):
    if not is_valid_ip_range(device_range):
        return f"Formato de rango inválido"
    
    try:
        parts = device_range.split('-')
        start_ip = parts[0].strip()
        end_part = parts[1].strip()
        
        if '.' not in end_part:
            base_parts = start_ip.split('.')
            end_ip = '.'.join(base_parts[:3]) + '.' + end_part
        else:
            end_ip = end_part
        
        start = ipaddress.ip_address(start_ip)
        end = ipaddress.ip_address(end_ip)
        
        if start > end:
            return "El IP inicial debe ser menor al final"
        
        current = start
        count = 0
        while current <= end:
            run(f"iptables -D FORWARD -s {current} -d {dst_ip} -j DROP")
            current += 1
            count += 1
        
        return f"IP desbloqueada para {count} dispositivos"
        
    except Exception as e:
        return f"Error al procesar el rango: {e}"


def block_app_ips_for_device_range(ips, device_range):
    if not ips:
        return "No hay IPs para bloquear"
    
    if not is_valid_ip_range(device_range):
        return f"Formato de rango inválido"
    
    try:
        parts = device_range.split('-')
        start_ip = parts[0].strip()
        end_part = parts[1].strip()
        
        if '.' not in end_part:
            base_parts = start_ip.split('.')
            end_ip = '.'.join(base_parts[:3]) + '.' + end_part
        else:
            end_ip = end_part
        
        start = ipaddress.ip_address(start_ip)
        end = ipaddress.ip_address(end_ip)
        
        if start > end:
            return "El IP inicial debe ser menor al final"
        
        total_count = 0
        for app_ip in ips:
            current = start
            count = 0
            while current <= end:
                run(f"iptables -A FORWARD -s {current} -d {app_ip} -j DROP")
                current += 1
                count += 1
                total_count += 1
        
        return f"App bloqueada exitosamente ({total_count} reglas creadas)"
        
    except Exception as e:
        return f"Error al procesar el rango: {e}"


def unblock_app_ips_for_device_range(ips, device_range):
    if not ips:
        return "No hay IPs para desbloquear"
    
    if not is_valid_ip_range(device_range):
        return f"Formato de rango inválido"
    
    try:
        parts = device_range.split('-')
        start_ip = parts[0].strip()
        end_part = parts[1].strip()
        
        if '.' not in end_part:
            base_parts = start_ip.split('.')
            end_ip = '.'.join(base_parts[:3]) + '.' + end_part
        else:
            end_ip = end_part
        
        start = ipaddress.ip_address(start_ip)
        end = ipaddress.ip_address(end_ip)
        
        if start > end:
            return "El IP inicial debe ser menor al final"
        
        total_count = 0
        for app_ip in ips:
            current = start
            count = 0
            while current <= end:
                run(f"iptables -D FORWARD -s {current} -d {app_ip} -j DROP")
                current += 1
                count += 1
                total_count += 1
        
        return f"App desbloqueada exitosamente ({total_count} reglas eliminadas)"
        
    except Exception as e:
        return f"Error al procesar el rango: {e}"


# =========================
# GESTIÓN DE REGLAS
# =========================

def list_rules():
    return subprocess.check_output("iptables -L FORWARD -n --line-numbers", shell=True).decode()


def delete_rule(num):
    run(f"iptables -D FORWARD {num}")
    return f"Regla {num} eliminada"


def flush_rules():
    run("iptables -F FORWARD")
    return "Todas las reglas FORWARD eliminadas"


# =========================
# MENÚ FIREWALL (CLI)
# =========================

def firewall_menu():
    while True:
        print(f"\n{BOLD}{PINK}=== FIREWALL ==={RESET}")
        print(f"{ORANGE}--- BLOQUEOS ---{RESET}")
        print(f"{ORANGE}[1]{WHITE} Bloquear dispositivo (IP){RESET}")
        print(f"{ORANGE}[2]{WHITE} Bloqueo global (IP destino){RESET}")
        print(f"{ORANGE}[3]{WHITE} Bloquear IP destino a dispositivo{RESET}")
        print(f"{ORANGE}[4]{WHITE} Bloquear red completa (CIDR){RESET}")
        print(f"{ORANGE}[5]{WHITE} Bloquear rango de IPs{RESET}")
        print(f"{ORANGE}[6]{WHITE} Bloquear IP específica para rango de dispositivos{RESET}")

        print(f"{PURPLE}--- APPs / REGLAS ---{RESET}")
        print(f"{PURPLE}[7]{WHITE} Bloquear app{RESET}")
        print(f"{PURPLE}[8]{WHITE} Ver reglas{RESET}")
        print(f"{PURPLE}[9]{WHITE} Eliminar regla{RESET}")
        print(f"{PURPLE}[10]{WHITE} Limpiar todo{RESET}")
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
            print(f"{ORANGE}[+] {block_device(ip)}{RESET}")
            
        elif op == "2":
            dst_ip = input(f"{PINK}IP a bloquear (0 cancelar): {RESET}")
            if dst_ip.strip() == "0":
                print(f"{ORANGE}[!] Operación cancelada{RESET}")
                continue
            print(f"{ORANGE}[+] {block_global(dst_ip)}{RESET}")

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

            print(f"{ORANGE}[+] {block_ip_for_device(src_ip, dst_ip)}{RESET}")

        elif op == "4":
            cidr = input(f"{PINK}Red CIDR (ej: 192.168.1.0/24) o (0 cancelar): {RESET}")
            if cidr.strip() == "0":
                print(f"{ORANGE}[!] Operación cancelada{RESET}")
                continue
            print(f"{ORANGE}[+] {block_network(cidr.strip())}{RESET}")

        elif op == "5":
            ip_range = input(f"{PINK}Rango de IPs (ej: 192.168.1.100-200) o (0 cancelar): {RESET}")
            if ip_range.strip() == "0":
                print(f"{ORANGE}[!] Operación cancelada{RESET}")
                continue
            print(f"{ORANGE}[+] {block_ip_range(ip_range.strip())}{RESET}")

        elif op == "6":
            dst_ip = input(f"{PINK}IP a bloquear (0 cancelar): {RESET}")
            if dst_ip.strip() == "0":
                print(f"{ORANGE}[!] Operación cancelada{RESET}")
                continue
            
            device_range = input(f"{PINK}Rango de dispositivos (ej: 192.168.1.100-200) o (0 cancelar): {RESET}")
            if device_range.strip() == "0":
                print(f"{ORANGE}[!] Operación cancelada{RESET}")
                continue
            
            print(f"{ORANGE}[+] {block_ip_for_device_range(dst_ip.strip(), device_range.strip())}{RESET}")


        elif op == "7":
            try:
                import firewall_apps
                firewall_apps.main_menu()
            except Exception as e:
                print(f"{RED}[!] No se pudo abrir el submenu: {e}{RESET}")

        elif op == "8":
            print(f"\n{ORANGE}[+] Reglas activas:{RESET}\n")
            print(list_rules())

        elif op == "9":
            print(list_rules())
            print(f"{RED}[0] Cancelar{RESET}")
            num = input(f"\n{PINK}Número de regla a eliminar: {RESET}")
            if num.strip() == "0":
                print(f"{ORANGE}[!] Operación cancelada{RESET}")
                continue
            print(f"{ORANGE}[+] {delete_rule(num)}{RESET}")

        elif op == "10":
            print(f"{ORANGE}[+] {flush_rules()}{RESET}")

        elif op == "0":
            break

        else:
            print(f"{RED}[!] Opción inválida{RESET}")