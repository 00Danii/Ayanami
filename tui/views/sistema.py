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
    return f"[{c}]{'#' * filled}[/][#2a2e42]{'-' * empty}[/] [white]{pct:>3}%[/]"


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
                yield Static("", id="sys-net-card", classes="sys-panel")
                with Vertical(id="sys-left-bot", classes="sys-panel"):
                    yield Static("", id="sys-mem-card", classes="sys-section")
                    yield Static("", id="sys-disk-card", classes="sys-section")
            with Vertical(id="sys-col-right"):
                with Vertical(id="sys-right-top", classes="sys-panel"):
                    yield Static("", id="sys-info-card", classes="sys-section")
                    yield Static("", id="sys-cpu-card", classes="sys-section")
                yield Static("", id="sys-proc-card", classes="sys-panel")

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

        content = (
            f"[bold #ff007c]AYANAMI[/]  "
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
        temp = system.get_temperature()

        lines = [
            "[#3b4261]── [/][bold #7aa2f7]SYSTEMA[/][#3b4261] ──────────────[/]",
            f"[#565f89]Host   [/] [white]{hostname}[/]",
            f"[#565f89]Kernel  [/] [#a9b1d6]{kernel}[/]",
            f"[#565f89]Uptime  [/] [#09b609]{uptime}[/]",
            f"[#565f89]Shell   [/] [#e0af68]{shell}[/]",
        ]
        if gpu:
            lines.append(f"[#565f89]GPU     [/] [#a9b1d6]{gpu[:22]}[/]")
        if temp:
            lines.append(f"[#565f89]Temp    [/] [#f7768e]{temp}[/]")
        content = "\n".join(lines)
        self.query_one("#sys-info-card", Static).update(content)

    def _render_cpu(self):
        model = system.get_cpu_model()
        cores = system.get_cpu_cores()
        load1, load5, load15 = system.get_load_avg()
        pct = min(100, int(load1 / cores * 100)) if cores != "?" else 0
        short = model.split()[-3] if len(model.split()) >= 3 else model
        if len(short) > 22:
            short = short[:22]
        content = (
            "[#3b4261]── [/][bold #7aa2f7]CPU[/][#3b4261] ─────────────────[/]\n"
            f"[white]{short}[/]\n"
            f"[#565f89]Cores[/] [#a9b1d6]{cores}[/]"
            f"   [#565f89]Load[/] {load1:.2f}\n"
            f"  {bar(pct)}"
        )
        self.query_one("#sys-cpu-card", Static).update(content)

    def _render_memory(self):
        total, used, buffers, cached, swap_total, swap_used = system.get_memory()
        pct = int(used / total * 100) if total else 0
        swap_pct = int(swap_used / swap_total * 100) if swap_total else 0
        content = (
            "[#3b4261]── [/][bold #7aa2f7]MEMORY[/][#3b4261] ─────────────[/]\n"
            f"  {dot(pct)} [white]{fmt_bytes(used)}[/][#565f89] /[/] {fmt_bytes(total)}\n"
            f"  {bar(pct)}\n"
            f"[#565f89]Buf[/] [#a9b1d6]{fmt_bytes(buffers)}[/]"
            f"  [#565f89]Cached[/] [#a9b1d6]{fmt_bytes(cached)}[/]\n"
            f"[#565f89]Swap[/] {dot(swap_pct)} {fmt_bytes(swap_used)} / {fmt_bytes(swap_total)}"
        )
        self.query_one("#sys-mem-card", Static).update(content)

    def _render_disk(self):
        disks = system.get_disk()
        lines = ["[#3b4261]── [/][bold #7aa2f7]DISK[/][#3b4261] ─────────────────[/]"]
        for d in disks[:4]:
            mount = d["mount"]
            if len(mount) > 10:
                mount = ".." + mount[-8:]
            pct = d["percent"]
            lines.append(f" {dot(pct)} [#a9b1d6]{mount:>10}[/] {bar(pct, 12)}")
        content = "\n".join(lines)
        self.query_one("#sys-disk-card", Static).update(content)

    def _render_network(self):
        ifaces = system.get_network()
        gw = system.get_gateway()
        dns = system.get_dns()
        rx, tx = system.get_net_traffic()

        lines = ["[#3b4261]── [/][bold #7aa2f7]NETWORK[/][#3b4261] ────────────[/]"]
        for iface in ifaces[:3]:
            dev = iface["device"]
            ip = system.get_ip(dev)
            if iface["type"] == "wifi":
                icon = "[#41a6b5]~[/]"
            else:
                icon = "[#e0af68]|[/]"
            lines.append(f" {icon} [white]{dev:8}[/] [#a9b1d6]{ip or '---'}[/]")
        if gw:
            lines.append(f"[#565f89]GW [/] [#a9b1d6]{gw}[/]")
        if dns:
            lines.append(f"[#565f89]DNS[/] [#a9b1d6]{dns}[/]")
        lines.append(f"[#565f89]RX [/] [#09b609]{fmt_bytes(rx)}[/]  [#565f89]TX[/] [#e0af68]{fmt_bytes(tx)}[/]")
        content = "\n".join(lines)
        self.query_one("#sys-net-card", Static).update(content)

    def _render_processes(self):
        count = system.get_process_count()
        top = system.get_top_processes(8)
        top_mem = system.get_top_mem_processes(3)

        lines = ["[#3b4261]── [/][bold #7aa2f7]PROCESSES[/][#3b4261] ──────────[/]"]
        lines.append(f"[white]{count}[/][#565f89] total[/]")
        for p in top:
            cpu_val = float(p["cpu"])
            lines.append(
                f" {dot(cpu_val)} [#e0af68]{p['cpu']:>5}%[/] [#a9b1d6]{p['name'][:16]}[/]"
            )
        if top_mem:
            lines.append("[#3b4261]  Top Mem:[/]")
            for p in top_mem:
                lines.append(
                    f"   [#7dcfff]{p['mem']:>5}%[/] [#a9b1d6]{p['name']}[/]"
                )
        content = "\n".join(lines)
        self.query_one("#sys-proc-card", Static).update(content)
