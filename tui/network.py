import subprocess

def run(cmd):
    return subprocess.check_output(cmd, shell=True).decode()

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