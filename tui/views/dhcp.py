from textual.containers import Vertical, Horizontal
from textual.widgets import Label, Button, RichLog

import subprocess


class DhcpView(Vertical):
    """Estado y configuración del servicio dnsmasq (DHCP y DNS local)."""

    def compose(self):
        with Vertical(classes="fw-card"):
            with Horizontal(classes="dhcp-header-row"):
                with Vertical(classes="dhcp-info-col"):
                    yield Label("DHCP / dnsmasq", classes="fw-card-title")
                    yield Label(
                        "Estado del servicio que reparte DHCP y resuelve el DNS local.",
                        classes="fw-card-desc"
                    )
                with Horizontal(classes="dhcp-actions"):
                    yield Button("Estado", id="dhcp-status", variant="primary")
                    yield Button("Ver Config", id="dhcp-show-config")
                    yield Button("Reiniciar Servicio", id="dhcp-restart", variant="warning")

        yield RichLog(id="dhcp-log", markup=True, highlight=True)

    def refresh_data(self):
        self.show_status()

    def on_button_pressed(self, event: Button.Pressed):
        bid = event.button.id
        if bid == "dhcp-status":
            self.show_status()
        elif bid == "dhcp-show-config":
            self.show_config()
        elif bid == "dhcp-restart":
            self.restart_service()

    def log(self, text: str):
        self.query_one("#dhcp-log", RichLog).write(text)

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

    def show_status(self, clear=True):
        if clear:
            self.query_one("#dhcp-log", RichLog).clear()
        self.log("[#7dcfff]◆ Estado del servicio dnsmasq[/]")
        self.run("systemctl status dnsmasq --no-pager")

    def show_config(self):
        self.query_one("#dhcp-log", RichLog).clear()
        self.log("[#7dcfff]◆ Contenido de /etc/dnsmasq.conf[/]")
        self.run("cat /etc/dnsmasq.conf")

    def restart_service(self):
        # systemctl restart puede tardar: se corre en un hilo para no
        # congelar la interfaz y el resultado se pinta desde el hilo principal.
        self.log("[#7dcfff]◆ Reiniciando servicio dnsmasq…[/]")
        self.run_worker(self._do_restart, thread=True)

    def _do_restart(self):
        result = subprocess.run(
            "systemctl restart dnsmasq", shell=True, capture_output=True, text=True
        )
        self.app.call_from_thread(self._after_restart, result)

    def _after_restart(self, result):
        # Orden pedido: limpiar, mensaje del resultado, línea en blanco y estado.
        self.query_one("#dhcp-log", RichLog).clear()
        if result.returncode == 0:
            self.log("[#09b609]✓ Servicio dnsmasq reiniciado correctamente[/]")
        else:
            self.log("[#f7768e]✗ Error al reiniciar dnsmasq[/]")
            for line in result.stderr.strip().splitlines():
                self.log(f"[#f7768e]{line}[/]")
        self.log("")
        self.show_status(clear=False)
