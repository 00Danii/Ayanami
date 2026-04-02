import json
import os
import sys

from colors import BLUE, BOLD, ORANGE, PINK, RED, RESET, WHITE

DATA_FILE = os.path.join(os.path.dirname(__file__), "firewall_apps.json")

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def display_apps(data):
    if not data:
        print(f"{RED}No hay apps registradas.{RESET}")
        return
    for idx, (app, info) in enumerate(data.items(), start=1):
        status = "(BLOQUEADA)" if info.get("blocked") else ""
        ips = ", ".join(info.get("ips", [])) or "sin IPs"
        print(f"[{idx}] {app} {status} — IPs: {ips}")

def prompt_app_selection(data, purpose="seleccionar"):
    if not data:
        print(f"{RED}No hay apps registradas.{RESET}")
        return None
    apps = list(data.keys())
    for i, name in enumerate(apps, start=1):
        print(f"{BLUE}[{i}] {WHITE}{name}{RESET}")
    print(f"{RED}[0] Cancelar{RESET}")
    choice = input(f"\n{PINK}Elija el número de la app para {purpose} (0 cancelar): {RESET}")
    if choice.strip() == "0":
        return None
    try:
        idx = int(choice)
        if 1 <= idx <= len(apps):
            return apps[idx - 1]
    except ValueError:
        pass
    print(f"{RED}[!] Selección inválida.{RESET}")
    return None

def register_app(data):
    name = input(f"\n{PINK}Nombre de la app (0 cancelar): {RESET}").strip()
    if name == "0" or not name:
        return
    if name in data:
        print(f"{RED}[!] La app ya existe. Use otra opción para modificarla.{RESET}")
        return
    ips_input = input(f"\n{PINK}IPs separadas por coma (dejar vacío para ninguna) (0 cancelar): {RESET}")
    if ips_input.strip() == "0":
        return
    ips = [ip.strip() for ip in ips_input.split(",") if ip.strip()]
    data[name] = {"ips": ips, "blocked": False}
    save_data(data)
    print(f"{ORANGE}App '{name}' registrada.{RESET}")

def delete_app_or_ip(data):
    app = prompt_app_selection(data, "borrar")
    if not app:
        return
    print(f"[1] Borrar app completa")
    print(f"[2] Borrar una IP de la app")
    print(f"[0] Cancelar")
    choice = input(f"\n{PINK}Opción: {RESET}")
    if choice.strip() == "0":
        return
    if choice.strip() == "1":
        confirm = input(f"\n{PINK}Confirma borrar la app '{app}'? (s/N): {RESET}")
        if confirm.lower() == "s":
            del data[app]
            save_data(data)
            print(f"{ORANGE}[+] App borrada.{RESET}")
        else:
            print(f"{ORANGE}[!] Operación cancelada.{RESET}")
        return
    if choice.strip() == "2":
        ips = data[app].get("ips", [])
        if not ips:
            print(f"{RED}[!] La app no tiene IPs registradas.{RESET}")
            return
        for i, ip in enumerate(ips, start=1):
            print(f"{BLUE}[{i}] {WHITE}{ip}{RESET}")
        print(f"{RED}[0] Cancelar{RESET}")
        sel = input(f"\n{PINK}Elija IP a borrar: {RESET}")
        if sel.strip() == "0":
            return
        try:
            idx = int(sel)
            if 1 <= idx <= len(ips):
                removed = ips.pop(idx - 1)
                if ips:
                    data[app]["ips"] = ips
                else:
                    # dejar lista vacía
                    data[app]["ips"] = []
                save_data(data)
                print(f"{ORANGE}[+] IP {removed} borrada de '{app}'.{RESET}")
                return
        except ValueError:
            pass
        print(f"{RED}[!] Selección inválida.{RESET}")

def set_block_state(data, block=True):
    action = "bloquear" if block else "desbloquear"
    app = prompt_app_selection(data, action)
    if not app:
        return
    # Aplicar reglas iptables usando funciones en firewall.py
    ips = data[app].get("ips", [])
    try:
        import firewall
        if block:
            # bloquear por IPs registradas
            if ips:
                firewall.block_app_ips(ips)
        else:
            # desbloquear por IPs registradas
            if ips:
                firewall.unblock_app_ips(ips)
    except Exception as e:
        print(f"{RED}[!] Error al aplicar reglas (se necesita permiso root): {e}")

    data[app]["blocked"] = bool(block)
    save_data(data)
    estado = "BLOQUEADA" if block else "DESBLOQUEADA"
    print(f"{ORANGE}[+] App '{app}' {estado}.{RESET}")

def main_menu():
    while True:
        data = load_data()
        print(f"\n{BOLD}{PINK}=== Firewall Apps ==={RESET}")
        print("[1] Ver apps")
        print("[2] Registrar app nueva")
        print("[3] Borrar app o IP de una app")
        print("[4] Bloquear app")
        print("[5] Desbloquear app")
        print(f"{RED}[0] Cancelar{RESET}")

        choice = input(f"\n{PINK}Opción: {RESET}")

        if choice.strip() == "0":
            print("Saliendo.")
            return
        if choice.strip() == "1":
            display_apps(data)
            continue
        if choice.strip() == "2":
            register_app(data)
            continue
        if choice.strip() == "3":
            delete_app_or_ip(data)
            continue
        if choice.strip() == "4":
            set_block_state(data, True)
            continue
        if choice.strip() == "5":
            set_block_state(data, False)
            continue
        print("Opción inválida.")

if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print(f"\n{RED}Interrumpido. Saliendo.{RESET}")
        sys.exit(0)
