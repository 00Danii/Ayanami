from datetime import datetime
from threading import Lock

from textual.app import ComposeResult
from textual.containers import (
    Vertical,
    Horizontal,
    VerticalScroll
)

from textual.widgets import (
    Label,
    Button,
    Static,
    Select,
    RichLog
)

from scapy.all import (
    AsyncSniffer,
    IP,
    TCP,
    UDP,
    DNSQR,
    Raw
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

        # ======================================================
        # HEADER
        # ======================================================

        yield Horizontal(

            Label(
                "DEEP PACKET INSPECTOR",
                classes="sniffer-title"
            ),

            Static(
                "[red]STOPPED[/]",
                id="sniffer-status"
            ),

            classes="sniffer-header"
        )

        # ======================================================
        # TOOLBAR
        # ======================================================

        yield Horizontal(

            Select(
                [
                    ("Todo el tráfico", "all"),
                    ("Por dispositivo", "device")
                ],
                value="all",
                id="sniffer-mode"
            ),

            Horizontal(

                Select(
                    [],
                    id="sniffer-device"
                ),

                Button(
                    "↻",
                    id="refresh-devices"
                ),

                id="device-controls",
                classes="device-controls"
            ),

            Button(
                "START",
                variant="success",
                id="start-sniffer"
            ),

            Button(
                "PAUSE",
                variant="warning",
                id="pause-sniffer"
            ),

            Button(
                "STOP",
                variant="error",
                id="stop-sniffer"
            ),

            classes="sniffer-toolbar"
        )

        # ======================================================
        # STATS
        # ======================================================

        yield Horizontal(

            Static(
                "Packets: 0",
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
                "Interface: --",
                id="sniffer-iface",
                classes="sniffer-stat"
            ),

            classes="sniffer-stats"
        )

        # ======================================================
        # MAIN CONTENT
        # ======================================================

        with Horizontal(
            id="sniffer-main"
        ):

            # ==================================================
            # LIVE LOG
            # ==================================================

            yield RichLog(
                id="sniffer-log",
                markup=True,
                highlight=True,
                wrap=True
            )

            # ==================================================
            # INSPECTOR
            # ==================================================

            with VerticalScroll(
                id="sniffer-inspector-container"
            ):

                yield Static(

                    """
[bold #7aa2f7]PACKET INSPECTOR[/]

Esperando paquetes...
                    """,

                    id="packet-inspector",
                    markup=True
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

        self.packet_lock = Lock()

        self.last_packet = None

        self.refresh_devices()

        self.update_stats()
        
        self.update_mode_ui()
        
    
    # ==========================================================
    # MODE CHANGE
    # ==========================================================
    
    def update_mode_ui(self):

        mode = self.query_one(
            "#sniffer-mode",
            Select
        ).value

        device_controls = self.query_one(
            "#device-controls",
            Horizontal
        )

        if mode == "device":

            device_controls.display = True

        else:

            device_controls.display = False

    def on_select_changed(self, event):

        if event.select.id == "sniffer-mode":

            self.update_mode_ui()
    # ==========================================================
    # BUTTONS
    # ==========================================================

    def on_button_pressed(self, event):

        button_id = event.button.id

        if button_id == "refresh-devices":

            self.refresh_devices()

        elif button_id == "start-sniffer":

            self.start_sniffer()

        elif button_id == "pause-sniffer":

            self.toggle_pause()

        elif button_id == "stop-sniffer":

            self.stop_sniffer()

    # ==========================================================
    # DEVICES
    # ==========================================================

    def refresh_devices(self):

        try:

            devices = scanner.get_neighbors()

            options = []

            for d in devices:

                label = (
                    f"{d['ip']} ({d['mac']})"
                )

                options.append(
                    (label, d["ip"])
                )

            if not options:

                options = [
                    ("No devices", "NONE")
                ]

            select = self.query_one(
                "#sniffer-device",
                Select
            )

            select.set_options(options)

            select.value = options[0][1]

        except Exception as e:

            self.notify(
                str(e),
                severity="error"
            )

    # ==========================================================
    # START
    # ==========================================================

    def start_sniffer(self):

        if self.sniffer:

            self.notify(
                "Sniffer ya activo",
                severity="warning"
            )
            return

        iface = getattr(
            self.app,
            "selected_interface",
            None
        )

        if not iface:

            self.notify(
                "Selecciona una interfaz",
                severity="error"
            )

            return

        mode = self.query_one(
            "#sniffer-mode",
            Select
        ).value

        device = self.query_one(
            "#sniffer-device",
            Select
        ).value

        bpf_filter = None

        if mode == "device" and device != "NONE":

            bpf_filter = f"host {device}"

        self.paused = False

        self.sniffer = AsyncSniffer(

            iface=iface,

            prn=self.process_packet,

            store=False,

            filter=bpf_filter
        )

        self.sniffer.start()

        self.query_one(
            "#sniffer-status",
            Static
        ).update(
            "[green]RUNNING[/]"
        )

        self.notify(
            f"Capturando en {iface}"
        )

    # ==========================================================
    # PAUSE
    # ==========================================================

    def toggle_pause(self):

        if not self.sniffer:
            return

        self.paused = not self.paused

        btn = self.query_one(
            "#pause-sniffer",
            Button
        )

        if self.paused:

            btn.label = "RESUME"

            self.query_one(
                "#sniffer-status",
                Static
            ).update(
                "[yellow]PAUSED[/]"
            )

        else:

            btn.label = "PAUSE"

            self.query_one(
                "#sniffer-status",
                Static
            ).update(
                "[green]RUNNING[/]"
            )

    # ==========================================================
    # STOP
    # ==========================================================

    def stop_sniffer(self):

        self.paused = False

        if self.sniffer:

            try:

                if getattr(
                    self.sniffer,
                    "running",
                    False
                ):

                    self.sniffer.stop()

            except Exception:
                pass

            self.sniffer = None

        self.query_one(
            "#sniffer-status",
            Static
        ).update(
            "[red]STOPPED[/]"
        )

        self.query_one(
            "#pause-sniffer",
            Button
        ).label = "PAUSE"

        self.notify(
            "Sniffer detenido"
        )

    # ==========================================================
    # PROCESS PACKET
    # ==========================================================

    def process_packet(self, pkt):

        if self.paused:
            return

        if not pkt.haslayer(IP):
            return

        try:

            self.last_packet = pkt

            src = pkt[IP].src
            dst = pkt[IP].dst

            proto = "IP"

            service = "UNKNOWN"

            info = ""

            length = len(pkt)

            # ==================================================
            # TCP
            # ==================================================

            if pkt.haslayer(TCP):

                proto = "TCP"

                sport = pkt[TCP].sport
                dport = pkt[TCP].dport

                service = SERVICE_MAP.get(
                    dport,
                    "TCP"
                )

                flags = pkt[TCP].flags

                info = (
                    f"{sport} → {dport} "
                    f"FLAGS={flags}"
                )

                self.tcp_count += 1

            # ==================================================
            # UDP
            # ==================================================

            elif pkt.haslayer(UDP):

                proto = "UDP"

                sport = pkt[UDP].sport
                dport = pkt[UDP].dport

                service = SERVICE_MAP.get(
                    dport,
                    "UDP"
                )

                info = (
                    f"{sport} → {dport}"
                )

                self.udp_count += 1

            # ==================================================
            # DNS
            # ==================================================

            if pkt.haslayer(DNSQR):

                query = pkt[DNSQR].qname.decode()

                service = "DNS"

                info += f" QUERY={query}"

                self.dns_count += 1

            # ==================================================
            # RAW PAYLOAD
            # ==================================================

            payload_preview = ""

            if pkt.haslayer(Raw):

                try:

                    payload_preview = (
                        pkt[Raw]
                        .load[:80]
                        .decode(
                            errors="ignore"
                        )
                    )

                except Exception:
                    pass

            self.packet_count += 1

            timestamp = datetime.now().strftime(
                "%H:%M:%S"
            )

            # ==================================================
            # LIVE LOG
            # ==================================================

            log_message = f"""

[bold #7aa2f7]{timestamp}[/]

[#9ece6a]{src}[/]
→
[#f7768e]{dst}[/]

[#e0af68]{proto}[/]
[#bb9af7]{service}[/]

{info}

[#7dcfff]{length} bytes[/]

{payload_preview}

────────────────────────────────────
"""

            self.app.call_from_thread(

                self.add_log_entry,

                log_message
            )

            # ==================================================
            # INSPECTOR
            # ==================================================

            self.app.call_from_thread(
                self.update_inspector,
                pkt
            )

        except Exception:
            pass

    # ==========================================================
    # LOG
    # ==========================================================

    def add_log_entry(self, text):

        log = self.query_one(
            "#sniffer-log",
            RichLog
        )

        log.write(text)

        self.update_stats()

    # ==========================================================
    # INSPECTOR
    # ==========================================================

    def update_inspector(self, pkt):

        details = []

        details.append(
            "[bold #7aa2f7]PACKET INSPECTOR[/]\n"
        )

        details.append(pkt.summary())

        # ======================================================
        # IP
        # ======================================================

        if pkt.haslayer(IP):

            details.append(
                "\n[bold cyan]IP[/]"
            )

            details.append(
                f"SRC : {pkt[IP].src}"
            )

            details.append(
                f"DST : {pkt[IP].dst}"
            )

            details.append(
                f"TTL : {pkt[IP].ttl}"
            )

            details.append(
                f"LEN : {pkt[IP].len}"
            )

        # ======================================================
        # TCP
        # ======================================================

        if pkt.haslayer(TCP):

            details.append(
                "\n[bold green]TCP[/]"
            )

            details.append(
                f"SPORT : {pkt[TCP].sport}"
            )

            details.append(
                f"DPORT : {pkt[TCP].dport}"
            )

            details.append(
                f"FLAGS : {pkt[TCP].flags}"
            )

            details.append(
                f"SEQ   : {pkt[TCP].seq}"
            )

        # ======================================================
        # UDP
        # ======================================================

        if pkt.haslayer(UDP):

            details.append(
                "\n[bold yellow]UDP[/]"
            )

            details.append(
                f"SPORT : {pkt[UDP].sport}"
            )

            details.append(
                f"DPORT : {pkt[UDP].dport}"
            )

        # ======================================================
        # DNS
        # ======================================================

        if pkt.haslayer(DNSQR):

            details.append(
                "\n[bold magenta]DNS[/]"
            )

            details.append(
                f"QUERY : "
                f"{pkt[DNSQR].qname.decode()}"
            )

        # ======================================================
        # RAW
        # ======================================================

        if pkt.haslayer(Raw):

            details.append(
                "\n[bold red]PAYLOAD[/]"
            )

            try:

                payload = (
                    pkt[Raw]
                    .load[:500]
                    .decode(
                        errors="ignore"
                    )
                )

                details.append(payload)

            except Exception:

                details.append(
                    "Payload no decodificable"
                )

        # ======================================================
        # HEX
        # ======================================================

        details.append(
            "\n[bold #f7768e]HEX DUMP[/]"
        )

        hex_dump = bytes(pkt).hex()

        details.append(
            hex_dump[:1500]
        )

        self.query_one(
            "#packet-inspector",
            Static
        ).update(
            "\n".join(details)
        )

    # ==========================================================
    # STATS
    # ==========================================================

    def update_stats(self):

        iface = getattr(
            self.app,
            "selected_interface",
            "--"
        )

        self.query_one(
            "#sniffer-packets",
            Static
        ).update(
            f"Packets: {self.packet_count}"
        )

        self.query_one(
            "#sniffer-tcp",
            Static
        ).update(
            f"TCP: {self.tcp_count}"
        )

        self.query_one(
            "#sniffer-udp",
            Static
        ).update(
            f"UDP: {self.udp_count}"
        )

        self.query_one(
            "#sniffer-dns",
            Static
        ).update(
            f"DNS: {self.dns_count}"
        )

        self.query_one(
            "#sniffer-iface",
            Static
        ).update(
            f"Interface: {iface}"
        )