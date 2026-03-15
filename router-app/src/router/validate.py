import ipaddress


class ConfigError(RuntimeError):
    pass


def validate_config(config: dict) -> None:
    interfaces = config["interfaces"]

    if "lan" not in interfaces:
        raise ConfigError("interfaces.lan is required")

    if "wan" not in interfaces:
        raise ConfigError("interfaces.wan is required")

    lan = interfaces["lan"]

    try:
        subnet = ipaddress.ip_network(lan["subnet"], strict=False)
    except Exception:
        raise ConfigError("Invalid LAN subnet")
    
    try:
        lan_address = ipaddress.ip_interface(lan["address"])
    except Exception as exc:
        raise ConfigError("Invalid LAN interface address") from exc

    if lan_address.ip not in subnet:
        raise ConfigError("LAN address must be inside LAN subnet")

    nat = config["nat"]
    outbound_role = nat["outbound_interface"]
    if outbound_role not in interfaces:
        raise ConfigError(f"NAT outbound interface role is undefined: {outbound_role}")

    dhcp = config.get("dhcp")

    if dhcp and dhcp["enabled"]:
        interface_role = dhcp["interface"]
        if interface_role not in interfaces:
            raise ConfigError(f"DHCP interface role is undefined: {interface_role}")

        try:
            start = ipaddress.ip_address(dhcp["pool"]["start"])
            end = ipaddress.ip_address(dhcp["pool"]["end"])
        except Exception as exc:
            raise ConfigError("Invalid DHCP pool range") from exc

        if start.version != subnet.version or end.version != subnet.version:
            raise ConfigError("DHCP pool IP version must match LAN subnet")

        if start not in subnet or end not in subnet:
            raise ConfigError("DHCP pool must be inside LAN subnet")

        if int(start) > int(end):
            raise ConfigError("DHCP pool start must be less than or equal to pool end")

        try:
            router_ip = ipaddress.ip_address(dhcp["router"])
        except Exception as exc:
            raise ConfigError("Invalid DHCP router address") from exc

        if router_ip not in subnet:
            raise ConfigError("DHCP router address must be inside LAN subnet")
