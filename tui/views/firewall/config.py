from textual.containers import Vertical, Horizontal
from textual.widgets import Label, Button, Select, RichLog

import os
import subprocess

import network
import firewall_config
from firewall_ops import (
    get_dns_block_file,
    reset_apps_state,
    save_whitelist,
    load_whitelist,
)
from widgets.confirm_screen import ConfirmScreen


class ConfigTab(Vertical):
    def compose(self):
    
        with Vertical(classes="fw-card"):
            yield Label("Gateway / NAT", classes="fw-card-title")
            yield Label(
                "Configura el enrutamiento para que los dispositivos "
                "tengan salida a internet",
                classes="fw-card-desc"
            )
            with Horizontal(classes="fw-gw-row"):
                yield Select(
                    [],
                    prompt="Selecciona interfaz con internet (WAN)",
                    id="cfg-nat-iface"
                )
                yield Button("Configurar Gateway", id="cfg-setup-nat", variant="success")
                yield Button("Ver Estado", id="cfg-show-status", variant="primary")
                yield Button("Limpiar Firewall", id="cfg-flush", variant="error")

        yield RichLog(id="cfg-log", markup=True, highlight=True)

    def on_mount(self):
        ifaces = network.get_interfaces_detailed()
        select = self.query_one("#cfg-nat-iface", Select)
        options = [
            (f"{d['iface']} ({d['state']})", d['iface'])
            for d in ifaces
        ]
        select.set_options(options)
        ifaces_list = [d['iface'] for d in ifaces]
        if "eno1" in ifaces_list:
            select.value = "eno1"

    def _get_selected_interface(self):
        iface = getattr(self.app, "selected_interface", None)
        return iface

    def on_button_pressed(self, event: Button.Pressed):
        bid = event.button.id
        if bid == "cfg-setup-nat":
            self.setup_gateway()
        elif bid == "cfg-show-status":
            self.show_status()
        elif bid == "cfg-flush":
            self.app.push_screen(
                ConfirmScreen(
                    "Se limpiarán todas las reglas de firewall,\n"
                    "se desbloquearán todas las apps,\n"
                    "se desactivará la lista blanca\n"
                    "y se perderá la configuración del gateway.\n\n"
                    "Tendrás que configurar el gateway nuevamente.\n\n"
                    "¿Continuar?",
                    confirm_text="Limpiar"
                ),
                self.flush_all
            )

    def log(self, text: str):
        self.query_one("#cfg-log", RichLog).write(text)

    def run(self, cmd: str):
        self.log(f"[#565f89]$ {cmd}[/]")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.stdout:
            for line in result.stdout.strip().splitlines():
                self.log(f"[#a9b1d6]{line}[/]")
        if result.returncode != 0 and result.stderr:
            for line in result.stderr.strip().splitlines():
                self.log(f"[#f7768e]{line}[/]")
        return result

    def _save_gateway_config(self, wan_iface, lan_iface, dns_target) -> bool:
        """Persiste exactamente el gateway que se acaba de aplicar."""
        try:
            firewall_config.update_gateway(wan_iface, lan_iface, dns_target)
            self.log(
                "[#9ece6a]  ✓ Gateway guardado en backup.json[/]"
            )
            return True
        except Exception as e:
            self.log(f"[#f7768e]  ✗ No se pudo guardar config: {e}[/]")
            self.app.notify(
                "No se pudo guardar la configuración del gateway",
                severity="error",
            )
            return False

    def setup_gateway(self):
        select = self.query_one("#cfg-nat-iface", Select)
        iface = select.value  # WAN
        if iface is Select.NULL:
            self.app.notify("Selecciona la interfaz con internet", severity="error")
            return
        self.query_one("#cfg-log", RichLog).clear()

        lan_iface = self._get_selected_interface()  # LAN (en02)
        dns_target = network.get_iface_ip(lan_iface)

        self.log(f"\n[#e0af68]━━━ Configuración del Gateway ━━━[/]")

        self.log(f"[#565f89]   Interfaz WAN : {iface}[/]")
        self.log(f"[#565f89]   Interfaz LAN : {lan_iface}[/]")

        # ─────────────────────────────────────────────
        # IP FORWARD
        # ─────────────────────────────────────────────

        self.log("[#7dcfff]◆ Habilitando reenvío de paquetes IPv4[/]")

        self.run("sysctl -w net.ipv4.ip_forward=1")
        try:
            with open("/etc/sysctl.conf", "r") as f:
                content = f.read()
            if "net.ipv4.ip_forward=1" not in content:
                with open("/etc/sysctl.conf", "a") as f:
                    f.write("\nnet.ipv4.ip_forward=1\n")
                self.log("[#9ece6a]  ✓ IP Forward habilitado de forma persistente en /etc/sysctl.conf[/]")
            else:
                self.log("[#9ece6a]  ✓ IP Forward ya estaba configurado[/]")

        except Exception as e:
            self.log(f"[#f7768e]  ✗ Error al configurar /etc/sysctl.conf: {e}[/]")

        # ─────────────────────────────────────────────
        # MASQUERADE & FORWARD
        # ─────────────────────────────────────────────

        self.log("[#7dcfff]◆ Configurando NAT (MASQUERADE y FORWARD)[/]")

        self.log(f"[#565f89]  → El tráfico de los clientes saldrá por {iface}[/]")

        # Regla NAT Masquerade
        self.run(
            f"iptables -t nat -C POSTROUTING -o {iface} -j MASQUERADE 2>/dev/null || "
            f"iptables -t nat -A POSTROUTING -o {iface} -j MASQUERADE"
        )

        # Reglas de Reenvío entre LAN y WAN (Crucial para Access Points)
        if lan_iface:
            self.run(
                f"iptables -C FORWARD -i {lan_iface} -o {iface} -j ACCEPT 2>/dev/null || "
                f"iptables -A FORWARD -i {lan_iface} -o {iface} -j ACCEPT"
            )
            self.run(
                f"iptables -C FORWARD -i {iface} -o {lan_iface} -m state --state ESTABLISHED,RELATED -j ACCEPT 2>/dev/null || "
                f"iptables -A FORWARD -i {iface} -o {lan_iface} -m state --state ESTABLISHED,RELATED -j ACCEPT"
            )

        self.log("[#9ece6a]  ✓ Reglas de NAT y Reenvío (FORWARD) configuradas[/]")

        # ─────────────────────────────────────────────
        # DNS & BLOQUEO DOH/DOT
        # ─────────────────────────────────────────────

        self.log("[#7dcfff]◆ Configurando redirección DNS e interceptación[/]")

        if not dns_target:
            self.log(
                f"[#f7768e]  ✗ No se pudo obtener la IP de la interfaz LAN "
                f"{lan_iface}[/]"
            )

            self.app.notify(
                "No se pudo obtener la IP de la interfaz LAN",
                severity="error"
            )

            # WAN/NAT/FORWARD ya se aplicaron; guardamos lo que sí quedó
            # configurado aunque no se haya podido completar el DNS.
            self._save_gateway_config(iface, lan_iface, "")
            return

        self.log(f"[#565f89]  → Interfaz DNS: {lan_iface}[/]")
        self.log(f"[#565f89]  → Dirección local: {dns_target}[/]")
        self.log("[#565f89]  → Las consultas DNS de los clientes serán redirigidas a AYANAMI[/]")

        # Redirección de puerto 53 restringido a la LAN
        for proto in ("udp", "tcp"):
            self.run(
                f"iptables -t nat -C PREROUTING -i {lan_iface} -p {proto} --dport 53 "
                f"-j DNAT --to-destination {dns_target} 2>/dev/null || "
                f"iptables -t nat -A PREROUTING -i {lan_iface} -p {proto} --dport 53 "
                f"-j DNAT --to-destination {dns_target}"
            )

            self.log(f"[#9ece6a]  ✓ DNS {proto.upper()} (puerto 53) redirigido en {lan_iface}[/]")

        # Bloqueo de DNS sobre TLS (puerto 853) para evitar que los teléfonos eludan a Ayanami mediante DNS manual.
        # Se inserta en la posición 1, ANTES de la regla ACCEPT LAN→WAN: si se agregara al
        # final (-A), el ACCEPT la aceptaría primero y el DROP nunca se evaluaría.
        for proto in ("udp", "tcp"):
            self.run(
                f"iptables -C FORWARD -i {lan_iface} -p {proto} --dport 853 -j DROP 2>/dev/null || "
                f"iptables -I FORWARD 1 -i {lan_iface} -p {proto} --dport 853 -j DROP"
            )
        self.log("[#9ece6a]  ✓ Bloqueo anti-evasión (DoT puerto 853) activo[/]")

        # ─────────────────────────────────────────────
        # FINAL
        # ─────────────────────────────────────────────

        self.log("[#9ece6a]━━━ Gateway configurado correctamente ━━━[/]")

        self.log(f"[#565f89]   WAN → {iface}[/]")

        self.log(f"[#565f89]   LAN → {lan_iface} ({dns_target})[/]")

        self.log("[#565f89]   NAT → Activo[/]")

        self.log("[#565f89]   DNS → Redirección e interceptación local activa[/]")

        if self._save_gateway_config(iface, lan_iface, dns_target):
            self.app.notify(f"Gateway configurado en {iface}")

    def show_status(self):
        dns_conf = get_dns_block_file()
        self.query_one("#cfg-log", RichLog).clear()
        self.log("\n[#e0af68]━━━ IP FORWARD ━━━[/]")
        self.run("sysctl net.ipv4.ip_forward")
        self.log("\n[#e0af68]━━━ REGLAS DNS ━━━[/]")
        if os.path.exists(dns_conf):
            with open(dns_conf) as f:
                content = f.read().strip()
                self.log(f"[#a9b1d6]{content or 'Sin reglas'}[/]")
        else:
            self.log("[#565f89]Sin reglas[/]")
        self.log("\n[#e0af68]━━━ FORWARD ━━━[/]")
        self.run("iptables -L FORWARD -n --line-numbers")
        self.log("\n[#e0af68]━━━ NAT ━━━[/]")
        self.run("iptables -t nat -L -n --line-numbers")

    def flush_all(self, confirmed: bool | None = None):
        if not confirmed:
            return
        dns_conf = get_dns_block_file()
        self.query_one("#cfg-log", RichLog).clear()
        self.log("\n[#f7768e]━━━ Limpiando firewall ━━━[/]")
        if os.path.exists(dns_conf):
            os.remove(dns_conf)
            self.log("[#9ece6a]✓ Reglas DNS eliminadas[/]")
        self.log("[#7dcfff]◆ Limpiando iptables FORWARD[/]")
        self.run("iptables -F FORWARD")
        self.log("[#7dcfff]◆ Limpiando iptables NAT[/]")
        self.run("iptables -t nat -F")
        self.log("[#7dcfff]◆ Sincronizando estado de apps[/]")
        reset_apps_state()
        self.log("[#9ece6a]✓ Apps desbloqueadas en config[/]")
        self.log("[#7dcfff]◆ Apagando entradas de la lista blanca[/]")
        whitelist = load_whitelist()
        if whitelist:
            # Se conservan las entradas, pero todas quedan desactivadas:
            # así sus switches aparecen apagados y no se regeneran solas.
            save_whitelist(whitelist, whitelist)
            self.log("[#9ece6a]✓ Entradas de la lista blanca desactivadas[/]")
        else:
            self.log("[#565f89]Sin entradas en la lista blanca[/]")
        self.log("[#9ece6a]━━━ Firewall limpiado ━━━[/]")
        self.log("[#7dcfff]◆ Cerrando conexiones activas[/]")
        self.run("conntrack -F")
        apps_tab = self.screen.query_one("#fw-panel-apps")
        if hasattr(apps_tab, "refresh_apps"):
            apps_tab.refresh_apps()
        rules_tab = self.screen.query_one("#fw-panel-rules")
        if hasattr(rules_tab, "refresh_list"):
            rules_tab.refresh_list()
        self.app.notify("Firewall limpiado")
