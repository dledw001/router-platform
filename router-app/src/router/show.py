import os
import shutil
import socket
import subprocess
from pathlib import Path
from datetime import datetime

DNSMASQ_CONFIG_PATH = Path("/etc/dnsmasq.d/router.conf")
DNSMASQ_LEASES_PATH = Path("/var/lib/misc/dnsmasq.leases")
IPV4_FORWARD_PATH = Path("/proc/sys/net/ipv4/ip_forward")

SEARCH_DIRS = (Path("/usr/sbin"), Path("/usr/bin"), Path("/sbin"), Path("/bin"),)

def find_binary(name: str) -> Path | None:
    found = shutil.which(name)
    if found:
        return Path(found)

    for directory in SEARCH_DIRS:
        candidate = directory / name
        if candidate.exists() and os.access(candidate, os.X_OK):
            return candidate

    return None

def run_command(cmd: list[str]) -> str:
    executable = find_binary(cmd[0])
    if executable is None:
        raise RuntimeError(f"Command not found: {cmd[0]}")

    resolved_cmd = [str(executable), *cmd[1:]]
    result = subprocess.run(resolved_cmd, capture_output=True, text=True)

    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise RuntimeError(stderr or f"Command failed: {' '.join(cmd)}")

    return result.stdout.strip()

def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None

def get_hostname() -> str:
    return socket.gethostname()

def get_interfaces() -> str:
    return run_command(["ip", "-br", "addr"])

def get_default_route() -> str:
    return run_command(["ip", "route", "show", "default"])

def get_ipv4_forwarding() -> str:
    value = read_text(IPV4_FORWARD_PATH)
    if value is None:
        return "unavailable"
    return "enabled" if value == "1" else "disabled"

def get_firewall_nat() -> str:
    try:
        return run_command(["nft", "list", "table", "ip", "nat"])
    except RuntimeError as exc:
        message = str(exc)
        if "Operation not permitted" in message:
            return "unavailable (requires root)"
        return f"unavailable ({message})"

def get_dnsmasq_status() -> str:
    try:
        return run_command(["systemctl", "is-active", "dnsmasq"])
    except RuntimeError:
        return "inactive"

def get_dnsmasq_config() -> str:
    config = read_text(DNSMASQ_CONFIG_PATH)
    return config if config is not None else "unavailable"

def get_dhcp_leases() -> str:
    leases = read_text(DNSMASQ_LEASES_PATH)
    if not leases:
        return "none"

    rows: list[str] = []

    for line in leases.splitlines():
        parts = line.split()
        if len(parts) < 4:
            rows.append(line)
            continue

        expiry_epoch, mac, ip_addr, hostname = parts[:4]

        try:
            expiry = datetime.fromtimestamp(int(expiry_epoch)).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            expiry = expiry_epoch

        rows.append(f"{ip_addr:<15} {mac:<17} {hostname: <20} expires {expiry}")

    return "\n".join(rows)

def print_section(title: str, body: str) -> None:
    print(title)
    print(body)
    print()

def safe_get(getter) -> str:
    try:
        return getter()
    except Exception as exc:
        return f"unavailable ({exc})"

def main() -> None:
    print_section("Hostname", safe_get(get_hostname))
    print_section("Interfaces", safe_get(get_interfaces))
    print_section("Default Route", safe_get(get_default_route))
    print_section("IPv4 Forwarding", safe_get(get_ipv4_forwarding))
    print_section("Firewall", safe_get(get_firewall_nat))
    print_section("dnsmasq Status", safe_get(get_dnsmasq_status))
    print_section("dnsmasq Config", safe_get(get_dnsmasq_config))
    print_section("DHCP Leases", safe_get(get_dhcp_leases))


if __name__ == "__main__":
    main()
