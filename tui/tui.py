from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Header, Footer, ListView, ContentSwitcher
from textual.binding import Binding

from widgets.sidebar import Sidebar

from views.interfaces import InterfacesView
from views.hostspot import HotspotView
from views.scanner import ScannerView
from views.monitor import MonitorView
from views.sniffer import SnifferView
from views.firewall import FirewallView
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

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item and event.item.id:
            self.query_one("#main-content", ContentSwitcher).current = event.item.id

    def action_refresh(self) -> None:
        current_view = self.query_one("#main-content", ContentSwitcher).current
        if current_view == "nav-interfaces":
            self.query_one(InterfacesView).refresh_data()
            self.query_one(Sidebar).refresh_interfaces()
        elif current_view == "nav-scanner":
            self.query_one(ScannerView).refresh_data()
        elif current_view == "nav-sniffer":
            self.query_one(SnifferView).refresh_devices()
        #elif current_view == "nav-firewall":
            

if __name__ == "__main__":
    app = AyanamiApp()
    app.run()
