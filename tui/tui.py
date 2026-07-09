from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Header, Footer, ListView, ContentSwitcher, RichLog, Select
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
            fw = self.query_one(FirewallView)
            fw.refresh_apps()
            fw.fw_list()

if __name__ == "__main__":
    app = AyanamiApp()
    app.run()
