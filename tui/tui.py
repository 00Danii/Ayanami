from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Header, Footer, Button, ContentSwitcher
from textual.binding import Binding

from widgets.sidebar import Sidebar

from views.interfaces import InterfacesView
from views.hostspot import HotspotView
from views.scanner import ScannerView
from views.monitor import MonitorView
from views.sniffer import SnifferView
from views.firewall import FirewallView


NAV_ORDER = ["nav-interfaces", "nav-hotspot", "nav-scanner", "nav-monitor", "nav-sniffer", "nav-firewall"]


class AyanamiApp(App):

    CSS_PATH = "styles/app.css"

    ENABLE_COMMAND_PALETTE = False

    capture_print = True

    selected_interface = None

    BINDINGS = [
        Binding("q", "quit", "Salir"),
        Binding("r", "refresh", "Actualizar Vista"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield Sidebar()
            with ContentSwitcher(initial="nav-interfaces", id="main-content"):
                yield InterfacesView(id="nav-interfaces")
                yield ScannerView(id="nav-scanner")
                yield SnifferView(id="nav-sniffer")
                yield HotspotView(id="nav-hotspot")
                yield MonitorView(id="nav-monitor")
                yield FirewallView(id="nav-firewall")
        yield Footer()

    def on_mount(self):
        self._activate_nav("nav-interfaces")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id in NAV_ORDER:
            self.query_one("#main-content", ContentSwitcher).current = btn_id
            self._activate_nav(btn_id)
            if btn_id == "nav-hotspot":
                self.query_one(HotspotView).refresh_data()

    def _activate_nav(self, item_id: str):
        for btn in self.query(".nav-btn"):
            btn.remove_class("nav-active")
        active = self.query_one("#sidebar-list").query_one(f"#{item_id}", Button)
        active.add_class("nav-active")

    def action_refresh(self) -> None:
        current_view = self.query_one("#main-content", ContentSwitcher).current
        if current_view == "nav-interfaces":
            self.query_one(InterfacesView).refresh_data()
            self.query_one(Sidebar).refresh_interfaces()
        elif current_view == "nav-scanner":
            self.query_one(ScannerView).refresh_data()
        elif current_view == "nav-sniffer":
            self.query_one(SnifferView).refresh_devices()
        elif current_view == "nav-hotspot":
            self.query_one(HotspotView).refresh_data()

if __name__ == "__main__":
    app = AyanamiApp()
    app.run()
