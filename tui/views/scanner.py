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
        neighbors = scanner.get_neighbors()
        for device in neighbors:
            hostname = self.resolve_hostname(
                device["ip"]
            )
            table.add_row(
                device["ip"],
                hostname,
                device["mac"],
                device["iface"]
            )

        # ESTADISTICAS

        self.query_one(
            "#scanner-count",
            Static
        ).update(
            f"Dispositivos: {len(neighbors)}"
        )

        self.query_one(
            "#scanner-lastscan",
            Static
        ).update(
            f"Último Escaneo: {datetime.now().strftime('%H:%M:%S')}"
        )

        iface = getattr(
            self.app,
            "selected_interface",
            "--"
        )

        self.query_one(
            "#scanner-iface",
            Static
        ).update(
            f"Interfaz: {iface}"
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

        ip, hostname, mac, iface = row

        info = (
            f"[cyan]IP:[/] {ip}\n"
            f"[green]HOSTNAME:[/] {hostname}\n"
            f"[yellow]MAC:[/] {mac}\n"
            f"[magenta]INTERFACE:[/] {iface}"
        )
        self.query_one(
            "#device-info",
            Static
        ).update(info)