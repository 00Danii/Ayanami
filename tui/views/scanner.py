from textual.app import ComposeResult

from textual.containers import (
    Vertical,
    Horizontal
)

from textual.widgets import (
    Label,
    Button,
    DataTable,
    Static
)

import scanner
import socket
from datetime import datetime


class ScannerView(Vertical):

    def compose(self) -> ComposeResult:
        yield Horizontal(
            Label(
                "Escáner de dispositivos en la red",
                classes="scanner-title"
            ),

            Button(
                "ESCANEAR",
                variant="primary",
                id="refresh-scanner"
            ),

            classes="scanner-topbar"
        )

        # INFORMACION GENERAL

        yield Horizontal(
            Static(
                "Interfaz: --",
                id="scanner-iface",
                classes="scanner-stat"
            ),

            Static(
                "Dispositivos: 0",
                id="scanner-count",
                classes="scanner-stat"
            ),

            Static(
                "Último Escaneo: --",
                id="scanner-lastscan",
                classes="scanner-stat"
            ),

            classes="scanner-stats-bar"
        )

        # TABLA DE DISPOSITIVOS 
        yield DataTable(
            id="scanner-table"
        )

        # PANEL DE INFORMACION DEL DISPOSITIVO
        with Vertical(
            id="device-panel"
        ):
            yield Label(
                "Información del dispositivo",
                classes="device-title"
            )
            yield Static(
                "Selecciona un dispositivo",
                id="device-info"
            )


    def on_mount(self):
        table = self.query_one(
            "#scanner-table",
            DataTable
        )
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns(
            "IP",
            "HOSTNAME",
            "MAC",
            "VENDOR",
            "STATE",
            "INTERFACE"
        )

        self.refresh_data()

    # BOTON DE REFRESH

    def refresh_data(self):
        table = self.query_one(
            "#scanner-table",
            DataTable
        )

        table.clear()

        devices = scanner.get_neighbors_simple()

        iface = getattr(
            self.app,
            "selected_interface",
            None
        )

        if iface:
            devices = scanner.enrich_devices(
                devices,
                iface
            )
        for device in devices:

            hostname = self.resolve_hostname(
                device["ip"]
            )

            table.add_row(
                device["ip"],
                hostname,
                device["mac"],
                device["vendor"],
                device["state"],
                device["iface"]
            )

        # ESTADISTICAS

        self.query_one(
            "#scanner-count",
            Static
        ).update(
            f"Dispositivos: {len(devices)}"
        )

        self.query_one(
            "#scanner-lastscan",
            Static
        ).update(
            f"Último Escaneo: {datetime.now().strftime('%H:%M:%S')}"
        )

        self.query_one(
            "#scanner-iface",
            Static
        ).update(
            f"Interfaz: {iface or '--'}"
        )

    # RESOLVER HOSTNAME

    def resolve_hostname(self, ip):

        try:

            return socket.gethostbyaddr(ip)[0]

        except:

            return "unknown"

    # EVENTOS

    def on_button_pressed(self, event):
        if event.button.id == "refresh-scanner":
            self.refresh_data()
            self.notify(
                "Escaneo completado"
            )

    # SELECCION DE FILA EN LA TABLA
    def on_data_table_row_selected(
        self,
        event: DataTable.RowSelected
    ):
        table = self.query_one(
            "#scanner-table",
            DataTable
        )
        row = table.get_row(
            event.row_key
        )

        ip, hostname, mac, vendor, state, iface = row

        self.query_one(
            "#device-info",
            Static
        ).update(
            "[yellow]Analizando host...[/]"
        )

        data = scanner.fingerprint_host(ip)

        if "error" in data:

            self.query_one(
                "#device-info",
                Static
            ).update(
                f"[red]{data['error']}[/]"
            )

            return

        ports_text = ""

        for port in data["ports"]:

            ports_text += (
                f"\n"
                f"[cyan]{port['port']}[/] "
                f"{port['service']} "
                f"({port['state']})"
            )

        info = (
            f"[cyan]IP:[/] {ip}\n"
            f"[green]HOSTNAME:[/] {hostname}\n"
            f"[yellow]MAC:[/] {mac}\n"
            f"[magenta]VENDOR:[/] {vendor}\n"
            f"[blue]STATE:[/] {state}\n"
            f"[white]INTERFACE:[/] {iface}\n\n"
            f"[bold green]OS:[/] {data['os']}\n\n"
            f"[bold yellow]PUERTOS:[/]"
            f"{ports_text}"
        )
        self.query_one(
            "#device-info",
            Static
        ).update(info)