from datetime import datetime

from rich import box
from rich.console import Group
from rich.table import Table

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
    DNS,
    DNSQR,
    DNSRR,
    Ether,
    IP,
    TCP,
    UDP,
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
        self.last_pkt_detail: Table | None = None
        self.ui_timer = None

        self.refresh_devices()
        self.query_one(
            "#pause-sniffer", Button
        ).disabled = True
        self.query_one(
            "#stop-sniffer", Button
        ).disabled = True
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

        self.query_one(
            "#start-sniffer", Button
        ).disabled = True

        self.query_one(
            "#pause-sniffer", Button
        ).disabled = False

        self.query_one(
            "#stop-sniffer", Button
        ).disabled = False

        if self.sniffer:
            self.notify("Ya activo", severity="warning")
            return

        iface = getattr(self.app, "selected_interface", None)
        if not iface:
            self.notify("Selecciona una interfaz", severity="error")
            return

        bpf_filter = None

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
            btn.variant = "success"
            status = "[yellow]PAUSADO[/]"
            if self.ui_timer:
                self.ui_timer.pause()
        else:
            btn.label = "PAUSAR"
            btn.variant = "warning"
            status = "[green]CAPTURANDO[/]"
            if self.ui_timer:
                self.ui_timer.resume()

        self.query_one("#sniffer-status", Static).update(status)

    # ==========================================================
    # STOP
    # ==========================================================

    def stop_sniffer(self):

        self.paused = False

        self.query_one(
            "#start-sniffer", Button
        ).disabled = False

        self.query_one(
            "#pause-sniffer", Button
        ).disabled = True

        self.query_one(
            "#stop-sniffer", Button
        ).disabled = True

        self.query_one("#pause-sniffer", Button).label = "PAUSAR"
        self.query_one("#pause-sniffer", Button).variant = "warning"

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
        self.query_one("#sniffer-last-packet", Static).update(
            "[dim]Esperando captura...[/]"
        )
        self.query_one("#sniffer-packet-detail", Static).update("")
        self.last_pkt_detail = None

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

            parts: list[Table] = []

            if pkt.haslayer(Ether):
                et = Table(
                    box=box.ROUNDED,
                    show_header=False,
                    padding=(0, 2),
                    expand=True,
                )
                et.add_column(width=8, no_wrap=True)
                et.add_column(ratio=1, no_wrap=True)
                et.add_row(
                    "[bold #565f89]ETHER[/]", "", end_section=True
                )
                et.add_row(
                    "[#565f89]src[/]",
                    f"[#565f89]{pkt[Ether].src}[/]",
                )
                et.add_row(
                    "[#565f89]dst[/]",
                    f"[#565f89]{pkt[Ether].dst}[/]",
                )
                parts.append(et)

            ipt = Table(
                box=box.ROUNDED,
                show_header=False,
                padding=(0, 2),
                expand=True,
            )
            ipt.add_column(width=8, no_wrap=True)
            ipt.add_column(ratio=1, no_wrap=True)
            ipt.add_row("[bold #7aa2f7]IP[/]", "", end_section=True)
            ipt.add_row("[#565f89]De[/]", f"[#9ece6a]{src}[/]")
            ipt.add_row("[#565f89]Para[/]", f"[#f7768e]{dst}[/]")
            ipt.add_row("[#565f89]Protocolo[/]", f"[#e0af68]{proto}[/]")
            ipt.add_row("[#565f89]Tamaño[/]", f"[#7dcfff]{length}B[/]")
            parts.append(ipt)

            if pkt.haslayer(TCP):
                tcp = Table(
                    box=box.ROUNDED,
                    show_header=False,
                    padding=(0, 2),
                    expand=True,
                )
                tcp.add_column(width=8, no_wrap=True)
                tcp.add_column(ratio=1, no_wrap=True)
                tcp.add_row(
                    "[bold #9ece6a]TCP[/]", "", end_section=True
                )
                svc = SERVICE_MAP.get(pkt[TCP].sport) or SERVICE_MAP.get(pkt[TCP].dport) or ""
                sport_label = f"{pkt[TCP].sport}"
                dport_label = f"{pkt[TCP].dport}"
                if svc:
                    sport_label += f" [#3b4261]({svc})[/]"
                    dport_label += f" [#3b4261]({svc})[/]"
                tcp.add_row(
                    "[#565f89]Puerto[/]",
                    f"[#7dcfff]{sport_label}[/] [#f7768e]\u2192[/] [#7dcfff]{dport_label}[/]",
                )
                tcp.add_row(
                    "[#565f89]Banderas[/]",
                    f"[#e0af68]{pkt[TCP].flags}[/]",
                )
                try:
                    data_len = len(pkt[TCP].payload)
                except Exception:
                    data_len = 0
                tcp.add_row(
                    "[#565f89]Datos[/]",
                    f"[#7dcfff]{data_len}B[/]" if data_len else "[#565f89]0[/]",
                )
                parts.append(tcp)

            if pkt.haslayer(UDP):
                udp = Table(
                    box=box.ROUNDED,
                    show_header=False,
                    padding=(0, 2),
                    expand=True,
                )
                udp.add_column(width=8, no_wrap=True)
                udp.add_column(ratio=1, no_wrap=True)
                udp.add_row(
                    "[bold #e0af68]UDP[/]", "", end_section=True
                )
                svc = SERVICE_MAP.get(pkt[UDP].sport) or SERVICE_MAP.get(pkt[UDP].dport) or ""
                sport_label = f"{pkt[UDP].sport}"
                dport_label = f"{pkt[UDP].dport}"
                if svc:
                    sport_label += f" [#3b4261]({svc})[/]"
                    dport_label += f" [#3b4261]({svc})[/]"
                udp.add_row(
                    "[#565f89]Puerto[/]",
                    f"[#7dcfff]{sport_label}[/] [#f7768e]\u2192[/] [#7dcfff]{dport_label}[/]",
                )
                parts.append(udp)

            if pkt.haslayer(DNSQR) or pkt.haslayer(DNSRR):
                dnst = Table(
                    box=box.ROUNDED,
                    show_header=False,
                    padding=(0, 2),
                    expand=True,
                )
                dnst.add_column(width=8, no_wrap=True)
                dnst.add_column(ratio=1, no_wrap=True)
                dnst.add_row(
                    "[bold #bb9af7]DNS[/]", "", end_section=True
                )
                if pkt.haslayer(DNS):
                    qr = "[#9ece6a]Respuesta[/]" if pkt[DNS].qr else "[#e0af68]Consulta[/]"
                    dnst.add_row(
                        "[#565f89]Tipo[/]", qr
                    )
                if pkt.haslayer(DNSQR):
                    qname = pkt[DNSQR].qname.decode()
                    dnst.add_row(
                        "[#565f89]Consulta[/]",
                        f"[#a9b1d6]{qname[:100]}[/]",
                    )
                    self.dns_count += 1
                if pkt.haslayer(DNSRR):
                    for rr in pkt[DNSRR][:3]:
                        try:
                            dnst.add_row(
                                "[#565f89]Respuesta[/]",
                                f"[#a9b1d6]{rr.rdata.decode()[:60]}[/]",
                            )
                        except Exception:
                            pass
                parts.append(dnst)

            self.last_pkt_detail = Group(*parts) if parts else None
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
