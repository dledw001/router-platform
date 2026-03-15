from pathlib import Path
import subprocess

DNSMASQ_CONFIG_PATH = Path("/etc/dnsmasq.d/router.conf")


class DhcpError(RuntimeError):
    pass


def build_dnsmasq_config(config: dict) -> str:
    dhcp = config["dhcp"]
    interfaces = config["interfaces"]

    interface_role = dhcp["interface"]
    lan_device = interfaces[interface_role]["device"]

    start = dhcp["pool"]["start"]
    end = dhcp["pool"]["end"]

    router_ip = dhcp["router"]
    lease_time = dhcp.get("lease_time", "12h")

    lines = [
        f"interface={lan_device}",
        "bind-interfaces",
        "",
        f"dhcp-range={start},{end},{lease_time}",
        f"dhcp-option=3,{router_ip}",
        f"dhcp-option=6,{router_ip}",
        "",
    ]
    return "\n".join(lines)


def test_dnsmasq(
    config_path: Path = DNSMASQ_CONFIG_PATH, executable: str | Path = "dnsmasq"
) -> None:
    result = subprocess.run(
        [str(executable), "--test", f"--conf-file={config_path}"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise DhcpError(result.stderr.strip() or result.stdout.strip())


def write_dnsmasq_config(config_text: str, path: Path = DNSMASQ_CONFIG_PATH) -> None:
    path.write_text(config_text, encoding="utf-8")


def restart_dnsmasq() -> None:
    result = subprocess.run(
        ["systemctl", "restart", "dnsmasq"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise DhcpError(result.stderr.strip() or "Failed to restart dnsmasq")
