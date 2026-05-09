from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, Container, ScrollableContainer
from textual.widgets import Header, Footer, Static, ListView, ListItem, Label, ContentSwitcher, DataTable, Button, RichLog, Input, Select
from textual.screen import Screen
from textual.worker import Worker, WorkerState
from textual.binding import Binding
from textual.message import Message

import subprocess
import threading
from threading import Lock
import asyncio
import json
import os

# Importar módulos existentes (SIN MODIFICARLOS)
import network
import scanner
import gateway
import monitor_bw
import sniffer
import firewall
import firewall_apps

class Sidebar(Vertical):
    def compose(self) -> ComposeResult:
        yield Label("AYANAMI", id="app-title")
        yield Label("Interfaz Global:", classes="sidebar-label")
        yield Select([], id="global-iface-select", compact=True)
        yield ListView(
            ListItem(Label("Interfaces"), id="nav-interfaces"),
            ListItem(Label("Hotspot"), id="nav-hotspot"),
            ListItem(Label("Scanner"), id="nav-scanner"),
            ListItem(Label("Monitor"), id="nav-monitor"),
            ListItem(Label("Sniffer"), id="nav-sniffer"),
            ListItem(Label("Firewall"), id="nav-firewall"),
            id="sidebar-list"
        )

    def on_mount(self) -> None:
        self.refresh_interfaces()

    def refresh_interfaces(self) -> None:
        ifaces = network.get_interfaces_detailed()
        iface_select = self.query_one("#global-iface-select", Select)
        if ifaces:
            options = [(f"{d['iface']} ({d['state']})", d['iface']) for d in ifaces]
            iface_select.set_options(options)
            # Set first available interface as default if not set
            if not getattr(self.app, 'selected_interface', None):
                first_iface = ifaces[0]['iface']
                self.app.selected_interface = first_iface
                iface_select.value = first_iface
        else:
            iface_select.set_options([("No hay interfaces", "")])

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "global-iface-select":
            if event.value:
                self.app.selected_interface = event.value
                self.app.notify(f"Interfaz global: {event.value}")
            else:
                self.app.selected_interface = None
                self.app.notify("Interfaz deseleccionada", severity="warning")

class InterfacesView(Vertical):
    def compose(self) -> ComposeResult:
        yield Label("Gestión de Interfaces", classes="section-title")
        yield Label("Haz clic en una interfaz para seleccionarla como interfaz global", classes="help-text")
        yield DataTable(id="interfaces-table")
        yield Horizontal(
            Button("Actualizar", variant="primary", id="refresh-interfaces"),
            Button("Seleccionar como Global", variant="success", id="set-global-iface"),
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

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Set selected interface as global when row is selected"""
        table = self.query_one("#interfaces-table", DataTable)
        row_key = event.row_key
        iface = table.get_row(row_key)[0]
        self.app.selected_interface = iface
        self.app.notify(f"Interfaz global: {iface}")
        # Update sidebar selector
        try:
            sidebar = self.app.query_one(Sidebar)
            sidebar.query_one("#global-iface-select", Select).value = iface
        except:
            pass

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
        yield Label("Usa la interfaz global seleccionada en la barra lateral", classes="help-text")

        with Horizontal(classes="button-bar"):
            yield Label("Modo:")
            yield Button("Todo el tráfico", id="mode-all", classes="mode-btn")
            yield Button("Por dispositivo", id="mode-device", classes="mode-btn")
            yield Button("Modo RAW", id="mode-raw", classes="mode-btn")

        with Horizontal(id="device-selector", classes="button-bar"):
            yield Label("Dispositivo:")
            yield Select([], id="sniffer-device", compact=True)

        with Horizontal(classes="button-bar"):
            yield Button("Start", variant="success", id="start-sniffer")
            yield Button("Stop", variant="error", id="stop-sniffer")
            yield Button("Actualizar Dispositivos", variant="default", id="refresh-devices")

        yield RichLog(id="sniffer-log", highlight=True, markup=True)

    def on_mount(self) -> None:
        # Ocultar selector de dispositivo inicialmente
        self.query_one("#device-selector").display = False
        # Initialize mode
        self.current_mode = "all"
        # Set default mode button style
        self.query_one("#mode-all").variant = "primary"
        self.refresh_devices()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        # Handle mode buttons
        if event.button.id == "mode-all":
            self.current_mode = "all"
            self._update_mode_buttons("mode-all")
            event.stop()
        elif event.button.id == "mode-device":
            self.current_mode = "device"
            self._update_mode_buttons("mode-device")
            self.refresh_devices()
            event.stop()
        elif event.button.id == "mode-raw":
            self.current_mode = "raw"
            self._update_mode_buttons("mode-raw")
            event.stop()
        elif event.button.id == "refresh-devices":
            self.refresh_devices()
            event.stop()

    def _update_mode_buttons(self, active_id: str):
        """Update mode button styles"""
        for btn_id in ["mode-all", "mode-device", "mode-raw"]:
            btn = self.query_one(f"#{btn_id}", Button)
            if btn_id == active_id:
                btn.variant = "primary"
                # Show/hide device selector
                self.query_one("#device-selector").display = (btn_id == "mode-device")
            else:
                btn.variant = "default"

    def refresh_devices(self) -> None:
        try:
            devices = scanner.get_neighbors()
            device_select = self.query_one("#sniffer-device", Select)
            if devices:
                options = [(f"{d['ip']} ({d['mac']})", d['ip']) for d in devices]
                device_select.set_options(options)
                if options:
                    device_select.value = options[0][1]
            else:
                device_select.set_options([("No hay dispositivos", "")])
        except Exception as e:
            self.app.notify(f"Error al cargar dispositivos: {e}", severity="error")

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
        yield Label("Monitor de Ancho de Banda", classes="section-title")
        yield Label("Usa la interfaz global seleccionada en la barra lateral", classes="help-text")
        yield Label("Interfaz actual:", id="monitor-current-iface", classes="section-title")

        with Horizontal(classes="button-bar"):
            yield Button("Iniciar", variant="success", id="start-monitor")
            yield Button("Detener", variant="error", id="stop-monitor")

        yield DataTable(id="monitor-table")

    def on_mount(self) -> None:
        table = self.query_one("#monitor-table", DataTable)
        table.add_columns("IP", "↓ Descarga", "↑ Subida", "Paquetes", "Total")
        self.traffic_data = {}
        self.traffic_lock = Lock()
        self.monitor_worker = None
        self.update_timer = None
        # Check for interface periodically until found
        self._iface_check_timer = self.set_interval(2.0, self.refresh_data)
        self.refresh_data()

    def on_show(self) -> None:
        """Refresh when view becomes visible"""
        self.refresh_data()


    def refresh_data(self) -> None:
        label = self.query_one("#monitor-current-iface", Label)
        iface = getattr(self.app, 'selected_interface', None)
        if iface:
            label.update(f"Interfaz actual: {iface}")
        else:
            label.update("Interfaz actual: No seleccionada (Selecciona en barra lateral)")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start-monitor":
            self.start_monitoring()
        elif event.button.id == "stop-monitor":
            self.stop_monitoring()

    def start_monitoring(self) -> None:
        iface = self.app.selected_interface
        if not iface:
            self.app.notify("Selecciona una interfaz global en la barra lateral", severity="error")
            return

        self.traffic_data = {}

        # Start periodic table update (runs in main thread)
        self.update_timer = self.set_interval(1.0, self.update_table)

        # Start sniffing worker (runs in background thread)
        self.monitor_worker = self.run_worker(
            lambda: self.do_monitoring(iface),
            thread=True,
            name="monitor"
        )
        self.app.notify(f"Monitor iniciado en {iface}")

    def stop_monitoring(self) -> None:
        # Stop timer
        if self.update_timer:
            self.update_timer.stop()
            self.update_timer = None

        # Stop worker
        if self.monitor_worker:
            self.monitor_worker.cancel()

        table = self.query_one("#monitor-table", DataTable)
        table.clear()

        self.app.notify("Monitor detenido")

    def do_monitoring(self, iface: str):
        from scapy.all import AsyncSniffer, IP
        import time

        def packet_callback(pkt):
            try:
                if pkt.haslayer(IP):
                    src_ip = pkt[IP].src
                    dst_ip = pkt[IP].dst
                    pkt_len = len(pkt)

                    with self.traffic_lock:

                        # Upload
                        if src_ip not in self.traffic_data:
                            self.traffic_data[src_ip] = {
                                "download": 0,
                                "upload": 0,
                                "packets": 0
                            }

                        self.traffic_data[src_ip]["upload"] += pkt_len
                        self.traffic_data[src_ip]["packets"] += 1

                        # Download
                        if dst_ip not in self.traffic_data:
                            self.traffic_data[dst_ip] = {
                                "download": 0,
                                "upload": 0,
                                "packets": 0
                            }

                        self.traffic_data[dst_ip]["download"] += pkt_len
                        self.traffic_data[dst_ip]["packets"] += 1

            except Exception:
                pass

        try:
            sniffer = AsyncSniffer(
                iface=iface,
                prn=packet_callback,
                store=False
            )

            sniffer.start()

            while self.monitor_worker and not self.monitor_worker.is_cancelled:
                time.sleep(0.2)

            sniffer.stop()

        except Exception as e:
            self.call_from_thread(
                self.app.notify,
                f"Error en monitor: {e}",
                severity="error"
            )

    def update_table(self) -> None:
        """Update the table with current traffic data - called periodically from main thread"""
        if not self.traffic_data:
            return

        # Safely copy traffic data
        with self.traffic_lock:
            traffic_copy = {
                ip: {"download": data["download"], "upload": data["upload"], "packets": data["packets"]}
                for ip, data in self.traffic_data.items()
            }

        table = self.query_one("#monitor-table", DataTable)
        table.clear()

        # Sort by total traffic (download + upload)
        sorted_ips = sorted(
            traffic_copy.items(),
            key=lambda x: x[1]["download"] + x[1]["upload"],
            reverse=True
        )

        for ip, data in sorted_ips:
            download_kb = data["download"] / 1024
            upload_kb = data["upload"] / 1024
            total_kb = (data["download"] + data["upload"]) / 1024

            table.add_row(
                ip,
                f"{download_kb:.2f} KB",
                f"{upload_kb:.2f} KB",
                str(data["packets"]),
                f"{total_kb:.2f} KB"
            )

class FirewallView(Vertical):
    def compose(self) -> ComposeResult:
        yield Label("Gestión de Firewall (iptables)", classes="section-title")

        with Horizontal(classes="firewall-actions"):
            with Vertical():
                yield Label("Bloqueo Rápido de IP")
                yield Input(placeholder="IP destino a bloquear", id="fw-ip-input")
                yield Button("Bloquear IP (Global)", variant="error", id="btn-fw-block-global")
                yield Button("Bloquear Dispositivo", variant="error", id="btn-fw-block-device")

            with Vertical():
                yield Label("Bloqueo por Dispositivo")
                yield Input(placeholder="IP dispositivo origen", id="fw-src-ip")
                yield Input(placeholder="IP destino (opcional)", id="fw-dst-ip")
                yield Button("Bloquear IP para Dispositivo", variant="warning", id="btn-fw-block-device-ip")

            with Vertical():
                yield Label("Gestión de Reglas")
                yield Input(placeholder="Número de regla a eliminar", id="fw-rule-num")
                yield Button("Listar Reglas", id="btn-fw-list")
                yield Button("Eliminar Regla", variant="warning", id="btn-fw-delete-rule")
                yield Button("Limpiar Todo", variant="error", id="btn-fw-flush")

        with Horizontal(classes="firewall-actions"):
            with Vertical():
                yield Label("Apps Registradas")
                yield DataTable(id="fw-apps-table")
                with Horizontal():
                    yield Button("Bloquear App (Global)", id="btn-fw-app-block")
                    yield Button("Desbloquear App (Global)", id="btn-fw-app-unblock")
                with Horizontal():
                    yield Button("Bloquear App en Dispositivo", id="btn-fw-app-block-device")
                    yield Button("Desbloquear App en Disp.", id="btn-fw-app-unblock-device")
                with Horizontal():
                    yield Button("Registrar App", id="btn-fw-app-register")
                    yield Button("Modificar App", id="btn-fw-app-modify")
                    yield Button("Borrar App", id="btn-fw-app-delete")

        yield RichLog(id="fw-log", markup=True)

    def on_mount(self) -> None:
        table = self.query_one("#fw-apps-table", DataTable)
        table.add_columns("App", "IPs", "Estado Global", "Dispositivos Bloqueados")
        self.refresh_apps()
        self.app.action_fw_list()

    def refresh_apps(self) -> None:
        try:
            data = firewall_apps.load_data()
            table = self.query_one("#fw-apps-table", DataTable)
            table.clear()
            for name, info in data.items():
                status = "BLOQUEADA" if info.get("blocked") else "ACTIVA"
                ips = ", ".join(info.get("ips", [])) or "sin IPs"
                blocked_devs = ", ".join(info.get("blocked_devices", [])) or "ninguno"
                table.add_row(name, ips, status, blocked_devs)
        except Exception as e:
            self.app.notify(f"Error al cargar apps: {e}", severity="error")

class AyanamiApp(App):
    selected_interface = None

    def on_mount(self) -> None:
        # Initialize selected interface from available interfaces
        ifaces = network.get_interfaces()
        if ifaces:
            self.selected_interface = ifaces[0]
            self.notify(f"Interfaz global: {self.selected_interface}")
        else:
            self.selected_interface = ""
            self.notify("No se encontraron interfaces", severity="warning")

    def set_interface(self, iface: str) -> None:
        """Set the global interface and notify all views"""
        self.selected_interface = iface
        self.notify(f"Interfaz global: {iface}")

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

    .sidebar-label {
        padding: 1;
        color: #565f89;
        text-align: center;
    }

    Sidebar {
        width: 25;
        background: #16161e;
        border-right: solid #3b4261;
    }

    #sidebar-list {
        background: transparent;
    }

    #global-iface-select {
        margin: 1;
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
        margin-bottom: 1;
    }

    .help-text {
        color: #565f89;
        text-style: italic;
        margin-top: 1;
    }

    Button {
        margin-bottom: 1;
    }

    Select {
        margin-bottom: 1;
        width: 100%;
    }

    Label {
        margin-bottom: 1;
    }

    #device-selector {
        height: auto;
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
            self.query_one(Sidebar).refresh_interfaces()
        elif event.button.id == "disconnect-interface":
            self.action_disconnect_interface()
        elif event.button.id == "set-global-iface":
            self.action_set_global_iface()

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

        # Firewall - Quick blocks
        elif event.button.id == "btn-fw-block-global":
            self.action_fw_block_global()
        elif event.button.id == "btn-fw-block-device":
            self.action_fw_block_device()
        elif event.button.id == "btn-fw-block-device-ip":
            self.action_fw_block_device_ip()

        # Firewall - Rule management
        elif event.button.id == "btn-fw-list":
            self.action_fw_list()
        elif event.button.id == "btn-fw-delete-rule":
            self.action_fw_delete_rule()
        elif event.button.id == "btn-fw-flush":
            self.action_fw_flush()

        # Firewall - Apps
        elif event.button.id == "btn-fw-app-block":
            self.action_fw_app_block()
        elif event.button.id == "btn-fw-app-unblock":
            self.action_fw_app_unblock()
        elif event.button.id == "btn-fw-app-block-device":
            self.action_fw_app_block_device()
        elif event.button.id == "btn-fw-app-unblock-device":
            self.action_fw_app_unblock_device()
        elif event.button.id == "btn-fw-app-register":
            self.action_fw_app_register()
        elif event.button.id == "btn-fw-app-modify":
            self.action_fw_app_modify()
        elif event.button.id == "btn-fw-app-delete":
            self.action_fw_app_delete()

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
            self.query_one(Sidebar).refresh_interfaces()
        except:
            self.notify("Selecciona una interfaz en la tabla primero", severity="error")

    def action_set_global_iface(self) -> None:
        """Set selected interface in table as global interface"""
        table = self.query_one("#interfaces-table", DataTable)
        try:
            row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
            iface = table.get_row(row_key)[0]
            self.selected_interface = iface
            self.notify(f"Interfaz global: {iface}")
            # Update sidebar selector
            try:
                sidebar = self.query_one(Sidebar)
                sidebar.query_one("#global-iface-select", Select).value = iface
            except:
                pass
        except:
            self.notify("Selecciona una interfaz en la tabla primero", severity="error")

    def action_create_hotspot(self) -> None:
        ssid = self.query_one("#hotspot-ssid", Input).value
        pwd = self.query_one("#hotspot-password", Input).value
        log = self.query_one("#hotspot-log", RichLog)

        if not ssid or len(pwd) < 8:
            log.write("[red][!] SSID requerido y Password min 8 caracteres[/]")
            return

        iface = self.selected_interface
        if not iface:
            log.write("[red][!] Selecciona una interfaz global en la barra lateral[/]")
            return

        log.write(f"[orange][+] Creando hotspot {ssid} en {iface}...[/]")
        cmd = f"nmcli dev wifi hotspot ifname {iface} ssid {ssid} password {pwd}"
        try:
            subprocess.run(cmd, shell=True, check=True)
            log.write("[green][+] Hotspot creado correctamente[/]")
        except subprocess.CalledProcessError:
            log.write(f"[red][!] Error al crear hotspot. Verifica que {iface} sea una interfaz WiFi[/]")

    def action_show_hotspot_password(self) -> None:
        log = self.query_one("#hotspot-log", RichLog)
        res = subprocess.check_output("nmcli dev wifi show-password", shell=True).decode()
        log.write(f"[blue][+] Detalles:\n{res}[/]")

    # --- FIREWALL ACTIONS ---

    # Quick blocks
    def action_fw_block_global(self) -> None:
        ip = self.query_one("#fw-ip-input", Input).value.strip()
        if ip:
            firewall.block_global(ip)
            self.notify(f"IP {ip} bloqueada globalmente")
            self.action_fw_list()
        else:
            self.notify("Ingresa una IP válida", severity="error")

    def action_fw_block_device(self) -> None:
        try:
            devices = scanner.get_neighbors()
            if not devices:
                self.notify("No hay dispositivos detectados", severity="error")
                return

            # Show device selection in log
            log = self.query_one("#fw-log", RichLog)
            log.write("[yellow][+] Selecciona el número del dispositivo a bloquear:[/]")
            for i, d in enumerate(devices, 1):
                log.write(f"  [{i}] {d['ip']} ({d['mac']})")

            # For simplicity, we'll use a dialog-like approach via input
            # In a real TUI, you'd use a proper selection widget
            self.notify("Usa el CLI para bloqueo por selección o ingresa IP manualmente en el campo de IP destino")
        except Exception as e:
            self.notify(f"Error: {e}", severity="error")

    def action_fw_block_device_ip(self) -> None:
        src_ip = self.query_one("#fw-src-ip", Input).value.strip()
        dst_ip = self.query_one("#fw-dst-ip", Input).value.strip()

        if not src_ip:
            self.notify("Ingresa IP de origen (dispositivo)", severity="error")
            return

        if dst_ip:
            # Block specific destination for device
            firewall.block_ip_for_device(src_ip, dst_ip)
            self.notify(f"Bloqueado {dst_ip} para {src_ip}")
        else:
            # Block all traffic from device
            firewall.block_device(src_ip)
            self.notify(f"Dispositivo {src_ip} bloqueado completamente")

        self.action_fw_list()

    # Rule management
    def action_fw_list(self) -> None:
        log = self.query_one("#fw-log", RichLog)
        log.clear()
        try:
            res = subprocess.check_output("iptables -L FORWARD -n --line-numbers",
                                         shell=True, stderr=subprocess.STDOUT).decode()
            log.write(f"[orange][+] Reglas FORWARD actuales:[/]\n{res}")
        except subprocess.CalledProcessError as e:
            log.write(f"[red][!] Error: {e.output.decode()}[/]")

    def action_fw_delete_rule(self) -> None:
        rule_num = self.query_one("#fw-rule-num", Input).value.strip()
        if not rule_num:
            self.notify("Ingresa el número de regla a eliminar", severity="error")
            return
        try:
            subprocess.run(f"iptables -D FORWARD {rule_num}", shell=True, check=True)
            self.notify(f"Regla {rule_num} eliminada")
            self.action_fw_list()
        except subprocess.CalledProcessError as e:
            self.notify(f"Error al eliminar regla: {e}", severity="error")

    def action_fw_flush(self) -> None:
        firewall.flush_rules()
        self.notify("Todas las reglas FORWARD eliminadas")
        self.action_fw_list()

    # App management actions
    def _get_selected_app(self) -> str | None:
        """Get the selected app name from the apps table"""
        try:
            table = self.query_one("#fw-apps-table", DataTable)
            if table.cursor_row is not None:
                row_key = table.coordinate_to_cell_key((table.cursor_row, 0)).row_key
                return table.get_row(row_key)[0]
        except:
            pass
        return None

    def action_fw_app_block(self) -> None:
        app_name = self._get_selected_app()
        if not app_name:
            self.notify("Selecciona una app de la tabla", severity="error")
            return
        data = firewall_apps.load_data()
        if app_name in data:
            ips = data[app_name].get("ips", [])
            if ips:
                firewall.block_app_ips(ips)
                data[app_name]["blocked"] = True
                firewall_apps.save_data(data)
                self.notify(f"App '{app_name}' bloqueada globalmente")
            else:
                self.notify(f"La app '{app_name}' no tiene IPs registradas", severity="warning")
        self.query_one(FirewallView).refresh_apps()

    def action_fw_app_unblock(self) -> None:
        app_name = self._get_selected_app()
        if not app_name:
            self.notify("Selecciona una app de la tabla", severity="error")
            return
        data = firewall_apps.load_data()
        if app_name in data:
            ips = data[app_name].get("ips", [])
            if ips:
                firewall.unblock_app_ips(ips)
                data[app_name]["blocked"] = False
                firewall_apps.save_data(data)
                self.notify(f"App '{app_name}' desbloqueada globalmente")
            else:
                self.notify(f"La app '{app_name}' no tiene IPs registradas", severity="warning")
        self.query_one(FirewallView).refresh_apps()

    def action_fw_app_block_device(self) -> None:
        app_name = self._get_selected_app()
        if not app_name:
            self.notify("Selecciona una app de la tabla", severity="error")
            return
        data = firewall_apps.load_data()
        if app_name not in data:
            self.notify(f"App '{app_name}' no encontrada", severity="error")
            return
        ips = data[app_name].get("ips", [])
        if not ips:
            self.notify(f"La app '{app_name}' no tiene IPs registradas", severity="warning")
            return
        # Show available devices
        log = self.query_one("#fw-log", RichLog)
        log.write(f"[yellow][+] Selecciona dispositivo para bloquear '{app_name}':[/]")
        devices = scanner.get_neighbors()
        if not devices:
            self.notify("No hay dispositivos detectados", severity="error")
            return
        for i, d in enumerate(devices, 1):
            log.write(f"  [{i}] {d['ip']} ({d['mac']})")
        self.notify("Usa el CLI para seleccionar dispositivo específico")

    def action_fw_app_unblock_device(self) -> None:
        app_name = self._get_selected_app()
        if not app_name:
            self.notify("Selecciona una app de la tabla", severity="error")
            return
        data = firewall_apps.load_data()
        if app_name not in data:
            self.notify(f"App '{app_name}' no encontrada", severity="error")
            return
        blocked_devs = data[app_name].get("blocked_devices", [])
        if not blocked_devs:
            self.notify(f"La app '{app_name}' no tiene dispositivos bloqueados", severity="warning")
            return
        log = self.query_one("#fw-log", RichLog)
        log.write(f"[yellow][+] Dispositivos bloqueados para '{app_name}':[/]")
        for i, dev in enumerate(blocked_devs, 1):
            log.write(f"  [{i}] {dev}")
        self.notify("Usa el CLI para desbloquear dispositivo específico")

    def action_fw_app_register(self) -> None:
        log = self.query_one("#fw-log", RichLog)
        log.write("[yellow][+] Para registrar una app, usa el CLI: python ayanami.py[/]")
        log.write("[yellow]O edita manualmente firewall_apps.json[/]")

    def action_fw_app_modify(self) -> None:
        app_name = self._get_selected_app()
        if not app_name:
            self.notify("Selecciona una app de la tabla", severity="error")
            return
        data = firewall_apps.load_data()
        self.notify(f"Usa el CLI para modificar '{app_name}'")
        firewall_apps.modify_app(data)
        self.query_one(FirewallView).refresh_apps()

    def action_fw_app_delete(self) -> None:
        app_name = self._get_selected_app()
        if not app_name:
            self.notify("Selecciona una app de la tabla", severity="error")
            return
        data = firewall_apps.load_data()
        if app_name in data:
            del data[app_name]
            firewall_apps.save_data(data)
            self.notify(f"App '{app_name}' eliminada")
            self.query_one(FirewallView).refresh_apps()

    # --- SNIFFER LOGIC ---
    def start_sniffing(self) -> None:
        iface = self.app.selected_interface
        mode = self.current_mode
        log = self.query_one("#sniffer-log", RichLog)

        if not iface:
            self.notify("Selecciona una interfaz global en la barra lateral", severity="error")
            return

        log.write(f"[bold orange][+] Iniciando sniffer en {iface} (modo: {mode})...[/]")

        self.sniff_worker = self.run_worker(
            self.do_sniffing(iface, mode),
            thread=True,
            name="sniffer"
        )

    async def do_sniffing(self, iface: str, mode: str):
        from scapy.all import sniff, IP, TCP, UDP, DNSQR

        if mode == "raw":
            # Modo RAW - mostrar paquete completo
            def packet_callback(pkt):
                self.call_from_thread(self.append_log, pkt.summary())
                self.call_from_thread(self.append_log, str(pkt.show(dump=True)))
        elif mode == "device":
            # Sniffing por dispositivo específico
            target = self.query_one("#sniffer-device", Select).value
            if not target:
                self.call_from_thread(self.append_log, "[red][!] No hay dispositivo seleccionado[/]")
                return

            def packet_callback(pkt):
                if pkt.haslayer(IP):
                    self.call_from_thread(self.append_log,
                        f"[cyan]{pkt.summary()}[/] | {pkt[IP].src} → {pkt[IP].dst}")
                    if pkt.haslayer(TCP):
                        self.call_from_thread(self.append_log, f"  TCP: {pkt[TCP].sport} → {pkt[TCP].dport}")
                    elif pkt.haslayer(UDP):
                        self.call_from_thread(self.append_log, f"  UDP: {pkt[UDP].sport} → {pkt[UDP].dport}")
                    if pkt.haslayer(DNSQR):
                        self.call_from_thread(self.append_log, f"  DNS: {pkt[DNSQR].qname.decode()}")

            sniff(iface=iface, filter=f"host {target}", prn=packet_callback, store=0,
                  stop_filter=lambda x: self.sniff_worker.is_cancelled)
            return
        else:
            # Modo ALL - todo el tráfico
            def packet_callback(pkt):
                if pkt.haslayer(IP):
                    self.call_from_thread(self.append_log,
                        f"[green]{pkt.summary()}[/] | {pkt[IP].src} → {pkt[IP].dst}")
                    if pkt.haslayer(TCP):
                        self.call_from_thread(self.append_log, f"  TCP: {pkt[TCP].sport} → {pkt[TCP].dport}")
                    elif pkt.haslayer(UDP):
                        self.call_from_thread(self.append_log, f"  UDP: {pkt[UDP].sport} → {pkt[UDP].dport}")
                    if pkt.haslayer(DNSQR):
                        self.call_from_thread(self.append_log, f"  DNS: {pkt[DNSQR].qname.decode()}")

        # Ejecutar sniff en hilo aparte
        sniff(iface=iface, prn=packet_callback, store=0,
              stop_filter=lambda x: self.sniff_worker.is_cancelled)

    def append_log(self, text: str) -> None:
        try:
            self.query_one("#sniffer-log", RichLog).write(text)
        except:
            pass

    def stop_sniffing(self) -> None:
        if hasattr(self, "sniff_worker"):
            self.sniff_worker.cancel()
            try:
                self.query_one("#sniffer-log", RichLog).write("[bold red][!] Sniffer detenido.[/]")
            except:
                pass

    def action_refresh(self) -> None:
        current_view = self.query_one("#main-content", ContentSwitcher).current
        if current_view == "nav-interfaces":
            self.query_one(InterfacesView).refresh_data()
            self.query_one(Sidebar).refresh_interfaces()
        elif current_view == "nav-scanner":
            self.query_one(ScannerView).refresh_data()
        elif current_view == "nav-sniffer":
            self.query_one(SnifferView).refresh_devices()
        elif current_view == "nav-firewall":
            self.query_one(FirewallView).refresh_apps()
            self.action_fw_list()

if __name__ == "__main__":
    app = AyanamiApp()
    app.run()
