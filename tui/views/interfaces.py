from textual.containers import Vertical, Horizontal
from textual.widgets import Label, Button, Select

from widgets.sidebar import Sidebar
from widgets.interface_row import InterfaceRow

import subprocess
import network


class InterfacesView(Vertical):

    def compose(self):
        yield Horizontal(
            Label(
                "Interfaces",
                classes="title"
            ),
            Button(
                "Refresh",
                variant="primary",
                id="refresh"
            ),
            classes="topbar"
        )
        
        yield Horizontal(
            Label("Interfaz", classes="header-col iface-name"),
            Label("Tipo", classes="header-col iface-type"),
            Label("Estado", classes="header-col iface-state"),
            Label("Acciones", classes="header-col iface-actions"),
            id="interfaces-header"
        )

        yield Vertical(
            id="interfaces-container"
        )

    def on_mount(self):
        self.refresh_data()

    def refresh_data(self):
        container = self.query_one(
            "#interfaces-container",
            Vertical
        )
        container.remove_children()
        interfaces = network.get_interfaces_detailed()
        for iface in interfaces:
            container.mount(
                InterfaceRow(iface)
            )

    def on_button_pressed(self, event: Button.Pressed):
        button_id = event.button.id
        if button_id == "refresh":
            self.refresh_data()
            return

        if button_id.startswith("global-"):
            iface = button_id.replace("global-", "")
            self.set_global_interface(iface)

        elif button_id.startswith("disconnect-"):
            iface = button_id.replace("disconnect-", "")
            self.disconnect_interface(iface)

    def set_global_interface(self, iface: str):
        self.app.selected_interface = iface
        try:
            sidebar = self.app.query_one(Sidebar)
            sidebar.query_one(
                "#global-iface-select",
                Select
            ).value = iface
        except:
            pass
        self.notify(f"{iface} global")

    def disconnect_interface(self, iface: str):
        subprocess.run(
            f"nmcli device disconnect {iface}",
            shell=True,
            capture_output=True,
            text=True
        )
        self.notify(f"{iface} desconectada")
        self.refresh_data()