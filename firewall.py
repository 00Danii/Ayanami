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
    """Valida que el formato CIDR sea correcto (ej: 192.168.1.0/24)"""
    try:
        ipaddress.ip_network(cidr, strict=False)
        return True
    except ValueError:
        return False


def is_valid_ip_range(ip_range):
    """Valida que el formato de rango sea correcto (ej: 192.168.1.100-200)"""
    try:
        parts = ip_range.split('-')
        if len(parts) != 2:
            return False
        
        start_ip = parts[0].strip()
        end_part = parts[1].strip()
        
        # Validar IP inicio
        ipaddress.ip_address(start_ip)
        
        # Si el final es un IP completo
        try:
            ipaddress.ip_address(end_part)
            return True
        except ValueError:
            # Si es solo la última octeteta (ej: 200 en 192.168.1.100-200)
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
# BLOQUEOS POR REDES Y RANGOS
# =========================

def block_network(network_cidr):
    """Bloquea una red completa usando CIDR notation (ej: 192.168.1.0/24)"""
    if not is_valid_cidr(network_cidr):
        print(f"{RED}[!] Formato CIDR inválido. Usa: 192.168.1.0/24{RESET}")
        return False
    
    print(f"{ORANGE}[+] Bloqueando red {network_cidr}{RESET}")
    run(f"iptables -A FORWARD -d {network_cidr} -j DROP")
    print(f"{ORANGE}[✓] Red bloqueada exitosamente{RESET}")
    return True


def unblock_network(network_cidr):
    """Desbloquea una red completa usando CIDR notation"""
    if not is_valid_cidr(network_cidr):
        print(f"{RED}[!] Formato CIDR inválido. Usa: 192.168.1.0/24{RESET}")
        return False
    
    print(f"{ORANGE}[+] Desbloqueando red {network_cidr}{RESET}")
    run(f"iptables -D FORWARD -d {network_cidr} -j DROP")
    print(f"{ORANGE}[✓] Red desbloqueada exitosamente{RESET}")
    return True


def block_ip_range(ip_range):
    """Bloquea un rango de IPs (ej: 192.168.1.100-200 o 192.168.1.100-192.168.1.200)"""
    if not is_valid_ip_range(ip_range):
        print(f"{RED}[!] Formato de rango inválido. Usa:  192.168.1.100-200 o 192.168.1.100-192.168.1.200{RESET}")
        return False
    
    try:
        parts = ip_range.split('-')
        start_ip = parts[0].strip()
        end_part = parts[1].strip()
        
        # Completar el IP final si es necesario
        if '.' not in end_part:
            base_parts = start_ip.split('.')
            end_ip = '.'.join(base_parts[:3]) + '.' + end_part
        else:
            end_ip = end_part
        
        start = ipaddress.ip_address(start_ip)
        end = ipaddress.ip_address(end_ip)
        
        if start > end:
            print(f"{RED}[!] El IP inicial debe ser menor al final{RESET}")
            return False
        
        print(f"{ORANGE}[+] Bloqueando rango {start_ip} - {end_ip}{RESET}")
        
        # Generar reglas para cada IP en el rango
        current = start
        count = 0
        while current <= end:
            run(f"iptables -A FORWARD -d {current} -j DROP")
            current += 1
            count += 1
            
            # Mostrar progreso cada 50 IPs
            if count % 50 == 0:
                print(f"{ORANGE}[...] Procesadas {count} IPs...{RESET}")
        
        print(f"{ORANGE}[✓] Rango bloqueado exitosamente ({count} IPs){RESET}")
        return True
        
    except Exception as e:
        print(f"{RED}[!] Error al procesar el rango: {e}{RESET}")
        return False


def unblock_ip_range(ip_range):
    """Desbloquea un rango de IPs"""
    if not is_valid_ip_range(ip_range):
        print(f"{RED}[!] Formato de rango inválido. Usa: 192.168.1.100-200 o 192.168.1.100-192.168.1.200{RESET}")
        return False
    
    try:
        parts = ip_range.split('-')
        start_ip = parts[0].strip()
        end_part = parts[1].strip()
        
        # Completar el IP final si es necesario
        if '.' not in end_part:
            base_parts = start_ip.split('.')
            end_ip = '.'.join(base_parts[:3]) + '.' + end_part
        else:
            end_ip = end_part
        
        start = ipaddress.ip_address(start_ip)
        end = ipaddress.ip_address(end_ip)
        
        if start > end:
            print(f"{RED}[!] El IP inicial debe ser menor al final{RESET}")
            return False
        
        print(f"{ORANGE}[+] Desbloqueando rango {start_ip} - {end_ip}{RESET}")
        
        # Eliminar reglas para cada IP en el rango
        current = start
        count = 0
        while current <= end:
            run(f"iptables -D FORWARD -d {current} -j DROP")
            current += 1
            count += 1
            
            if count % 50 == 0:
                print(f"{ORANGE}[...] Procesadas {count} IPs...{RESET}")
        
        print(f"{ORANGE}[✓] Rango desbloqueado exitosamente ({count} IPs){RESET}")
        return True
        
    except Exception as e:
        print(f"{RED}[!] Error al procesar el rango: {e}{RESET}")
        return False


def block_ip_for_device_range(dst_ip, device_range):
    """Bloquea una IP destino para un rango de dispositivos fuente"""
    if not is_valid_ip_range(device_range):
        print(f"{RED}[!] Formato de rango inválido. Usa: 192.168.1.100-200 o 192.168.1.100-192.168.1.200{RESET}")
        return False
    
    try:
        parts = device_range.split('-')
        start_ip = parts[0].strip()
        end_part = parts[1].strip()
        
        # Completar el IP final si es necesario
        if '.' not in end_part:
            base_parts = start_ip.split('.')
            end_ip = '.'.join(base_parts[:3]) + '.' + end_part
        else:
            end_ip = end_part
        
        start = ipaddress.ip_address(start_ip)
        end = ipaddress.ip_address(end_ip)
        
        if start > end:
            print(f"{RED}[!] El IP inicial debe ser menor al final{RESET}")
            return False
        
        print(f"{ORANGE}[+] Bloqueando {dst_ip} para dispositivos {start_ip} - {end_ip}{RESET}")
        
        # Generar reglas para cada dispositivo en el rango
        current = start
        count = 0
        while current <= end:
            run(f"iptables -A FORWARD -s {current} -d {dst_ip} -j DROP")
            current += 1
            count += 1
            
            if count % 50 == 0:
                print(f"{ORANGE}[...] Procesados {count} dispositivos...{RESET}")
        
        print(f"{ORANGE}[✓] IP bloqueada para {count} dispositivos{RESET}")
        return True
        
    except Exception as e:
        print(f"{RED}[!] Error al procesar el rango: {e}{RESET}")
        return False


def unblock_ip_for_device_range(dst_ip, device_range):
    """Desbloquea una IP destino para un rango de dispositivos fuente"""
    if not is_valid_ip_range(device_range):
        print(f"{RED}[!] Formato de rango inválido. Usa: 192.168.1.100-200 o 192.168.1.100-192.168.1.200{RESET}")
        return False
    
    try:
        parts = device_range.split('-')
        start_ip = parts[0].strip()
        end_part = parts[1].strip()
        
        # Completar el IP final si es necesario
        if '.' not in end_part:
            base_parts = start_ip.split('.')
            end_ip = '.'.join(base_parts[:3]) + '.' + end_part
        else:
            end_ip = end_part
        
        start = ipaddress.ip_address(start_ip)
        end = ipaddress.ip_address(end_ip)
        
        if start > end:
            print(f"{RED}[!] El IP inicial debe ser menor al final{RESET}")
            return False
        
        print(f"{ORANGE}[+] Desbloqueando {dst_ip} para dispositivos {start_ip} - {end_ip}{RESET}")
        
        # Eliminar reglas para cada dispositivo en el rango
        current = start
        count = 0
        while current <= end:
            run(f"iptables -D FORWARD -s {current} -d {dst_ip} -j DROP")
            current += 1
            count += 1
            
            if count % 50 == 0:
                print(f"{ORANGE}[...] Procesados {count} dispositivos...{RESET}")
        
        print(f"{ORANGE}[✓] IP desbloqueada para {count} dispositivos{RESET}")
        return True
        
    except Exception as e:
        print(f"{RED}[!] Error al procesar el rango: {e}{RESET}")
        return False


def block_app_ips_for_device_range(ips, device_range):
    """Bloquea una lista de IPs de app para un rango de dispositivos fuente"""
    if not ips:
        return False
    
    if not is_valid_ip_range(device_range):
        print(f"{RED}[!] Formato de rango inválido. Usa: 192.168.1.100-200 o 192.168.1.100-192.168.1.200{RESET}")
        return False
    
    try:
        parts = device_range.split('-')
        start_ip = parts[0].strip()
        end_part = parts[1].strip()
        
        # Completar el IP final si es necesario
        if '.' not in end_part:
            base_parts = start_ip.split('.')
            end_ip = '.'.join(base_parts[:3]) + '.' + end_part
        else:
            end_ip = end_part
        
        start = ipaddress.ip_address(start_ip)
        end = ipaddress.ip_address(end_ip)
        
        if start > end:
            print(f"{RED}[!] El IP inicial debe ser menor al final{RESET}")
            return False
        
        print(f"{ORANGE}[+] Bloqueando app para dispositivos {start_ip} - {end_ip}{RESET}")
        
        total_count = 0
        for app_ip in ips:
            current = start
            count = 0
            while current <= end:
                run(f"iptables -A FORWARD -s {current} -d {app_ip} -j DROP")
                current += 1
                count += 1
                total_count += 1
            print(f"{ORANGE}    └─ {app_ip}: bloqueado para {count} dispositivos{RESET}")
        
        print(f"{ORANGE}[✓] App bloqueada exitosamente ({total_count} reglas creadas){RESET}")
        return True
        
    except Exception as e:
        print(f"{RED}[!] Error al procesar el rango: {e}{RESET}")
        return False


def unblock_app_ips_for_device_range(ips, device_range):
    """Desbloquea una lista de IPs de app para un rango de dispositivos fuente"""
    if not ips:
        return False
    
    if not is_valid_ip_range(device_range):
        print(f"{RED}[!] Formato de rango inválido. Usa: 192.168.1.100-200 o 192.168.1.100-192.168.1.200{RESET}")
        return False
    
    try:
        parts = device_range.split('-')
        start_ip = parts[0].strip()
        end_part = parts[1].strip()
        
        # Completar el IP final si es necesario
        if '.' not in end_part:
            base_parts = start_ip.split('.')
            end_ip = '.'.join(base_parts[:3]) + '.' + end_part
        else:
            end_ip = end_part
        
        start = ipaddress.ip_address(start_ip)
        end = ipaddress.ip_address(end_ip)
        
        if start > end:
            print(f"{RED}[!] El IP inicial debe ser menor al final{RESET}")
            return False
        
        print(f"{ORANGE}[+] Desbloqueando app para dispositivos {start_ip} - {end_ip}{RESET}")
        
        total_count = 0
        for app_ip in ips:
            current = start
            count = 0
            while current <= end:
                run(f"iptables -D FORWARD -s {current} -d {app_ip} -j DROP")
                current += 1
                count += 1
                total_count += 1
            print(f"{ORANGE}    └─ {app_ip}: desbloqueado para {count} dispositivos{RESET}")
        
        print(f"{ORANGE}[✓] App desbloqueada exitosamente ({total_count} reglas eliminadas){RESET}")
        return True
        
    except Exception as e:
        print(f"{RED}[!] Error al procesar el rango: {e}{RESET}")
        return False


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
            cidr = input(f"{PINK}Red CIDR (ej: 192.168.1.0/24) o (0 cancelar): {RESET}")
            if cidr.strip() == "0":
                print(f"{ORANGE}[!] Operación cancelada{RESET}")
                continue
            block_network(cidr.strip())

        elif op == "5":
            ip_range = input(f"{PINK}Rango de IPs (ej: 192.168.1.100-200 o 192.168.1.100-192.168.1.200) o (0 cancelar): {RESET}")
            if ip_range.strip() == "0":
                print(f"{ORANGE}[!] Operación cancelada{RESET}")
                continue
            block_ip_range(ip_range.strip())

        elif op == "6":
            dst_ip = input(f"{PINK}IP a bloquear (0 cancelar): {RESET}")
            if dst_ip.strip() == "0":
                print(f"{ORANGE}[!] Operación cancelada{RESET}")
                continue
            
            device_range = input(f"{PINK}Rango de dispositivos (ej: 192.168.1.100-200 o 0 cancelar): {RESET}")
            if device_range.strip() == "0":
                print(f"{ORANGE}[!] Operación cancelada{RESET}")
                continue
            
            block_ip_for_device_range(dst_ip.strip(), device_range.strip())


        elif op == "7":
            try:
                import firewall_apps
                firewall_apps.main_menu()
            except Exception as e:
                print(f"{RED}[!] No se pudo abrir el submenu: {e}{RESET}")

        elif op == "8":
            list_rules()

        elif op == "9":
            delete_rule()

        elif op == "10":
            flush_rules()

        elif op == "0":
            break

        else:
            print(f"{RED}[!] Opción inválida{RESET}")