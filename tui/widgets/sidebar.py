from textual.containers import Vertical
from textual.widgets import Label, Select, ListView, ListItem

import network


class Sidebar(Vertical):
  
    def compose(self):
        yield Label("AYANAMI", id="app-title")
        
        yield Label(
            "Interfaz Global:",
            classes="sidebar-label"
        )
        
        yield Select(
            [],
            id="global-iface-select",
            compact=True
        )
        
        yield ListView(
            ListItem(Label("Interfaces"), id="nav-interfaces"),
            ListItem(Label("Hotspot"), id="nav-hotspot"),
            ListItem(Label("Scanner"), id="nav-scanner"),
            ListItem(Label("Monitor"), id="nav-monitor"),
            ListItem(Label("Sniffer"), id="nav-sniffer"),
            ListItem(Label("Firewall"), id="nav-firewall"),
            id="sidebar-list"
        )
        
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