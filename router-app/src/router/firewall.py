import subprocess


class FirewallError(RuntimeError):
    pass


def run_nft(cmd: list[str], *, ignore_exists: bool = False) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        return

    stderr = result.stderr.strip()

    if ignore_exists and "File exists" in stderr:
        return

    raise FirewallError(f"Command failed: {' '.join(cmd)}\n{stderr}")


def apply_nat_masquerade(wan_device: str) -> None:
    run_nft(["nft", "add", "table", "ip", "nat"], ignore_exists=True)

    run_nft(
        [
            "nft",
            "add",
            "chain",
            "ip",
            "nat",
            "postrouting",
            "{",
            "type",
            "nat",
            "hook",
            "postrouting",
            "priority",
            "100",
            ";",
            "}",
        ],
        ignore_exists=True,
    )

    run_nft(["nft", "flush", "chain", "ip", "nat", "postrouting"])
    run_nft(
        [
            "nft",
            "add",
            "rule",
            "ip",
            "nat",
            "postrouting",
            "oifname",
            wan_device,
            "masquerade",
        ]
    )
