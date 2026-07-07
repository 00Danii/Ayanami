from datetime import datetime

from textual.app import ComposeResult
from textual.containers import (
    Vertical,
    Horizontal,
)
from textual.widgets import (
    Label,
    Button,
    Static,
    Select,
)
from scapy.all import (
    AsyncSniffer,
    IP,
    TCP,
    UDP,
    DNSQR,
    DNSRR,
)
import scanner


SERVICE_MAP = {

    80: "HTTP",
    443: "HTTPS",
    53: "DNS",
    22: "SSH",
    21: "FTP",
    25: "SMTP",
    110: "POP3",
    143: "IMAP",
    123: "NTP",
    8080: "HTTP-ALT",
    3306: "MYSQL",
    27017: "MONGO"
}


class SnifferView(Vertical):

    # ==========================================================
    # UI
    # ==========================================================

    def compose(self) -> ComposeResult:

        yield Horizontal(

            Label(
                "Monitor de Paquetes",
                classes="sniffer-title"
            ),

            Static(
                "[red]DETENIDO[/]",
                id="sniffer-status"
            ),

            classes="sniffer-header"
        )

        yield Horizontal(

            Horizontal(

                Select(
                    [("Toda la red", "ALL")],
                    value="ALL",
                    id="sniffer-host-select"
                ),

                Button(
                    "\u21bb",
                    id="refresh-devices",
                    variant="primary"
                ),

                classes="sniffer-left"
            ),

            Static(
                "",
                classes="sniffer-spacer"
            ),

            Horizontal(

                Button(
                    "INICIAR",
                    variant="success",
                    id="start-sniffer"
                ),

                Button(
                    "PAUSAR",
                    variant="warning",
                    id="pause-sniffer"
                ),

                Button(
                    "DETENER",
                    variant="error",
                    id="stop-sniffer"
                ),

                classes="sniffer-right"
            ),

            classes="sniffer-toolbar"
        )

        yield Horizontal(

            Static(
                "Paquetes: 0",
                id="sniffer-packets",
                classes="sniffer-stat"
            ),

            Static(
                "TCP: 0",
                id="sniffer-tcp",
                classes="sniffer-stat"
            ),

            Static(
                "UDP: 0",
                id="sniffer-udp",
                classes="sniffer-stat"
            ),

            Static(
                "DNS: 0",
                id="sniffer-dns",
                classes="sniffer-stat"
            ),

            Static(
                "Interfaz: --",
                id="sniffer-iface",
                classes="sniffer-stat"
            ),

            classes="sniffer-stats"
        )

        yield Static(
            "[dim]Esperando captura...[/]",
            id="sniffer-last-packet",
            classes="sniffer-last-packet"
        )

        yield Static(
            "",
            id="sniffer-packet-detail",
            classes="sniffer-packet-detail"
        )

    # ==========================================================
    # MOUNT
    # ==========================================================

    def on_mount(self):

        self.packet_count = 0
        self.tcp_count = 0
        self.udp_count = 0
        self.dns_count = 0
        self.paused = False
        self.sniffer = None
        self.last_pkt_info = ""
        self.last_pkt_detail = ""
        self.ui_timer = None

        self.refresh_devices()
        self.tick()

    # ==========================================================
    # BUTTONS
    # ==========================================================

    def on_button_pressed(self, event):

        bid = event.button.id

        if bid == "refresh-devices":
            self.refresh_devices()
        elif bid == "start-sniffer":
            self.start_sniffer()
        elif bid == "pause-sniffer":
            self.toggle_pause()
        elif bid == "stop-sniffer":
            self.stop_sniffer()

    # ==========================================================
    # DEVICES
    # ==========================================================

    def refresh_devices(self):

        try:
            select = self.query_one(
                "#sniffer-host-select", Select
            )

            devices = scanner.get_neighbors_simple()

            seen = set()

            options = [
                ("Toda la red", "ALL")
            ]

            for device in devices:

                ip = device["ip"]

                if ip in seen:
                    continue

                seen.add(ip)

                mac = device.get("mac", "??")
                label = f"{ip} ({mac})"

                options.append((label, ip))

            select.set_options(options)
            select.value = "ALL"

        except Exception as e:
            self.notify(str(e), severity="error")

    # ==========================================================
    # START
    # ==========================================================

    def start_sniffer(self):

        if self.sniffer:
            self.notify("Ya activo", severity="warning")
            return

        iface = getattr(self.app, "selected_interface", None)
        if not iface:
            self.notify("Selecciona una interfaz", severity="error")
            return

        device = self.query_one("#sniffer-host-select", Select).value
        bpf_filter = None

        if device != "ALL":
            bpf_filter = f"host {device}"

        self.paused = False
        self.packet_count = 0
        self.tcp_count = 0
        self.udp_count = 0
        self.dns_count = 0
        self.last_pkt_info = ""

        self.sniffer = AsyncSniffer(
            iface=iface,
            prn=self.process_packet,
            store=False,
            filter=bpf_filter
        )
        self.sniffer.start()

        self.ui_timer = self.set_interval(1.0, self.tick)

        self.query_one("#sniffer-status", Static).update(
            "[green]CAPTURANDO[/]"
        )

        self.notify(f"Capturando en {iface}")

    # ==========================================================
    # PAUSE / RESUME
    # ==========================================================

    def toggle_pause(self):

        if not self.sniffer:
            return

        self.paused = not self.paused
        btn = self.query_one("#pause-sniffer", Button)

        if self.paused:
            btn.label = "CONTINUAR"
            status = "[yellow]PAUSADO[/]"
            if self.ui_timer:
                self.ui_timer.pause()
        else:
            btn.label = "PAUSAR"
            status = "[green]CAPTURANDO[/]"
            if self.ui_timer:
                self.ui_timer.resume()

        self.query_one("#sniffer-status", Static).update(status)

    # ==========================================================
    # STOP
    # ==========================================================

    def stop_sniffer(self):

        self.paused = False

        if self.ui_timer:
            self.ui_timer.stop()
            self.ui_timer = None

        if self.sniffer:
            try:
                if getattr(self.sniffer, "running", False):
                    self.sniffer.stop()
            except Exception:
                pass
            self.sniffer = None

        self.query_one("#sniffer-status", Static).update(
            "[red]DETENIDO[/]"
        )
        self.query_one("#pause-sniffer", Button).label = "PAUSAR"
        self.query_one("#sniffer-last-packet", Static).update(
            "[dim]Esperando captura...[/]"
        )
        self.query_one("#sniffer-packet-detail", Static).update(
            ""
        )

        self.notify("Captura detenida")

    # ==========================================================
    # PROCESS PACKET (sniffer thread)
    # ==========================================================

    def process_packet(self, pkt):

        if self.paused:
            return

        if not pkt.haslayer(IP):
            return

        try:
            src = pkt[IP].src
            dst = pkt[IP].dst
            proto = "IP"
            service = "UNKNOWN"
            info = ""
            length = len(pkt)

            if pkt.haslayer(TCP):
                proto = "TCP"
                sport = pkt[TCP].sport
                dport = pkt[TCP].dport
                service = SERVICE_MAP.get(dport, "TCP")
                info = f"{sport}->{dport} F={pkt[TCP].flags}"
                self.tcp_count += 1

            elif pkt.haslayer(UDP):
                proto = "UDP"
                sport = pkt[UDP].sport
                dport = pkt[UDP].dport
                service = SERVICE_MAP.get(dport, "UDP")
                info = f"{sport}->{dport}"
                self.udp_count += 1

            self.packet_count += 1

            ts = datetime.now().strftime("%H:%M:%S")

            self.last_pkt_info = (
                f"{ts} {src} > {dst} "
                f"{proto}/{service} "
                f"{info} "
                f"[{length}B]"
            )

            lines = [
                f"[bold #7aa2f7]ULTIMO PAQUETE[/]    "
                f"[#565f89]{ts}[/]",
                "",
                f"  [#9ece6a]{src}[/] \u2192 [#f7768e]{dst}[/]",
                f"  Proto: [#e0af68]{proto}[/]  "
                f"Service: [#bb9af7]{service}[/]  "
                f"Len: [#7dcfff]{length}[/]",
            ]

            if pkt.haslayer(TCP):
                lines.append(
                    f"  TCP: {pkt[TCP].sport} \u2192 {pkt[TCP].dport}  "
                    f"Flags: {pkt[TCP].flags}  "
                    f"Seq: {pkt[TCP].seq}"
                )

            if pkt.haslayer(UDP):
                lines.append(
                    f"  UDP: {pkt[UDP].sport} \u2192 {pkt[UDP].dport}"
                )

            if pkt.haslayer(DNSQR):
                qname = pkt[DNSQR].qname.decode()
                lines.append(
                    f"  DNS Query: {qname[:80]}"
                )
                self.dns_count += 1

            if pkt.haslayer(DNSRR):
                for i, rr in enumerate(pkt[DNSRR][:3]):
                    try:
                        lines.append(
                            f"  DNS Answer: "
                            f"{rr.rdata.decode()[:60]}"
                        )
                    except Exception:
                        pass

            self.last_pkt_detail = "\n".join(lines)
        except Exception:
            pass

    # ==========================================================
    # TICK (UI thread, 1 vez por segundo)
    # ==========================================================

    def tick(self):

        lp = self.query_one("#sniffer-last-packet", Static)

        if self.last_pkt_info:
            lp.update(self.last_pkt_info)
        else:
            lp.update("[dim]Esperando paquetes...[/]")

        detail = self.query_one("#sniffer-packet-detail", Static)
        detail.update(self.last_pkt_detail or "[dim]---[/]")

        iface = getattr(self.app, "selected_interface", "--")

        self.query_one("#sniffer-packets", Static).update(
            f"Paquetes: {self.packet_count}"
        )
        self.query_one("#sniffer-tcp", Static).update(
            f"TCP: {self.tcp_count}"
        )
        self.query_one("#sniffer-udp", Static).update(
            f"UDP: {self.udp_count}"
        )
        self.query_one("#sniffer-dns", Static).update(
            f"DNS: {self.dns_count}"
        )
        self.query_one("#sniffer-iface", Static).update(
            f"Interfaz: {iface}"
        )
