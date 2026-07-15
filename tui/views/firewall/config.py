from textual.containers import Vertical, Horizontal
from textual.widgets import Label, Button, Select, RichLog

import os
import subprocess

import network


DNSMASQ_CONF = "/etc/NetworkManager/dnsmasq-shared.d/ayanami-block.conf"


class ConfigTab(Vertical):
    def compose(self):
        with Horizontal(classes="fw-config-header"):
            yield Label("Configuración del Firewall", classes="fw-section-title")
            yield Button("Ver Estado", id="cfg-show-status", classes="fw-config-btn")
            yield Button("Limpiar Firewall", id="cfg-flush", classes="fw-config-btn error")

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
                    prompt="Selecciona interfaz con internet",
                    id="cfg-nat-iface"
                )
                yield Button("Configurar Gateway", id="cfg-setup-nat", variant="primary")

        yield RichLog(id="cfg-log", markup=True, highlight=True)

    def on_mount(self):
        ifaces = network.get_interfaces_detailed()
        select = self.query_one("#cfg-nat-iface", Select)
        options = [
            (f"{d['iface']} ({d['state']})", d['iface'])
            for d in ifaces
        ]
        select.set_options(options)

    def on_button_pressed(self, event: Button.Pressed):
        bid = event.button.id
        if bid == "cfg-setup-nat":
            self.setup_gateway()
        elif bid == "cfg-show-status":
            self.show_status()
        elif bid == "cfg-flush":
            self.flush_all()

    def log(self, text: str):
        self.query_one("#cfg-log", RichLog).write(text)

    def run(self, cmd: str):
        self.log(f"[dim]$ {cmd}[/]")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.stdout:
            self.log(result.stdout.strip())
        if result.returncode != 0 and result.stderr:
            self.log(f"[red]{result.stderr.strip()}[/]")
        return result

    def setup_gateway(self):
        iface = self.query_one("#cfg-nat-iface", Select).value
        if not iface:
            self.app.notify("Selecciona la interfaz con internet", severity="error")
            return

        self.log(f"[yellow][+] Configurando gateway en {iface}...[/]")

        # Activar IP Forward
        self.log("[+] Activando IP Forward")
        self.run("sysctl -w net.ipv4.ip_forward=1")
        try:
            with open("/etc/sysctl.conf", "r") as f:
                content = f.read()
            if "net.ipv4.ip_forward=1" not in content:
                with open("/etc/sysctl.conf", "a") as f:
                    f.write("\nnet.ipv4.ip_forward=1\n")
        except Exception as e:
            self.log(f"[red][!] Error en sysctl.conf: {e}[/]")

        # Configurar MASQUERADE
        self.log(f"[+] Configurando MASQUERADE en {iface}")
        self.run(
            f"iptables -t nat -C POSTROUTING -o {iface} -j MASQUERADE 2>/dev/null || "
            f"iptables -t nat -A POSTROUTING -o {iface} -j MASQUERADE"
        )

        # Forzar DNS local
        self.log("[+] Forzando DNS local")
        for proto in ("udp", "tcp"):
            self.run(
                f"iptables -t nat -C PREROUTING -p {proto} --dport 53 "
                f"-j DNAT --to-destination 10.42.0.1 2>/dev/null || "
                f"iptables -t nat -A PREROUTING -p {proto} --dport 53 "
                f"-j DNAT --to-destination 10.42.0.1"
            )

        self.log("[green][✓] Gateway configurado[/]")
        self.app.notify(f"Gateway configurado en {iface}")

    def show_status(self):
        self.log("\n[bold orange]========== IP FORWARD ==========[/]")
        self.run("sysctl net.ipv4.ip_forward")
        self.log("\n[bold orange]========== REGLAS DNS ==========[/]")
        if os.path.exists(DNSMASQ_CONF):
            with open(DNSMASQ_CONF) as f:
                self.log(f.read().strip() or "Sin reglas")
        else:
            self.log("Sin reglas")
        self.log("\n[bold orange]========== FORWARD ==========[/]")
        self.run("iptables -L FORWARD -n --line-numbers 2>/dev/null || echo 'Sin reglas'")
        self.log("\n[bold orange]========== NAT ==========[/]")
        self.run("iptables -t nat -L -n --line-numbers 2>/dev/null || echo 'Sin reglas'")

    def flush_all(self):
        self.log("[red][+] Limpiando firewall...[/]")
        if os.path.exists(DNSMASQ_CONF):
            os.remove(DNSMASQ_CONF)
            self.log("[green][✓] Reglas DNS eliminadas[/]")
        self.run("iptables -F FORWARD")
        self.run("iptables -t nat -F")
        self.log("[green][✓] Firewall limpiado[/]")
        self.app.notify("Firewall limpiado")
