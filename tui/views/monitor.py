from threading import Lock
from datetime import datetime
import socket
import time

from textual.app import ComposeResult
from textual.containers import (
    Vertical,
    Horizontal,
    VerticalScroll
)

from textual.widgets import (
    Label,
    Button,
    DataTable,
    Static,
    Select
)

from scapy.all import (
    AsyncSniffer,
    IP,
    TCP,
    UDP
)

import scanner


SERVICE_MAP = {

    80: "HTTP",
    443: "HTTPS",
    53: "DNS",
    22: "SSH",
    21: "FTP",
    123: "NTP",
    8080: "HTTP-ALT",
    3306: "MYSQL",
    27017: "MONGODB"
}


class MonitorView(Vertical):

    # ==========================================================
    # UI
    # ==========================================================

    def compose(self) -> ComposeResult:

        # TOPBAR

        yield Horizontal(

            Label(
                "Monitor de tráfico en tiempo real",
                classes="monitor-title"
            ),

            Select(
                options=[
                    ("Toda la red", "ALL")
                ],
                value="ALL",
                id="monitor-host-select"
            ),
            
            Button(
                "↻",
                id="refresh-hosts",
                variant="primary"
            ),

            Button(
                "INICIAR",
                variant="success",
                id="start-monitor"
            ),

            Button(
                "PAUSAR",
                variant="error",
                id="stop-monitor"
            ),

            classes="monitor-topbar"
        )

        # STATS

        yield Horizontal(

            Static(
                "Interfaz: --",
                id="monitor-iface",
                classes="monitor-stat"
            ),

            Static(
                "Flows: 0",
                id="monitor-flows",
                classes="monitor-stat"
            ),

            Static(
                "Packets: 0",
                id="monitor-packets",
                classes="monitor-stat"
            ),

            Static(
                "Actualización: --",
                id="monitor-lastupdate",
                classes="monitor-stat"
            ),

            classes="monitor-stats-bar"
        )

        with Horizontal(
            id="monitor-content"
        ):

            # TABLA

            yield DataTable(
                id="monitor-table"
            )

            # PANEL DERECHO

            with Vertical(
                id="monitor-side-panel"
            ):

                # yield Static(
                #     "FLOW INSPECTOR",
                #     classes="monitor-panel-title"
                # )

                with VerticalScroll():

                    yield Static(
                        "Selecciona un flujo",
                        id="monitor-info",
                        markup=True
                    )

    # ==========================================================
    # MOUNT
    # ==========================================================

    def on_mount(self):

        self.flows = {}

        self.flow_lock = Lock()

        self.hostname_cache = {}

        self.total_packets = 0

        self.monitor_worker = None

        self.update_timer = None

        self.row_map = {}

        self.selected_host = "ALL"

        self.populate_hosts()

        table = self.query_one(
            "#monitor-table",
            DataTable
        )

        table.cursor_type = "row"

        table.zebra_stripes = True

        table.add_columns(
            "SOURCE",
            "DESTINATION",
            "SERVICE",
            "PROTO",
            "RATE",
            "GRAPH",
            "PACKETS",
            "TOTAL"
        )

        self.refresh_stats()

    # ==========================================================
    # HOSTS
    # ==========================================================

    def populate_hosts(self):

        select = self.query_one(
            "#monitor-host-select",
            Select
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

            hostname = self.resolve_hostname(ip)

            label = f"{hostname} ({ip})"

            options.append(
                (label, ip)
            )

        select.set_options(options)

    # ==========================================================
    # EVENTS
    # ==========================================================

    # def on_select_changed(self, event):

    #     if event.select.id == "monitor-host-select":

    #         self.selected_host = event.value

    #         self.notify(
    #             f"Filtro: {self.selected_host}"
    #         )

    def on_button_pressed(self, event):

        if event.button.id == "start-monitor":

            self.start_monitor()

        elif event.button.id == "stop-monitor":

            self.stop_monitor()
            
        elif event.button.id == "refresh-hosts":
            self.refresh_hosts()
            
    
    # REFRESH HOSTS
    def refresh_hosts(self):
        current = self.selected_host
        
        self.populate_hosts()
        
        select = self.query_one(
            "#monitor-host-select",
            Select
        )

        try:
            select.value = current
        except Exception:
            select.value = "ALL"

        self.notify(
            "Dispositivos actualizados"
        )

    # ==========================================================
    # START
    # ==========================================================

    def start_monitor(self):
        
        self.query_one(
            "#stop-monitor",
            Button
        ).label = "PAUSAR"
        
        self.query_one(
            "#start-monitor",
            Button
        ).disabled = True
        
        if self.monitor_worker:
            self.notify(
                "El monitor ya está activo",
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

        self.flows.clear()

        self.row_map.clear()

        self.total_packets = 0

        table = self.query_one(
            "#monitor-table",
            DataTable
        )

        table.clear()

        self.monitor_worker = self.run_worker(
            lambda: self.sniff_traffic(iface),
            thread=True,
            exclusive=True
        )

        self.update_timer = self.set_interval(
            1,
            self.update_table
        )

        self.notify(
            f"Monitoreando {iface}"
        )

    # ==========================================================
    # STOP
    # ==========================================================

    def stop_monitor(self):
        
        self.query_one(
            "#start-monitor",
            Button
        ).disabled = False

        if self.update_timer:

            self.update_timer.stop()

            self.update_timer = None

        if self.monitor_worker:

            self.monitor_worker.cancel()

            self.monitor_worker = None

        self.notify(
            "Monitor pausado"
        )

    # ==========================================================
    # SNIFFER
    # ==========================================================

    def sniff_traffic(self, iface):

        def packet_callback(pkt):

            try:

                if not pkt.haslayer(IP):
                    return

                src_ip = pkt[IP].src
                dst_ip = pkt[IP].dst

                # ==================================================
                # FILTRO POR HOST
                # ==================================================

                if self.selected_host != "ALL":

                    if (
                        src_ip != self.selected_host
                        and dst_ip != self.selected_host
                    ):
                        return

                # ==================================================
                # PROTOCOLOS
                # ==================================================

                proto = "IP"

                sport = 0
                dport = 0

                if pkt.haslayer(TCP):

                    proto = "TCP"

                    sport = pkt[TCP].sport
                    dport = pkt[TCP].dport

                elif pkt.haslayer(UDP):

                    proto = "UDP"

                    sport = pkt[UDP].sport
                    dport = pkt[UDP].dport

                # ==================================================
                # FLOW
                # ==================================================

                src = f"{src_ip}"
                dst = f"{dst_ip}"

                service = SERVICE_MAP.get(
                    dport,
                    "UNKNOWN"
                )

                size = len(pkt)

                flow_key = (
                    src,
                    dst,
                    proto
                )

                # ==================================================
                # HOSTNAME
                # ==================================================

                hostname = self.resolve_hostname(
                    dst_ip
                )

                # ==================================================
                # DIRECCIÓN DEL FLUJO
                # ==================================================

                direction = "OUTBOUND"

                if self.selected_host != "ALL":

                    if src_ip == self.selected_host:

                        direction = "UPLOAD"

                    elif dst_ip == self.selected_host:

                        direction = "DOWNLOAD"

                # ==================================================
                # LOCAL / INTERNET
                # ==================================================

                is_local = (

                    dst_ip.startswith("192.168.")
                    or dst_ip.startswith("10.")
                    or dst_ip.startswith("172.")
                )

                network_type = (
                    "LAN"
                    if is_local
                    else "INTERNET"
                )

                # ==================================================
                # FLOW STORAGE
                # ==================================================

                with self.flow_lock:

                    self.total_packets += 1

                    if flow_key not in self.flows:

                        self.flows[flow_key] = {

                            # BÁSICO

                            "service": service,
                            "bytes": 0,
                            "packets": 0,
                            "rate": 0,

                            # RATE TRACKING

                            "last_bytes": 0,
                            "last_update": time.time(),

                            # METADATA

                            "hostname": hostname,
                            "src_ip": src_ip,
                            "dst_ip": dst_ip,
                            "sport": sport,
                            "dport": dport,
                            "proto": proto,

                            # FLOW INFO

                            "direction": direction,
                            "network_type": network_type,

                            # TIMESTAMPS

                            "first_seen": datetime.now().strftime(
                                "%H:%M:%S"
                            ),

                            # EXTRA

                            "ttl": pkt[IP].ttl,
                            "length": size
                        }

                    flow = self.flows[flow_key]

                    # ==================================================
                    # UPDATE FLOW
                    # ==================================================

                    flow["bytes"] += size

                    flow["packets"] += 1

                    flow["last_packet"] = datetime.now().strftime(
                        "%H:%M:%S"
                    )

            except Exception:

                pass

        # ==========================================================
        # SNIFFER
        # ==========================================================

        try:

            sniffer = AsyncSniffer(

                iface=iface,

                prn=packet_callback,

                store=False
            )

            sniffer.start()

            while (
                self.monitor_worker
                and not self.monitor_worker.is_cancelled
            ):

                time.sleep(0.2)

            sniffer.stop()

        except Exception as e:

            self.call_from_thread(

                self.notify,

                f"Error: {e}",

                severity="error"
            )

    # ==========================================================
    # TABLE UPDATE
    # ==========================================================

    def update_table(self):

        table = self.query_one(
            "#monitor-table",
            DataTable
        )

        # PRESERVAR POSICIÓN
        current_cursor = table.cursor_coordinate

        table.clear()

        now = time.time()

        with self.flow_lock:

            flows_copy = dict(self.flows)

        sorted_flows = []

        for key, data in flows_copy.items():

            src, dst, proto = key

            elapsed = now - data["last_update"]

            if elapsed <= 0:
                continue

            delta = (
                data["bytes"]
                - data["last_bytes"]
            )

            rate = delta / elapsed

            data["rate"] = rate

            data["last_bytes"] = data["bytes"]

            data["last_update"] = now

            self.flows[key] = data

            sorted_flows.append(
                (key, data)
            )

        sorted_flows.sort(
            key=lambda x: x[1]["rate"],
            reverse=True
        )

        for key, data in sorted_flows:

            src, dst, proto = key

            rate_kb = data["rate"] / 1024

            total_mb = (
                data["bytes"]
                / 1024
                / 1024
            )

            if rate_kb > 1024:

                rate_text = (
                    f"[red]{rate_kb / 1024:.2f} MB/s[/]"
                )

            elif rate_kb > 100:

                rate_text = (
                    f"[yellow]{rate_kb:.2f} KB/s[/]"
                )

            else:

                rate_text = (
                    f"[green]{rate_kb:.2f} KB/s[/]"
                )

            # MINI BARRA VISUAL

            MAX_BARS = 10

            bars = min(
                int(rate_kb / 10),
                MAX_BARS
            )

            filled = "█" * bars
            empty = "░" * (MAX_BARS - bars)

            graph = (
                f"[green]{filled}[/][#3b4261]{empty}[/]"
            )

            table.add_row(

                src,

                dst,

                data["service"],

                proto,

                rate_text,

                graph,

                str(data["packets"]),

                f"{total_mb:.2f} MB"
            )

        # RESTAURAR CURSOR

        try:
            table.cursor_coordinate = current_cursor
        except:
            pass

        self.refresh_stats()

    # ==========================================================
    # GRAPH
    # ==========================================================

    def make_bar(self, rate_kb):

        bars = int(rate_kb / 50)

        bars = min(bars, 25)

        if bars > 20:

            color = "red"

        elif bars > 10:

            color = "yellow"

        else:

            color = "green"

        return (
            f"[{color}]"
            + ("█" * bars)
            + "[/]"
        )

    # ==========================================================
    # STATS
    # ==========================================================

    def refresh_stats(self):

        iface = getattr(
            self.app,
            "selected_interface",
            "--"
        )

        self.query_one(
            "#monitor-iface",
            Static
        ).update(
            f"Interfaz: {iface}"
        )

        self.query_one(
            "#monitor-flows",
            Static
        ).update(
            f"Flows: {len(self.flows)}"
        )

        self.query_one(
            "#monitor-packets",
            Static
        ).update(
            f"Packets: {self.total_packets}"
        )

        self.query_one(
            "#monitor-lastupdate",
            Static
        ).update(
            datetime.now().strftime("%H:%M:%S")
        )

    # ==========================================================
    # HOSTNAME
    # ==========================================================

    def resolve_hostname(self, ip):

        if ip in self.hostname_cache:

            return self.hostname_cache[ip]

        try:

            hostname = socket.gethostbyaddr(ip)[0]

        except Exception:

            hostname = ip

        self.hostname_cache[ip] = hostname

        return hostname

    # ==========================================================
    # ROW SELECT
    # ==========================================================

    def on_data_table_row_selected(
        self,
        event: DataTable.RowSelected
    ):

        table = self.query_one(
            "#monitor-table",
            DataTable
        )

        row = table.get_row(
            event.row_key
        )

        src = row[0]
        dst = row[1]
        proto = row[3]

        # ==========================================================
        # BUSCAR FLOW REAL
        # ==========================================================

        flow_data = None

        with self.flow_lock:

            for key, flow in self.flows.items():

                flow_src, flow_dst, flow_proto = key

                if (
                    flow_src == src
                    and flow_dst == dst
                    and flow_proto == proto
                ):

                    flow_data = flow
                    break

        if not flow_data:
            return

        # ==========================================================
        # EXTRAER DATOS
        # ==========================================================

        hostname = flow_data.get(
            "hostname",
            "Unknown"
        )

        service = flow_data.get(
            "service",
            "UNKNOWN"
        )

        direction = flow_data.get(
            "direction",
            "UNKNOWN"
        )

        network_type = flow_data.get(
            "network_type",
            "UNKNOWN"
        )

        sport = flow_data.get(
            "sport",
            "?"
        )

        dport = flow_data.get(
            "dport",
            "?"
        )

        packets = flow_data.get(
            "packets",
            0
        )

        total_mb = (
            flow_data.get("bytes", 0)
            / 1024
            / 1024
        )

        rate_kb = (
            flow_data.get("rate", 0)
            / 1024
        )

        ttl = flow_data.get(
            "ttl",
            "?"
        )

        first_seen = flow_data.get(
            "first_seen",
            "--"
        )

        last_packet = flow_data.get(
            "last_packet",
            "--"
        )

        # ==========================================================
        # PANEL INFO
        # ==========================================================

        info = f"""
╔═══════════════════════════════════╗
║          FLOW INSPECTOR           ║
╚═══════════════════════════════════╝

[bold #7aa2f7]REMOTE HOST[/]
[white]{hostname}[/]

[bold #7aa2f7]CONNECTION[/]

[#9ece6a]SRC      :[/] {src}
[#9ece6a]DST      :[/] {dst}

[#e0af68]SERVICE  :[/] {service}
[#bb9af7]PROTO    :[/] {proto}

[#7dcfff]SPORT    :[/] {sport}
[#7dcfff]DPORT    :[/] {dport}

[#c0caf5]FLOW     :[/] {direction}
[#f7768e]NETWORK  :[/] {network_type}

[#9ece6a]TTL      :[/] {ttl}

[bold #7aa2f7]TRAFFIC[/]

[#7dcfff]RATE     :[/] {rate_kb:.2f} KB/s
[#c0caf5]PACKETS  :[/] {packets}
[#f7768e]TOTAL    :[/] {total_mb:.2f} MB

[bold #7aa2f7]TIMELINE[/]

[#e0af68]FIRST    :[/] {first_seen}
[#e0af68]LAST     :[/] {last_packet}
"""

        self.query_one(
            "#monitor-info",
            Static
        ).update(info)