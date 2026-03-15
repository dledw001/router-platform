import subprocess


def run_command(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def bring_interface_up(device: str) -> None:
    run_command(["ip", "link", "set", device, "up"])


def assign_address(device: str, address: str) -> None:
    run_command(["ip", "addr", "replace", address, "dev", device])
