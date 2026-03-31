import subprocess

def get_neighbors():
    result = subprocess.check_output("ip neigh", shell=True).decode()
    devices = []

    for line in result.split("\n"):
        if "REACHABLE" in line or "STALE" in line:
            parts = line.split()
            ip = parts[0]
            mac = parts[4] if "lladdr" in parts else "?"
            dev = parts[2]

            devices.append({
                "ip": ip,
                "mac": mac,
                "iface": dev
            })

    return devices

def show_neighbors():
    devices = get_neighbors()

    print("\n[+] Dispositivos en la red:\n")
    for i, d in enumerate(devices):
        print(f"{i+1}. {d['ip']} ({d['mac']}) - {d['iface']}")