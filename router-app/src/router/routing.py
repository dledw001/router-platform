from pathlib import Path

IPV4_FORWARD_PATH = Path("/proc/sys/net/ipv4/ip_forward")


def set_ipv4_forwarding(enabled: bool) -> None:
    value = "1" if enabled else "0"
    IPV4_FORWARD_PATH.write_text(value, encoding="utf-8")


def get_ipv4_forwarding() -> bool:
    return IPV4_FORWARD_PATH.read_text(encoding="utf-8").strip() == "1"
