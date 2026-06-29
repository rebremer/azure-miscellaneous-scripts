# Verifies that the FQDN registered on a Fabric Managed Private Endpoint resolves
# to the private IP allocated for the Private Link Service.
#
# Run this from a Fabric notebook (or any environment that sits inside the
# Fabric managed VNet) — running it from your laptop will resolve to a public
# IP (or NXDOMAIN), because the private DNS record only exists inside the MPE's VNet.

import socket

FQDN = "example.contoso.com"   # must match one of the TARGET_FQDNS you set on the MPE
PORT = 1433                    # TCP port the PLS / load balancer is listening on


def is_private_ip(ip: str) -> bool:
    octets = [int(o) for o in ip.split(".")]
    return (
        octets[0] == 10
        or (octets[0] == 172 and 16 <= octets[1] <= 31)
        or (octets[0] == 192 and octets[1] == 168)
    )


# 1) DNS resolution
ip = socket.gethostbyname(FQDN)
print(f"{FQDN} -> {ip}  (private={is_private_ip(ip)})")

# 2) TCP reachability over the private link
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.settimeout(5)
    try:
        s.connect((ip, PORT))
        print(f"TCP {FQDN}:{PORT} -> OPEN")
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        print(f"TCP {FQDN}:{PORT} -> CLOSED ({e})")
