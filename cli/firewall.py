import os
import subprocess
import ipaddress
import sys
from pathlib import Path
from colors import BLUE, BOLD, CYAN, ORANGE, PINK, PURPLE, RED, RESET, WHITE
from scanner import get_neighbors

# =========================================
# CONFIG - From reglasFirewall
# =========================================

DNSMASQ_CONF = (
    "/etc/NetworkManager/dnsmasq-shared.d/"
    "ayanami-block.conf"
)

# =========================================
# HELPERS
# =========================================

def run(cmd):
    print(f"\n[CMD] {cmd}")
    subprocess.run(cmd, shell=True)

def run_quiet(cmd):
    subprocess.run(cmd, shell=True)

def require_root():
    if os.geteuid() != 0:
        print("[!] Ejecuta este script como root")
        sys.exit(1)

# =========================================
# GATEWAY / NAT - From reglasFirewall
# =========================================

def enable_ip_forward():
    print("[+] Activando IP Forward")
    run_quiet("sysctl -w net.ipv4.ip_forward=1")
    try:
        with open("/etc/sysctl.conf", "r") as f:
            content = f.read()
        if "net.ipv4.ip_forward=1" not in content:
            with open("/etc/sysctl.conf", "a") as f:
                f.write("\nnet.ipv4.ip_forward=1\n")
    except Exception as e:
        print(f"[!] Error modificando sysctl.conf: {e}")

def force_dns():
    print("[+] Forzando DNS local")
    run_quiet(
        "iptables -t nat -C PREROUTING "
        "-p udp --dport 53 "
        "-j DNAT --to-destination 10.42.0.1 "
        "|| "
        "iptables -t nat -A PREROUTING "
        "-p udp --dport 53 "
        "-j DNAT --to-destination 10.42.0.1"
    )
    run_quiet(
        "iptables -t nat -C PREROUTING "
        "-p tcp --dport 53 "
        "-j DNAT --to-destination 10.42.0.1 "
        "|| "
        "iptables -t nat -A PREROUTING "
        "-p tcp --dport 53 "
        "-j DNAT --to-destination 10.42.0.1"
    )

def setup_nat():
    print("\n[+] Configuración NAT")
    print("[!] Necesitas la interfaz que tiene internet")
    print("[!] Ejemplo: wlan0, wlp2s0, eth0\n")
    run_quiet("ip route")
    interface = input("\nInterfaz internet: ").strip()
    if not interface:
        print("[!] Interfaz inválida")
        return False
    print(f"[+] Configurando MASQUERADE en {interface}")
    run_quiet(
        f"iptables -t nat -C POSTROUTING -o {interface} "
        f"-j MASQUERADE || "
        f"iptables -t nat -A POSTROUTING -o {interface} "
        f"-j MASQUERADE"
    )
    force_dns()
    return True

def configure_gateway():
    enable_ip_forward()
    if setup_nat():
        print("\n[✓] Gateway configurado")
        return True
    return False

# =========================================
# QUIC BLOCK - From reglasFirewall
# =========================================

def block_quic():
    print("[+] Bloqueando QUIC (UDP 443)")
    run_quiet(
        "iptables -C FORWARD -p udp --dport 443 -j DROP || "
        "iptables -I FORWARD 1 -p udp --dport 443 -j DROP"
    )

def unblock_quic():
    print("[+] Eliminando bloqueo QUIC")
    run_quiet(
        "iptables -D FORWARD -p udp --dport 443 -j DROP"
    )

# =========================================
# DNS BLOCKING - From reglasFirewall
# =========================================

def ensure_dnsmasq_shared_dir():
    Path("/etc/NetworkManager/dnsmasq-shared.d").mkdir(parents=True, exist_ok=True)

def write_domains(domains):
    ensure_dnsmasq_shared_dir()
    existing = ""
    if os.path.exists(DNSMASQ_CONF):
        with open(DNSMASQ_CONF, "r") as f:
            existing = f.read()
    with open(DNSMASQ_CONF, "a") as f:
        for domain in domains:
            line = f"address=/{domain}/0.0.0.0\n"
            if line not in existing:
                f.write(line)
    print("[+] Dominios agregados")

def remove_domains(domains):
    if not os.path.exists(DNSMASQ_CONF):
        return
    with open(DNSMASQ_CONF, "r") as f:
        lines = f.readlines()
    filtered = []
    for line in lines:
        keep = True
        for domain in domains:
            if f"/{domain}/" in line:
                keep = False
                break
        if keep:
            filtered.append(line)
    with open(DNSMASQ_CONF, "w") as f:
        f.writelines(filtered)
    print("[+] Dominios eliminados")

DEVICE_DNS_CONF = (
    "/etc/NetworkManager/dnsmasq-shared.d/"
    "ayanami-device-block.conf"
)

def write_domains_for_device(domains, device_ip):
    ensure_dnsmasq_shared_dir()
    existing = ""
    if os.path.exists(DEVICE_DNS_CONF):
        with open(DEVICE_DNS_CONF, "r") as f:
            existing = f.read()

    with open(DEVICE_DNS_CONF, "a") as f:
        for domain in domains:
            line = f"address=/{domain}/0.0.0.0#source={device_ip}\n"
            if line not in existing:
                f.write(line)
    print(f"[+] Dominios agregados para dispositivo {device_ip}")

def remove_domains_for_device(domains, device_ip):
    if not os.path.exists(DEVICE_DNS_CONF):
        return
    with open(DEVICE_DNS_CONF, "r") as f:
        lines = f.readlines()
    filtered = []
    for line in lines:
        keep = True
        if f"#source={device_ip}" in line:
            for domain in domains:
                if f"/{domain}/" in line:
                    keep = False
                    break
        if keep:
            filtered.append(line)
    with open(DEVICE_DNS_CONF, "w") as f:
        f.writelines(filtered)
    print(f"[+] Dominios eliminados para dispositivo {device_ip}")

def restart_networkmanager():
    print("[+] REINICIAR EL HOTSPOT MANUALMENTE PARA APLICAR CAMBIOS")

def reset_connections():
    print("[+] Cerrando conexiones activas")
    run_quiet("conntrack -F")

def flush_dns_rules():
    print("[+] Eliminando reglas DNS")
    if os.path.exists(DNSMASQ_CONF):
        os.remove(DNSMASQ_CONF)
    print("[+] Limpiando iptables")
    run_quiet("iptables -F FORWARD")
    run_quiet("iptables -t nat -F POSTROUTING")
    restart_networkmanager()
    reset_connections()
    print("[✓] Firewall limpiado")


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
        print(f"{CYAN}--- GATEWAY ---{RESET}")
        print(f"{CYAN}[1]{WHITE} Configurar gateway (NAT){RESET}")

        print(f"{ORANGE}--- BLOQUEOS IP ---{RESET}")
        print(f"{ORANGE}[2]{WHITE} Bloquear dispositivo (IP){RESET}")
        print(f"{ORANGE}[3]{WHITE} Bloqueo global (IP destino){RESET}")
        print(f"{ORANGE}[4]{WHITE} Bloquear IP destino a dispositivo{RESET}")
        print(f"{ORANGE}[5]{WHITE} Bloquear red completa (CIDR){RESET}")
        print(f"{ORANGE}[6]{WHITE} Bloquear rango de IPs{RESET}")
        print(f"{ORANGE}[7]{WHITE} Bloquear IP específica para rango de dispositivos{RESET}")

        print(f"{PURPLE}--- BLOQUEO DNS (APPS) ---{RESET}")
        print(f"{PURPLE}[8]{WHITE} Gestionar apps (bloqueo por dominio){RESET}")

        print(f"{BLUE}--- SISTEMA ---{RESET}")
        print(f"{BLUE}[9]{WHITE} Ver reglas{RESET}")
        print(f"{BLUE}[10]{WHITE} Eliminar regla{RESET}")
        print(f"{BLUE}[11]{WHITE} Flush conexiones (conntrack){RESET}")
        print(f"{BLUE}[12]{WHITE} Limpiar todo (firewall + DNS){RESET}")
        print(f"{RED}[0] Cancelar{RESET}")

        op = input(f"\n{PINK}Opción: {RESET}")

        if op == "1":
            require_root()
            configure_gateway()

        elif op == "2":
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

        elif op == "3":
            dst_ip = input(f"{PINK}IP a bloquear (0 cancelar): {RESET}")
            if dst_ip.strip() == "0":
                print(f"{ORANGE}[!] Operación cancelada{RESET}")
                continue
            block_global(dst_ip)

        elif op == "4":
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

        elif op == "5":
            cidr = input(f"{PINK}Red CIDR (ej: 192.168.1.0/24) o (0 cancelar): {RESET}")
            if cidr.strip() == "0":
                print(f"{ORANGE}[!] Operación cancelada{RESET}")
                continue
            block_network(cidr.strip())

        elif op == "6":
            ip_range = input(f"{PINK}Rango de IPs (ej: 192.168.1.100-200 o 192.168.1.100-192.168.1.200) o (0 cancelar): {RESET}")
            if ip_range.strip() == "0":
                print(f"{ORANGE}[!] Operación cancelada{RESET}")
                continue
            block_ip_range(ip_range.strip())

        elif op == "7":
            dst_ip = input(f"{PINK}IP a bloquear (0 cancelar): {RESET}")
            if dst_ip.strip() == "0":
                print(f"{ORANGE}[!] Operación cancelada{RESET}")
                continue
            device_range = input(f"{PINK}Rango de dispositivos (ej: 192.168.1.100-200 o 0 cancelar): {RESET}")
            if device_range.strip() == "0":
                print(f"{ORANGE}[!] Operación cancelada{RESET}")
                continue
            block_ip_for_device_range(dst_ip.strip(), device_range.strip())

        elif op == "8":
            try:
                import firewall_apps
                firewall_apps.main_menu()
            except Exception as e:
                print(f"{RED}[!] No se pudo abrir el submenu: {e}{RESET}")

        elif op == "9":
            list_rules()

        elif op == "10":
            delete_rule()

        elif op == "11":
            reset_connections()

        elif op == "12":
            require_root()
            flush_rules()
            flush_dns_rules()

        elif op == "0":
            break

        else:
            print(f"{RED}[!] Opción inválida{RESET}")