from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, Container
from textual.widgets import Header, Footer, Static, ListView, ListItem, Label, ContentSwitcher, DataTable, Button, RichLog, Input
from textual.screen import Screen
from textual.worker import Worker, WorkerState
from textual.binding import Binding

import subprocess
import threading
import asyncio

# Importar módulos existentes (SIN MODIFICARLOS)
import network
import scanner
import gateway
import monitor_bw
import sniffer
import firewall

class Sidebar(Vertical):
    def compose(self) -> ComposeResult:
        yield Label("AYANAMI", id="app-title")
        yield ListView(
            ListItem(Label("Interfaces"), id="nav-interfaces"),
            ListItem(Label("Hotspot"), id="nav-hotspot"),
            ListItem(Label("Scanner"), id="nav-scanner"),
            ListItem(Label("Monitor"), id="nav-monitor"),
            ListItem(Label("Sniffer"), id="nav-sniffer"),
            ListItem(Label("Firewall"), id="nav-firewall"),
            id="sidebar-list"
        )

class InterfacesView(Vertical):
    def compose(self) -> ComposeResult:
        yield Label("Gestión de Interfaces", classes="section-title")
        yield DataTable(id="interfaces-table")
        yield Horizontal(
            Button("Actualizar", variant="primary", id="refresh-interfaces"),
            Button("Desconectar Seleccionada", variant="error", id="disconnect-interface"),
            classes="button-bar"
        )

    def on_mount(self) -> None:
        table = self.query_one("#interfaces-table", DataTable)
        table.add_columns("Interface", "Type", "State", "Connection")
        self.refresh_data()

    def refresh_data(self) -> None:
        table = self.query_one("#interfaces-table", DataTable)
        table.clear()
        # Usar función existente
        interfaces = network.get_interfaces_detailed()
        for iface in interfaces:
            table.add_row(
                iface["iface"],
                iface["type"],
                iface["state"],
                iface["connection"]
            )

class ScannerView(Vertical):
    def compose(self) -> ComposeResult:
        yield Label("Dispositivos en la Red", classes="section-title")
        yield DataTable(id="scanner-table")
        yield Horizontal(
            Button("Escanear", variant="primary", id="refresh-scanner"),
            classes="button-bar"
        )

    def on_mount(self) -> None:
        table = self.query_one("#scanner-table", DataTable)
        table.add_columns("IP", "MAC", "Interface")
        self.refresh_data()

    def refresh_data(self) -> None:
        table = self.query_one("#scanner-table", DataTable)
        table.clear()
        # Usar función existente
        neighbors = scanner.get_neighbors()
        for n in neighbors:
            table.add_row(n["ip"], n["mac"], n["iface"])

class SnifferView(Vertical):
    def compose(self) -> ComposeResult:
        yield Label("Sniffer de Paquetes", classes="section-title")
        yield Label("Selecciona interfaz y presiona Start")
        yield Horizontal(
            Input(placeholder="Interfaz (ej: wlan0)", id="sniffer-iface"),
            Button("Start", variant="success", id="start-sniffer"),
            Button("Stop", variant="error", id="stop-sniffer"),
            classes="button-bar"
        )
        yield RichLog(id="sniffer-log", highlight=True, markup=True)

    def on_mount(self) -> None:
        # Intentar pre-cargar interfaz por defecto
        ifaces = network.get_interfaces()
        if ifaces:
            self.query_one("#sniffer-iface", Input).value = ifaces[0]

class HotspotView(Vertical):
    def compose(self) -> ComposeResult:
        yield Label("Crear Hotspot", classes="section-title")
        yield Label("SSID:")
        yield Input(placeholder="Nombre de la red", id="hotspot-ssid")
        yield Label("Password:")
        yield Input(placeholder="Mínimo 8 caracteres", id="hotspot-password", password=True)
        yield Button("Crear Hotspot", variant="success", id="btn-create-hotspot")
        yield Button("Ver Contraseña", variant="default", id="btn-show-password")
        yield RichLog(id="hotspot-log")

class MonitorView(Vertical):
    def compose(self) -> ComposeResult:
        yield Label("Monitor de Ancho de Banda (iftop)", classes="section-title")
        yield Label("Selecciona una interfaz para monitorear:")
        yield DataTable(id="monitor-iface-table")
        yield Button("Lanzar iftop", variant="primary", id="btn-launch-iftop")
        yield Label("(Presiona 'q' para salir de iftop y volver al TUI)", classes="help-text")

    def on_mount(self) -> None:
        table = self.query_one("#monitor-iface-table", DataTable)
        table.add_columns("Interface", "State")
        self.refresh_data()

    def refresh_data(self) -> None:
        table = self.query_one("#monitor-iface-table", DataTable)
        table.clear()
        ifaces = network.get_interfaces_detailed()
        for i in ifaces:
            table.add_row(i["iface"], i["state"])

class FirewallView(Vertical):
    def compose(self) -> ComposeResult:
        yield Label("Gestión de Firewall (iptables)", classes="section-title")
        with Horizontal(classes="firewall-actions"):
            with Vertical():
                yield Label("Bloqueos Rápidos")
                yield Input(placeholder="IP a bloquear", id="fw-ip-input")
                yield Button("Bloquear IP (Global)", variant="error", id="btn-fw-block")
            with Vertical():
                yield Label("Reglas")
                yield Button("Listar Reglas", id="btn-fw-list")
                yield Button("Limpiar Todo", variant="warning", id="btn-fw-flush")
        yield Label("Apps Registradas", classes="section-title")
        yield DataTable(id="fw-apps-table")
        yield RichLog(id="fw-log", markup=True)

    def on_mount(self) -> None:
        table = self.query_one("#fw-apps-table", DataTable)
        table.add_columns("App", "IPs", "Estado")
        self.refresh_apps()

    def refresh_apps(self) -> None:
        try:
            import firewall_apps
            data = firewall_apps.load_data()
            table = self.query_one("#fw-apps-table", DataTable)
            table.clear()
            for name, info in data.items():
                status = "BLOQUEADA" if info.get("blocked") else "ACTIVA"
                ips = ", ".join(info.get("ips", []))
                table.add_row(name, ips, status)
        except:
            pass

class AyanamiApp(App):
    CSS = """
    Screen {
        background: #1a1b26;
    }

    #app-title {
        text-align: center;
        width: 100%;
        padding: 1;
        background: #ff007c;
        color: white;
        text-style: bold;
    }

    Sidebar {
        width: 25;
        background: #16161e;
        border-right: solid #3b4261;
    }

    #sidebar-list {
        background: transparent;
    }

    .section-title {
        text-style: bold;
        padding: 1;
        background: #24283b;
        width: 100%;
        margin-bottom: 1;
    }

    DataTable {
        height: 1fr;
        border: solid #3b4261;
    }

    .button-bar {
        height: auto;
        padding: 1;
        align: center middle;
        
    }

    RichLog {
        background: #1a1b26;
        border: solid #3b4261;
        height: 1fr;
        margin-top: 1;
    }

    Input {
        width: 100%;
        margin-bottom: 1;
    }

    .firewall-actions {
        height: auto;
        
        padding: 1;
    }

    .help-text {
        color: #565f89;
        text-style: italic;
        margin-top: 1;
    }

    Button {
        margin-bottom: 1;
    }
    """

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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        # Interfaces
        if event.button.id == "refresh-interfaces":
            self.query_one(InterfacesView).refresh_data()
        elif event.button.id == "disconnect-interface":
            self.action_disconnect_interface()

        # Scanner
        elif event.button.id == "refresh-scanner":
            self.query_one(ScannerView).refresh_data()

        # Sniffer
        elif event.button.id == "start-sniffer":
            self.start_sniffing()
        elif event.button.id == "stop-sniffer":
            self.stop_sniffing()

        # Hotspot
        elif event.button.id == "btn-create-hotspot":
            self.action_create_hotspot()
        elif event.button.id == "btn-show-password":
            self.action_show_hotspot_password()

        # Monitor
        elif event.button.id == "btn-launch-iftop":
            self.action_launch_iftop()

        # Firewall
        elif event.button.id == "btn-fw-block":
            self.action_fw_block()
        elif event.button.id == "btn-fw-list":
            self.action_fw_list()
        elif event.button.id == "btn-fw-flush":
            self.action_fw_flush()

    # --- ACTIONS ---

    def action_disconnect_interface(self) -> None:
        table = self.query_one("#interfaces-table", DataTable)
        try:
            row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
            iface = table.get_row(row_key)[0]
            # Usar comando de network.py pero directo para evitar input()
            subprocess.run(f"nmcli device disconnect {iface}", shell=True)
            self.notify(f"Interfaz {iface} desconectada")
            self.query_one(InterfacesView).refresh_data()
        except:
            self.notify("Selecciona una interfaz en la tabla primero", severity="error")

    def action_create_hotspot(self) -> None:
        ssid = self.query_one("#hotspot-ssid", Input).value
        pwd = self.query_one("#hotspot-password", Input).value
        log = self.query_one("#hotspot-log", RichLog)
        
        if not ssid or len(pwd) < 8:
            log.write("[red][!] SSID requerido y Password min 8 caracteres[/]")
            return

        log.write(f"[orange][+] Creando hotspot {ssid}...[/]")
        # Llamar a comando nmcli (como en gateway.py)
        # Nota: Normalmente se necesita una interfaz wifi. 
        # Aquí simplificamos usando la primera disponible o asumiendo que el usuario sabe.
        ifaces = network.get_interfaces()
        if ifaces:
            cmd = f"nmcli dev wifi hotspot ifname {ifaces[0]} ssid {ssid} password {pwd}"
            subprocess.run(cmd, shell=True)
            log.write("[green][+] Hotspot creado correctamente[/]")
        else:
            log.write("[red][!] No se encontró interfaz WiFi[/]")

    def action_show_hotspot_password(self) -> None:
        log = self.query_one("#hotspot-log", RichLog)
        res = subprocess.check_output("nmcli dev wifi show-password", shell=True).decode()
        log.write(f"[blue][+] Detalles:\n{res}[/]")

    async def action_launch_iftop(self) -> None:
        table = self.query_one("#monitor-iface-table", DataTable)
        try:
            row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
            iface = table.get_row(row_key)[0]
            
            self.app.suspend_stdio()
            subprocess.run(f"iftop -i {iface}", shell=True)
            # Al volver de iftop, se restaura el TUI automáticamente
        except:
            self.notify("Selecciona una interfaz en la tabla", severity="error")

    def action_fw_block(self) -> None:
        ip = self.query_one("#fw-ip-input", Input).value
        if ip:
            firewall.block_global(ip) # Función existente
            self.notify(f"IP {ip} bloqueada")
            self.action_fw_list()

    def action_fw_list(self) -> None:
        log = self.query_one("#fw-log", RichLog)
        log.clear()
        res = subprocess.check_output("iptables -L FORWARD -n --line-numbers", shell=True).decode()
        log.write(f"[orange][+] Reglas actuales:\n{res}[/]")

    def action_fw_flush(self) -> None:
        firewall.flush_rules() # Función existente
        self.notify("Reglas eliminadas")
        self.action_fw_list()

    # --- SNIFFER LOGIC ---
    def start_sniffing(self) -> None:
        iface = self.query_one("#sniffer-iface", Input).value
        log = self.query_one("#sniffer-log", RichLog)
        log.write(f"[bold orange][+] Iniciando sniffer en {iface}...[/]")
        
        self.sniff_worker = self.run_worker(
            self.do_sniffing(iface),
            thread=True,
            name="sniffer"
        )

    async def do_sniffing(self, iface: str):
        from scapy.all import sniff, IP, TCP, UDP
        
        def packet_callback(pkt):
            summary = pkt.summary()
            # Simplificamos para el log del TUI
            self.call_from_thread(self.append_log, summary)

        # Ejecutar sniff en hilo aparte (ya estamos en un worker thread)
        sniff(iface=iface, prn=packet_callback, store=0, stop_filter=lambda x: self.sniff_worker.is_cancelled)

    def append_log(self, text: str) -> None:
        self.query_one("#sniffer-log", RichLog).write(text)

    def stop_sniffing(self) -> None:
        if hasattr(self, "sniff_worker"):
            self.sniff_worker.cancel()
            self.query_one("#sniffer-log", RichLog).write("[bold red][!] Sniffer detenido.[/]")

    def action_refresh(self) -> None:
        current_view = self.query_one("#main-content", ContentSwitcher).current
        if current_view == "nav-interfaces":
            self.query_one(InterfacesView).refresh_data()
        elif current_view == "nav-scanner":
            self.query_one(ScannerView).refresh_data()

if __name__ == "__main__":
    app = AyanamiApp()
    app.run()
