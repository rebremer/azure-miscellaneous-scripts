"""
Create a Fabric Managed Private Endpoint (MPE) targeting an Azure Private Link Service (PLS).

Fixes the common error 'ManagedVNet_InvalidPrivateEndpointFqdns', which is raised
when targetPrivateLinkResourceId points at a PLS but no valid targetFqdns are
supplied. For PLS-backed MPEs, Fabric requires one or more FQDNs that workloads
will use to reach the service.

Prereqs:
    pip install requests
    az login   (to obtain a token for https://api.fabric.microsoft.com)
"""

import json
import subprocess
import sys

import requests

# --- Hardcoded configuration ------------------------------------------------
WORKSPACE_ID = "00000000-0000-0000-0000-000000000000"
PRIVATE_LINK_RESOURCE_ID = (
    "/subscriptions/00000000-0000-0000-0000-000000000000"
    "/resourceGroups/<resource-group>"
    "/providers/Microsoft.Network/privateLinkServices/<pls-name>"
)
TARGET_FQDNS = ["example.contoso.com"]
NAME = "example-mpe"
REQUEST_MESSAGE = "Managed private endpoint request from Fabric"
# ---------------------------------------------------------------------------


def get_fabric_token() -> str:
    """Acquire a bearer token for the Fabric API using the Azure CLI."""
    result = subprocess.run(
        [
            "az",
            "account",
            "get-access-token",
            "--resource",
            "https://api.fabric.microsoft.com",
        ],
        capture_output=True,
        text=True,
        shell=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to get Fabric token: {result.stderr.strip()}")
    return json.loads(result.stdout)["accessToken"]


def main() -> int:
    token = get_fabric_token()

    url = f"https://api.fabric.microsoft.com/v1/workspaces/{WORKSPACE_ID}/managedPrivateEndpoints"
    body = {
        "name": NAME,
        "targetPrivateLinkResourceId": PRIVATE_LINK_RESOURCE_ID,
        # For a PLS, leave targetSubresourceType empty — supplying a value
        # (e.g. "sql") for a PLS target also produces validation errors.
        "targetSubresourceType": "",
        "targetFqdns": TARGET_FQDNS,
        "requestMessage": REQUEST_MESSAGE,
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    print(f"POST {url}")
    print("Request body:")
    print(json.dumps(body, indent=2))

    response = requests.post(url, headers=headers, json=body, timeout=60)

    if response.ok:
        print("\nManaged private endpoint created (pending approval):")
        print(json.dumps(response.json(), indent=2))
        print(
            "\nNext step: approve the connection in Azure portal -> "
            "Private Link Service -> Private endpoint connections."
        )
        return 0

    print(f"\nRequest failed ({response.status_code}):", file=sys.stderr)
    print(response.text, file=sys.stderr)
    if "ManagedVNet_InvalidPrivateEndpointFqdns" in response.text:
        print(
            "\nHint: targetFqdns is missing/empty or contains invalid hostnames. "
            "Provide at least one FQDN (e.g. 'mydb.contoso.com') that workloads "
            "will use to reach the PLS.",
            file=sys.stderr,
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
