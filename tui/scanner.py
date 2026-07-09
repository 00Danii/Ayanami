import subprocess
import re
import nmap

scanner = nmap.PortScanner()

# ESCABEO RAPIDO DE DISPOSITIVOS - IP NEIGHBOR

def get_neighbors_simple():

    result = subprocess.check_output(
        "ip neigh",
        shell=True,
        text=True
    )

    devices = []

    for line in result.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        ip = parts[0]
        iface = parts[2]
        mac = "?"
        if "lladdr" in parts:
            mac = parts[
                parts.index("lladdr") + 1
            ]
            
        state = parts[-1]
        
        devices.append({
            "ip": ip,
            "mac": mac,
            "iface": iface,
            "state": state,
            "vendor": "Unknown"
        })

    return devices


# ENRIQUECIMIENTO DE DISPOSITIVOS CON ARP-SCAN

def enrich_devices(devices, iface):

    try:
        result = subprocess.check_output(
            f"sudo arp-scan --interface={iface} --localnet",
            shell=True,
            text=True
        )

    except:
        return devices

    vendors = {}

    for line in result.splitlines():
        match = re.match(
            r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-f:]+)\s+(.*)",
            line,
            re.I
        )
        if match:
            ip = match.group(1)
            vendor = match.group(3)
            vendors[ip] = vendor

    for device in devices:
        device["vendor"] = vendors.get(
            device["ip"],
            "Unknown"
        )

    return devices


# FINGERPRINTING DE HOSTS CON NMAP 

def fingerprint_host(ip):

    try:
        scanner.scan(
            hosts=ip,
            arguments="-Pn -T4 -F --version-light"
        )

        host = scanner[ip]

        data = {
            "hostname": host.hostname(),
            "state": host.state(),
            "os": "Unknown",
            "vendor": "Unknown",
            "ports": []
        }

        # OS
        if "osmatch" in host:
            matches = host["osmatch"]
            if matches:
                data["os"] = matches[0]["name"]

        # PORTS
        for proto in host.all_protocols():
            ports = host[proto].keys()
            for port in ports:
                service = host[proto][port]
                data["ports"].append({
                    "port": port,
                    "protocol": proto,
                    "service": service.get("name", "unknown"),
                    "product": service.get("product", ""),
                    "version": service.get("version", ""),
                    "extrainfo": service.get("extrainfo", ""),
                    "state": service["state"]
                })

        return data

    except Exception as e:
        return {
            "error": str(e)
        }