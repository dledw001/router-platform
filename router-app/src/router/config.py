from pathlib import Path
import yaml


def load_config(path: str | Path) -> dict:
    path = Path(path)

    with path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict):
        raise ValueError(f"Config file must contain a YAML mapping: {path}")

    required_top = ["hostname", "interfaces", "routing", "nat", "dhcp"]
    for key in required_top:
        if key not in config:
            raise ValueError(f"Missing required top-level key: {key}")

    return config
