import tempfile
import shutil
import os
import sys
import argparse
from pathlib import Path

from router.config import load_config
from router.validate import validate_config
from router.interfaces import bring_interface_up, assign_address
from router.routing import set_ipv4_forwarding
from router.firewall import apply_nat_masquerade
from router.dhcp import (
    DNSMASQ_CONFIG_PATH,
    build_dnsmasq_config,
    write_dnsmasq_config,
    test_dnsmasq,
    restart_dnsmasq,
)

DEFAULT_CONFIG_PATH = Path("/etc/router/router.yaml")
REQUIRED_BINARIES = ("ip", "nft", "dnsmasq", "systemctl")
SEARCH_DIRS = (
    Path("/usr/sbin"),
    Path("/usr/bin"),
    Path("/sbin"),
    Path("/bin"),
)


class PreflightError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to router YAML config",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate config and runtime prerequisites without making changes",
    )
    return parser.parse_args()


def require_root() -> None:
    if os.geteuid() != 0:
        print(
            "ERROR: router-apply must be run as root. Try: sudo .venv/bin/router-apply",
            file=sys.stderr,
        )
        raise SystemExit(1)


def find_binary(name: str) -> Path | None:
    found = shutil.which(name)
    if found:
        return Path(found)

    for directory in SEARCH_DIRS:
        candidate = directory / name
        if candidate.exists() and os.access(candidate, os.X_OK):
            return candidate

    return None


def check_binaries() -> None:
    missing = [name for name in REQUIRED_BINARIES if find_binary(name) is None]
    if missing:
        missing_csv = ", ".join(missing)
        raise PreflightError(f"Missing required executables: {missing_csv}")


def check_interface_exists(device: str) -> None:
    if not Path("/sys/class/net", device).exists():
        raise PreflightError(f"Interface does not exist: {device}")


def preflight_dnsmasq(config: dict, dnsmasq_executable: Path) -> None:
    dnsmasq_conf = build_dnsmasq_config(config)

    with tempfile.TemporaryDirectory(prefix="router-dnsmasq-") as tmpdir:
        staged_path = Path(tmpdir) / DNSMASQ_CONFIG_PATH.name
        write_dnsmasq_config(dnsmasq_conf, path=staged_path)
        test_dnsmasq(config_path=staged_path, executable=dnsmasq_executable)


def run_preflight(config: dict) -> None:
    check_binaries()

    interfaces = config["interfaces"]
    wan_device: str | None = None
    dhcp_device: str | None = None

    lan = interfaces["lan"]
    check_interface_exists(lan["device"])

    nat = config["nat"]
    if nat["enabled"] and nat["masquerade"]:
        wan_role = nat["outbound_interface"]
        try:
            resolved_wan_device = interfaces[wan_role]["device"]
        except KeyError as exc:
            raise PreflightError(
                f"NAT outbound interface role is undefined: {wan_role}"
            ) from exc
        check_interface_exists(resolved_wan_device)
        wan_device = resolved_wan_device

    dhcp = config["dhcp"]
    if dhcp["enabled"]:
        dnsmasq_executable = find_binary("dnsmasq")
        if dnsmasq_executable is None:
            raise PreflightError("Missing required executable: dnsmasq")

        interface_role = dhcp["interface"]
        try:
            resolved_dhcp_device = interfaces[interface_role]["device"]
        except KeyError as exc:
            raise PreflightError(
                f"DHCP interface role is undefined: {interface_role}"
            ) from exc
        check_interface_exists(resolved_dhcp_device)
        dhcp_device = resolved_dhcp_device
        preflight_dnsmasq(config, dnsmasq_executable)

    print("Preflight OK")
    print(f"Config: {config['hostname']}")
    print(f"LAN interface: {lan['device']}")
    if wan_device is not None:
        print(f"NAT outbound interface: {wan_device}")
    if dhcp_device is not None:
        print(f"DHCP interface: {dhcp_device}")
        print("dnsmasq config test: passed")


def apply_config(config: dict) -> None:
    hostname = config["hostname"]
    lan = config["interfaces"]["lan"]
    lan_device = lan["device"]
    lan_address = lan["address"]

    print(f"Applying router config for {hostname}...")
    print(f"Configuring LAN interface {lan_device} with {lan_address}...")

    bring_interface_up(lan_device)
    assign_address(lan_device, lan_address)

    routing = config["routing"]
    if routing["ipv4_forward"]:
        print("Enabling IPv4 forwarding...")
        set_ipv4_forwarding(True)

    nat = config["nat"]
    if nat["enabled"] and nat["masquerade"]:
        wan_role = nat["outbound_interface"]
        wan_device = config["interfaces"][wan_role]["device"]
        print(f"Applying NAT masquerade on {wan_device}...")
        apply_nat_masquerade(wan_device)

    dhcp = config["dhcp"]
    if dhcp["enabled"]:
        print("Generated dnsmasq DHCP config...")
        dnsmasq_conf = build_dnsmasq_config(config)

        staged_path = DNSMASQ_CONFIG_PATH.with_suffix(".conf.tmp")
        write_dnsmasq_config(dnsmasq_conf, path=staged_path)

        print("Testing dnsmasq config...")
        test_dnsmasq(config_path=staged_path)

        print(f"Installing dnsmasq config to {DNSMASQ_CONFIG_PATH}...")
        staged_path.replace(DNSMASQ_CONFIG_PATH)

        print("Restarting dnsmasq...")
        restart_dnsmasq()

    print("Done.")


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    validate_config(config)

    if args.check:
        run_preflight(config)
        return

    require_root()
    apply_config(config)


if __name__ == "__main__":
    main()
