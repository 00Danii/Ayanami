from textual.containers import Vertical, Horizontal
from textual.widgets import Label, Button, Select, RichLog

import os
import subprocess

import network
from firewall_ops import get_dns_block_file


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
                    prompt="Selecciona interfaz con internet",
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
        self.log(f"[#565f89]$ {cmd}[/]")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.stdout:
            for line in result.stdout.strip().splitlines():
                self.log(f"[#a9b1d6]{line}[/]")
        if result.returncode != 0 and result.stderr:
            for line in result.stderr.strip().splitlines():
                self.log(f"[#f7768e]{line}[/]")
        return result

    def setup_gateway(self):
        select = self.query_one("#cfg-nat-iface", Select)
        iface = select.value
        if iface is Select.NULL:
            self.app.notify("Selecciona la interfaz con internet", severity="error")
            return
        self.query_one("#cfg-log", RichLog).clear()
        self.log(f"\n[#e0af68]━━━ Configurando gateway en [bold]{iface}[/] ━━━[/]")

        self.log("[#7dcfff]◆ Activando IP Forward[/]")
        self.run("sysctl -w net.ipv4.ip_forward=1")
        try:
            with open("/etc/sysctl.conf", "r") as f:
                content = f.read()
            if "net.ipv4.ip_forward=1" not in content:
                with open("/etc/sysctl.conf", "a") as f:
                    f.write("\nnet.ipv4.ip_forward=1\n")
                self.log("[#9ece6a]✓ Persistente en /etc/sysctl.conf[/]")
        except Exception as e:
            self.log(f"[#f7768e]✗ Error en sysctl.conf: {e}[/]")

        self.log("[#7dcfff]◆ Configurando MASQUERADE[/]")
        self.run(
            f"iptables -t nat -C POSTROUTING -o {iface} -j MASQUERADE 2>/dev/null || "
            f"iptables -t nat -A POSTROUTING -o {iface} -j MASQUERADE"
        )

        self.log("[#7dcfff]◆ Forzando DNS local[/]")
        for proto in ("udp", "tcp"):
            self.run(
                f"iptables -t nat -C PREROUTING -p {proto} --dport 53 "
                f"-j DNAT --to-destination 10.42.0.1 2>/dev/null || "
                f"iptables -t nat -A PREROUTING -p {proto} --dport 53 "
                f"-j DNAT --to-destination 10.42.0.1"
            )

        self.log("[#9ece6a]━━━ Gateway configurado ━━━[/]")
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

    def flush_all(self):
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
        self.log("[#9ece6a]━━━ Firewall limpiado ━━━[/]")
        self.log("[#7dcfff]◆ Cerrando conexiones activas[/]")
        self.run("conntrack -F")
        self.app.notify("Firewall limpiado")
