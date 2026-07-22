from textual.containers import Vertical
from textual.widgets import Label, Select, Button

import network


NAV_ITEMS = [
    ("nav-interfaces", ">  Interfaces"),
    ("nav-hotspot",    ">  Hotspot   "),
    ("nav-scanner",    ">  Scanner   "),
    ("nav-monitor",    ">  Monitor   "),
    ("nav-sniffer",    ">  Sniffer   "),
    ("nav-firewall",   ">  Firewall  "),
    ("nav-sistema",    ">  Sistema   "),
]


class Sidebar(Vertical):

    def compose(self):
        with Vertical(id="app-title-box"):
            yield Label("AYANAMI", id="app-title")
            #yield Label("network toolkit", id="app-subtitle")

        yield Label(
            "Interfaz Global:",
            classes="sidebar-label"
        )

        yield Select(
            [],
            id="global-iface-select",
            compact=True
        )

        yield Label("--- NAVEGACION ---", id="nav-divider")

        with Vertical(id="sidebar-list"):
            for item_id, label in NAV_ITEMS:
                yield Button(label, id=item_id, classes="nav-btn")

    def on_mount(self):
        self.refresh_interfaces()

    def refresh_interfaces(self):
        ifaces = network.get_interfaces_detailed()
        iface_select = self.query_one("#global-iface-select", Select)
        if ifaces:
            options = [
                (f"{d['iface']} ({d['state']})", d['iface'])
                for d in ifaces
            ]
            iface_select.set_options(options)
            if not getattr(self.app, 'selected_interface', None):
                first_iface = ifaces[0]['iface']
                self.app.selected_interface = first_iface
                iface_select.value = first_iface

    def on_select_changed(self, event: Select.Changed):
        if event.select.id == "global-iface-select":
          self.app.selected_interface = event.value
