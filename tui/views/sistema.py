from textual.containers import Vertical, Horizontal
from textual.widgets import Label, Static

import system


def bar(pct, width=16):
    filled = int(pct * width / 100)
    empty = width - filled
    if pct >= 80:
        c = "#f7768e"
    elif pct >= 50:
        c = "#e0af68"
    else:
        c = "#09b609"
    return f"[{c}]{'█' * filled}[/][#3b4261]{'░' * empty}[/] [white]{pct:>3}%[/]"


def dot(pct):
    if pct >= 80:
        return "[#f7768e]●[/]"
    elif pct >= 50:
        return "[#e0af68]●[/]"
    return "[#09b609]●[/]"


def fmt_bytes(b):
    for unit in ["B", "K", "M", "G", "T"]:
        if b < 1024:
            return f"{b:.1f}{unit}"
        b /= 1024
    return f"{b:.1f}P"


class SistemaView(Vertical):

    def compose(self):
        yield Static("", id="sys-header", classes="sys-header")

        with Horizontal(id="sys-main"):
            with Vertical(id="sys-col-left"):
                with Vertical(id="sys-net-card", classes="sys-panel"):
                    yield Static("", id="sys-net-content")
                with Vertical(id="sys-left-bot", classes="sys-panel"):
                    with Vertical(id="sys-mem-card", classes="sys-section"):
                        yield Static("", id="sys-mem-content")
                    with Vertical(id="sys-disk-card", classes="sys-section"):
                        yield Static("", id="sys-disk-content")
            with Vertical(id="sys-col-right"):
                with Vertical(id="sys-right-top", classes="sys-panel"):
                    with Vertical(id="sys-info-card", classes="sys-section"):
                        yield Static("", id="sys-info-content")
                    with Vertical(id="sys-cpu-card", classes="sys-section"):
                        yield Static("", id="sys-cpu-content")
                with Vertical(id="sys-proc-card", classes="sys-panel"):
                    yield Static("", id="sys-proc-content")

    def on_mount(self):
        self.refresh_data()

    def refresh_data(self):
        self._render_header()
        self._render_sys()
        self._render_cpu()
        self._render_memory()
        self._render_disk()
        self._render_network()
        self._render_processes()

    def _render_header(self):
        hostname = system.get_hostname()
        os_name = system.get_os().split()[0] if system.get_os() != "Unknown" else "?"
        kernel = system.get_kernel()
        uptime = system.get_uptime()
        count = system.get_process_count()
        dt = system.get_datetime()
        users = system.get_users()
        user = system.get_user()

        content = (
            f"[bold #ff007c]AYANAMI[/]  "
            f"[#565f89]|[/]  [#e0af68]{user}[/]  "
            f"[#565f89]|[/]  [white]{hostname}[/]  "
            f"[#565f89]|[/]  [#7aa2f7]{os_name}[/]  "
            f"[#565f89]|[/]  [#a9b1d6]{kernel}[/]  "
            f"[#565f89]|[/]  [#09b609]{uptime}[/]  "
            f"[#565f89]|[/]  [#e0af68]{count} proc[/]  "
            f"[#565f89]|[/]  [#41a6b5]{users} users[/]  "
            f"[#565f89]|[/]  [#a9b1d6]{dt}[/]"
        )
        self.query_one("#sys-header", Static).update(content)

    def _render_sys(self):
        hostname = system.get_hostname()
        kernel = system.get_kernel()
        uptime = system.get_uptime()
        shell = system.get_shell()
        gpu = system.get_gpu()
        os_name = system.get_os().split()[0] if system.get_os() != "Unknown" else "?"
        dt = system.get_datetime()
        user = system.get_user()

        lines = ["[#3b4261]── [/][bold #7aa2f7]SISTEMA[/][#3b4261] ──────────────[/]"]
        lines.append(
            f"  [#565f89]User   [/] [#ff007c]{user:<15}[/]"
            f"[#565f89]Shell  [/] [#a9b1d6]{shell}[/]"
        )
        lines.append(
            f"  [#565f89]Host   [/] [#a9b1d6]{hostname:<15}[/]"
            f"[#565f89]GPU    [/] [#a9b1d6]{(gpu or '---')[:18]}[/]"
        )
        lines.append(
            f"  [#565f89]OS     [/] [#a9b1d6]{os_name:<15}[/]"
            f"[#565f89]Kernel [/] [#a9b1d6]{kernel}[/]"
        )
        lines.append(
            f"  [#565f89]Uptime [/] [#09b609]{uptime:<15}[/]"
            f"[#565f89]Date   [/] [#a9b1d6]{dt}[/]"
        )
        content = "\n".join(lines)
        self.query_one("#sys-info-content", Static).update(content)

    def _render_cpu(self):
        model = system.get_cpu_model()
        cores = system.get_cpu_cores()
        load1, load5, load15 = system.get_load_avg()
        pct = min(100, int(load1 / cores * 100)) if cores != "?" else 0
        temp = system.get_temperature() or "---"

        def load_color(v, c):
            if v >= c * 0.8:
                return "#f7768e"
            elif v >= c * 0.5:
                return "#e0af68"
            return "#09b609"

        lines = [
            "[#3b4261]── [/][bold #7aa2f7]CPU[/][#3b4261] ─────────────────[/]",
            f"[white]{model[:40]}[/]",
            f"  [#565f89]Cores[/] [#a9b1d6]{cores}[/]  [#565f89]Temp[/] [#f7768e]{temp}[/]",
            f"  [#565f89]Load[/] [{load_color(load1, cores)}]{load1:.2f}[/]"
            f"  [{load_color(load5, cores)}]{load5:.2f}[/]"
            f"  [{load_color(load15, cores)}]{load15:.2f}[/]",
            f"  {bar(pct, 30)}",
        ]
        content = "\n".join(lines)
        self.query_one("#sys-cpu-content", Static).update(content)

    def _render_memory(self):
        total, used, buffers, cached, swap_total, swap_used = system.get_memory()
        pct = int(used / total * 100) if total else 0
        swap_pct = int(swap_used / swap_total * 100) if swap_total else 0

        if pct >= 80:
            pct_c = "#f7768e"
        elif pct >= 50:
            pct_c = "#e0af68"
        else:
            pct_c = "#09b609"

        lines = [
            "[#3b4261]── [/][bold #7aa2f7]MEMORIA RAM[/][#3b4261] ─────────────[/]",
            f"  {dot(pct)} [white]{fmt_bytes(used)}[/][#565f89] usado de[/] [#a9b1d6]{fmt_bytes(total)}[/]"
            f"  {bar(pct, 30)}",
            "",
            f"  [#e0af68]██[/] [#565f89]Buffer[/] [#a9b1d6]{fmt_bytes(buffers)}[/]",
            f"  [#7aa2f7]██[/] [#565f89]Cached[/] [#a9b1d6]{fmt_bytes(cached)}[/]",
            "",
        ]
        if swap_total > 0:
            lines.append(
                "[#3b4261]── [/][bold #7aa2f7]MEMORIA SWAP[/][#3b4261] ─────────────[/]\n"
                f"  {dot(swap_pct)} [white]{fmt_bytes(swap_used)}[/][#565f89] usado de[/] [#a9b1d6]{fmt_bytes(swap_total)}[/]"
                f"  {bar(swap_pct, 30)}"
            )
        content = "\n".join(lines)
        self.query_one("#sys-mem-content", Static).update(content)

    def _render_disk(self):
        disks = system.get_disk()
        lines = ["[#3b4261]── [/][bold #7aa2f7]DISCO[/][#3b4261] ─────────────────[/]"]
        for d in disks:
            pct = d["percent"]
            if pct >= 80:
                used_c = "#f7768e"
            elif pct >= 50:
                used_c = "#e0af68"
            else:
                used_c = "#09b609"
            mount = d["mount"]
            lines.append(
                f" {dot(pct)} [white]{d['mount']}[/]"
                f"  [#565f89]Total[/] [#a9b1d6]{d['size']}[/]"
            )
            lines.append(
                f"   [#565f89]Usado[/] [{used_c}]{d['used']:<6}[/]"
                f"[#565f89]Libre[/] [#09b609]{d['avail']:<6}[/]"
                f"  {bar(pct, 25)}"
            )
        content = "\n".join(lines)
        self.query_one("#sys-disk-content", Static).update(content)

    def _render_network(self):
        ifaces = system.get_network()
        gw = system.get_gateway()
        dns = system.get_dns()
        rx, tx = system.get_net_traffic()

        lines = ["[#3b4261]── [/][bold #7aa2f7]NETWORK[/][#3b4261] ────────────[/]"]
        for iface in ifaces[:3]:
            dev = iface["device"]
            ip = system.get_ip(dev) or "---"
            iface_type = iface["type"]
            if iface_type == "wifi":
                icon = "[#41a6b5]≈≈[/]"
                tag = f"[#41a6b5]{'wifi':<5}[/]"
            elif iface_type == "ethernet":
                icon = "[#e0af68]↑↓[/]"
                tag = f"[#e0af68]{'eth':<5}[/]"
            else:
                icon = "[#565f89]··[/]"
                tag = f"[#565f89]{iface_type[:4]:<5}[/]"
            lines.append(
                f"  {icon}  [white]{dev:<15}[/] {tag}"
                f"[#a9b1d6]{ip:<15}[/]"
            )
        lines.append(
            f"  [#7aa2f7]→ [/] [#565f89]Gateway      [/] [#a9b1d6]{gw or '---'}[/]"
        )
        lines.append(
            f"  [#7dcfff]◆ [/] [#565f89]DNS          [/] [#a9b1d6]{dns or '---'}[/]"
        )
        total = rx + tx
        lines.append(
            f"  [#09b609]RX ↓ [/] {fmt_bytes(rx)}"
            f"  [#e0af68]TX ↑ [/] {fmt_bytes(tx)}"
            f"   [#565f89]Total[/] [#a9b1d6]{fmt_bytes(total)}[/]"
        )
        content = "\n".join(lines)
        self.query_one("#sys-net-content", Static).update(content)

    def _render_processes(self):
        count = system.get_process_count()
        top = system.get_top_processes(8)
        top_mem = system.get_top_mem_processes(3)

        lines = ["[#3b4261]── [/][bold #7aa2f7]PROCESOS[/][#3b4261] ──────────[/]"]
        lines.append(f"[white]{count}[/][#565f89] total[/]")
        for p in top:
            cpu_val = float(p["cpu"])
            lines.append(
                f" {dot(cpu_val)} [#e0af68]{p['cpu']:>5}%[/] [#a9b1d6]{p['name'][:55]}[/]"
            )
        if top_mem:
            lines.append("[#3b4261]  Top Mem:[/]")
            for p in top_mem:
                lines.append(
                    f"   [#7dcfff]{p['mem']:>5}%[/] [#a9b1d6]{p['name'][:55]}[/]"
                )
        content = "\n".join(lines)
        self.query_one("#sys-proc-content", Static).update(content)
