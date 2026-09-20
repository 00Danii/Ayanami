import subprocess

def run(cmd):
    return subprocess.check_output(cmd, shell=True).decode()

def get_iface_ip(iface):
    """Devuelve la IP IPv4 de la interfaz o cadena vacía."""
    try:
        out = subprocess.check_output(
            f"ip -4 addr show {iface} 2>/dev/null | awk '/inet /{{print $2}}' | cut -d/ -f1",
            shell=True, text=True
        )
        return out.strip().splitlines()[0] if out.strip() else ""
    except Exception:
        return ""

def get_interfaces_detailed():
    output = run("nmcli device status")
    interfaces = []

    for line in output.split("\n")[1:]:
        if line:
            parts = line.split()
            iface = parts[0]
            dev_type = parts[1]
            state = parts[2]
            connection = " ".join(parts[3:]) if len(parts) > 3 else ""

            interfaces.append({
                "iface": iface,
                "type": dev_type,
                "state": state,
                "connection": connection
            })

    return interfaces