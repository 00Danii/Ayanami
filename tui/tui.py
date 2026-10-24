import importlib

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Header, Footer, Button, ContentSwitcher
from textual.binding import Binding
from textual.css.query import NoMatches

from widgets.sidebar import Sidebar

from views.interfaces import InterfacesView
from views.sistema import SistemaView


NAV_ORDER = ["nav-sistema", "nav-firewall", "nav-backups", "nav-dhcp", "nav-scanner", "nav-monitor", "nav-sniffer", "nav-interfaces", "nav-hotspot"]

# Las vistas se importan al abrirlas por primera vez. Monitor y Sniffer
# importan scapy, que tarda ~1 s y no hace falta para el arranque.
VIEW_IMPORTS = {
    "nav-interfaces": ("views.interfaces", "InterfacesView"),
    "nav-hotspot": ("views.hotspot", "HotspotView"),
    "nav-scanner": ("views.scanner", "ScannerView"),
    "nav-monitor": ("views.monitor", "MonitorView"),
    "nav-sniffer": ("views.sniffer", "SnifferView"),
    "nav-firewall": ("views.firewall", "FirewallView"),
    "nav-dhcp": ("views.dhcp", "DhcpView"),
    "nav-backups": ("views.backups", "BackupsView"),
    "nav-sistema": ("views.sistema", "SistemaView"),
}


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
            with ContentSwitcher(initial="nav-sistema", id="main-content"):
                # Solo la vista inicial se monta al arrancar. El resto se
                # crea bajo demanda en _show_view().
                yield SistemaView(id="nav-sistema")
        yield Footer()

    def on_mount(self):
        self._activate_nav("nav-sistema")
        self.set_interval(1.0, self._auto_refresh_sistema)

    def _auto_refresh_sistema(self):
        current = self.query_one("#main-content", ContentSwitcher).current
        if current == "nav-sistema":
            self.query_one("#nav-sistema").refresh_data()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id in NAV_ORDER:
            await self._show_view(btn_id)
            self._activate_nav(btn_id)
            if btn_id == "nav-hotspot":
                self.query_one("#nav-hotspot").refresh_data()
            if btn_id == "nav-sistema":
                # Sistema lee muchos datos del sistema: se pinta al abrirlo,
                # no al arrancar (el intervalo de refresco lo mantiene vivo).
                self.query_one("#nav-sistema").refresh_data()
            if btn_id == "nav-firewall":
                # La lista de Apps se dibuja al abrir el Firewall, no al arrancar.
                self.query_one("#nav-firewall").ensure_apps_loaded()
            if btn_id == "nav-dhcp":
                self.query_one("#nav-dhcp").refresh_data()
            if btn_id == "nav-backups":
                self.query_one("#nav-backups").refresh_data()

    async def _show_view(self, item_id: str) -> None:
        """Monta e importa una vista solo la primera vez que se abre."""
        content = self.query_one("#main-content", ContentSwitcher)

        try:
            content.get_child_by_id(item_id)
        except NoMatches:
            module_name, class_name = VIEW_IMPORTS[item_id]
            module = importlib.import_module(module_name)
            view_class = getattr(module, class_name)
            await content.add_content(view_class(id=item_id), set_current=True)
        else:
            content.current = item_id

    def _activate_nav(self, item_id: str):
        for btn in self.query(".nav-btn"):
            btn.remove_class("nav-active")
        active = self.query_one("#sidebar-list").query_one(f"#{item_id}", Button)
        active.add_class("nav-active")

    def action_refresh(self) -> None:
        current_view = self.query_one("#main-content", ContentSwitcher).current
        if current_view == "nav-interfaces":
            self.query_one("#nav-interfaces").refresh_data()
            self.query_one(Sidebar).refresh_interfaces()
        elif current_view == "nav-scanner":
            self.query_one("#nav-scanner").refresh_data()
        elif current_view == "nav-sniffer":
            self.query_one("#nav-sniffer").refresh_devices()
        elif current_view == "nav-hotspot":
            self.query_one("#nav-hotspot").refresh_data()
        elif current_view == "nav-dhcp":
            self.query_one("#nav-dhcp").refresh_data()
        elif current_view == "nav-backups":
            self.query_one("#nav-backups").refresh_data()
        elif current_view == "nav-sistema":
            self.query_one("#nav-sistema").refresh_data()

if __name__ == "__main__":
    app = AyanamiApp()
    app.run()
