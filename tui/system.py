import os
import socket
import subprocess
import time
from datetime import datetime


def get_hostname():
    return socket.gethostname()


def get_os():
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    return line.split("=", 1)[1].strip().strip('"')
    except Exception:
        pass
    return "Unknown"


def get_kernel():
    try:
        return subprocess.check_output("uname -r", shell=True, text=True).strip()
    except Exception:
        return "Unknown"


def get_uptime():
    try:
        with open("/proc/uptime") as f:
            seconds = float(f.read().split()[0])
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        mins = int((seconds % 3600) // 60)
        parts = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        parts.append(f"{mins}m")
        return " ".join(parts)
    except Exception:
        return "?"


def get_shell():
    return os.environ.get("SHELL", "unknown").split("/")[-1]


def get_datetime():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_gpu():
    try:
        result = subprocess.check_output(
            "lspci 2>/dev/null | grep -i vga | head -1",
            shell=True, text=True
        ).strip()
        if result:
            parts = result.split(":", 2)
            return parts[2].strip() if len(parts) >= 3 else result
    except Exception:
        pass
    return None


def get_temperature():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            temp = int(f.read().strip()) / 1000
        return f"{temp:.0f}C"
    except Exception:
        pass
    try:
        result = subprocess.check_output(
            "sensors 2>/dev/null | grep -i 'core 0' | head -1",
            shell=True, text=True
        )
        if "+" in result:
            return result.split("+")[1].split()[0]
    except Exception:
        pass
    return None


def get_cpu_model():
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if "model name" in line:
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return "Unknown"


def get_cpu_cores():
    try:
        import multiprocessing
        return multiprocessing.cpu_count()
    except Exception:
        return "?"


def get_load_avg():
    try:
        with open("/proc/loadavg") as f:
            parts = f.read().split()
        return float(parts[0]), float(parts[1]), float(parts[2])
    except Exception:
        return 0, 0, 0


def get_memory():
    try:
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split()
                key = parts[0].rstrip(":")
                info[key] = int(parts[1]) * 1024
        total = info.get("MemTotal", 0)
        available = info.get("MemAvailable", 0)
        used = total - available
        buffers = info.get("Buffers", 0)
        cached = info.get("Cached", 0)
        swap_total = info.get("SwapTotal", 0)
        swap_free = info.get("SwapFree", 0)
        swap_used = swap_total - swap_free
        return total, used, buffers, cached, swap_total, swap_used
    except Exception:
        return 0, 0, 0, 0, 0, 0


def get_disk():
    try:
        result = subprocess.check_output(
            "df -h --output=source,size,used,avail,pcent,target 2>/dev/null | grep -E '^/dev/' | head -4",
            shell=True, text=True
        )
        disks = []
        for line in result.strip().splitlines():
            parts = line.split()
            if len(parts) >= 6:
                disks.append({
                    "device": parts[0],
                    "size": parts[1],
                    "used": parts[2],
                    "avail": parts[3],
                    "percent": int(parts[4].rstrip("%")),
                    "mount": parts[5],
                })
        return disks
    except Exception:
        return []


def get_network():
    try:
        result = subprocess.check_output(
            "nmcli -t -f DEVICE,STATE,TYPE device 2>/dev/null | grep connected",
            shell=True, text=True
        )
        ifaces = []
        for line in result.strip().splitlines():
            parts = line.split(":")
            if len(parts) >= 3:
                ifaces.append({
                    "device": parts[0],
                    "state": parts[1],
                    "type": parts[2],
                })
        return ifaces
    except Exception:
        return []


def get_ip(iface):
    try:
        out = subprocess.check_output(
            f"nmcli -t -f IP4.ADDRESS device show {iface} 2>/dev/null | head -1",
            shell=True, text=True
        )
        ip = out.strip().split("=", 1)[1] if "=" in out else ""
        return ip.split("/")[0] if ip else ""
    except Exception:
        return ""


def get_gateway():
    try:
        result = subprocess.check_output(
            "ip route show default 2>/dev/null | head -1",
            shell=True, text=True
        )
        parts = result.split()
        return parts[2] if len(parts) >= 3 else ""
    except Exception:
        return ""


def get_dns():
    try:
        with open("/etc/resolv.conf") as f:
            for line in f:
                if line.startswith("nameserver"):
                    return line.split()[1]
    except Exception:
        pass
    return ""


def get_net_traffic():
    try:
        with open("/proc/net/dev") as f:
            lines = f.readlines()[2:]
        total_rx = 0
        total_tx = 0
        for line in lines:
            parts = line.split()
            if len(parts) >= 10:
                total_rx += int(parts[1])
                total_tx += int(parts[9])
        return total_rx, total_tx
    except Exception:
        return 0, 0


def get_users():
    try:
        result = subprocess.check_output(
            "who 2>/dev/null | wc -l", shell=True, text=True
        )
        return int(result.strip())
    except Exception:
        return "?"


def get_process_count():
    try:
        result = subprocess.check_output(
            "ps -e --no-headers | wc -l", shell=True, text=True
        )
        return int(result.strip())
    except Exception:
        return "?"


def get_top_processes(n=5):
    try:
        result = subprocess.check_output(
            f"ps aux --sort=-pcpu | head -{n + 1} | tail -{n}",
            shell=True, text=True
        )
        procs = []
        for line in result.strip().splitlines():
            parts = line.split(None, 10)
            if len(parts) >= 11:
                procs.append({
                    "user": parts[0][:8],
                    "pid": parts[1],
                    "cpu": parts[2],
                    "mem": parts[3],
                    "name": parts[10],
                })
        return procs
    except Exception:
        return []


def get_top_mem_processes(n=3):
    try:
        result = subprocess.check_output(
            f"ps aux --sort=-pmem | head -{n + 1} | tail -{n}",
            shell=True, text=True
        )
        procs = []
        for line in result.strip().splitlines():
            parts = line.split(None, 10)
            if len(parts) >= 11:
                procs.append({
                    "name": parts[10],
                    "mem": parts[3],
                })
        return procs
    except Exception:
        return []
