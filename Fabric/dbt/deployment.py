"""
Deployment script for Fabric dbt job and Data Warehouse.

Deploys items from the local folder structure to a Fabric workspace using the
Fabric REST API. Item names and types are auto-discovered from .platform files.
The dbt-content.json connection details are resolved at deploy time.

Usage:
    python deployment.py --workspace "testAgenticAIdeployment"

Prerequisites:
    - Azure CLI logged in (az login)
    - pip install azure-identity requests
"""

import argparse
import base64
import json
import os
import time

import requests
from azure.identity import AzureCliCredential
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

FABRIC_API = "https://api.fabric.microsoft.com/v1"

http = requests.Session()
_retries = Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504],
                 allowed_methods=["GET", "POST"])
http.mount("https://", HTTPAdapter(max_retries=_retries))


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _b64(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return base64.b64encode(data).decode("utf-8")


def _wait_lro(token: str, resp: requests.Response):
    if resp.status_code != 202:
        return
    op_id = resp.headers.get("x-ms-operation-id")
    if not op_id:
        return
    delay = int(resp.headers.get("Retry-After", 5))
    while True:
        time.sleep(delay)
        poll = http.get(f"{FABRIC_API}/operations/{op_id}", headers=_headers(token))
        if poll.status_code != 200:
            break
        status = poll.json().get("status", "")
        if status in ("Succeeded", "Completed"):
            break
        if status in ("Failed", "Cancelled"):
            raise SystemExit(f"Operation failed: {poll.json()}")


def _find_workspace(token: str, name: str) -> str:
    resp = http.get(f"{FABRIC_API}/workspaces", headers=_headers(token))
    resp.raise_for_status()
    for ws in resp.json().get("value", []):
        if ws["displayName"] == name:
            return ws["id"]
    raise SystemExit(f"Workspace '{name}' not found.")


def _ensure_item(token: str, ws_id: str, name: str, item_type: str,
                 creation_type: str | None = None) -> dict:
    """Return existing item by displayName or create it."""
    resp = http.get(f"{FABRIC_API}/workspaces/{ws_id}/items", headers=_headers(token))
    resp.raise_for_status()
    for item in resp.json().get("value", []):
        if item["displayName"] == name and item["type"] == item_type:
            print(f"   {name} already exists: {item['id']}")
            return item
    resp = http.post(f"{FABRIC_API}/workspaces/{ws_id}/items", headers=_headers(token),
                     json={"displayName": name, "type": creation_type or item_type})
    resp.raise_for_status()
    _wait_lro(token, resp)
    resp = http.get(f"{FABRIC_API}/workspaces/{ws_id}/items", headers=_headers(token))
    resp.raise_for_status()
    for item in resp.json().get("value", []):
        if item["displayName"] == name and item["type"] == item_type:
            print(f"   {name} created: {item['id']}")
            return item
    raise SystemExit(f"Failed to find '{name}' after creation.")


def _discover_items(root_dir: str) -> dict:
    """Scan for .platform files. Returns {type: [{displayName, folder}]}."""
    items = {}
    for dirpath, _, filenames in os.walk(root_dir):
        if ".platform" not in filenames:
            continue
        with open(os.path.join(dirpath, ".platform"), encoding="utf-8") as f:
            meta = json.load(f).get("metadata", {})
        if meta.get("type") and meta.get("displayName"):
            items.setdefault(meta["type"], []).append(
                {"displayName": meta["displayName"], "folder": dirpath})
    return items


def _collect_parts(dbt_folder: str, ws_id: str, dwh_id: str, endpoint: str) -> list:
    """Build the definition parts list: dbt-content.json + all Code/ files."""
    # Resolve dbt-content.json with actual connection details
    with open(os.path.join(dbt_folder, "dbt-content.json"), encoding="utf-8") as f:
        content = json.load(f)
    tp = content["profile"]["connectionSettings"]["properties"]["typeProperties"]
    tp["workspaceId"] = ws_id
    tp["artifactId"] = dwh_id
    tp["endPoint"] = endpoint

    parts = [{"path": "dbt-content.json", "payload": _b64(json.dumps(content, indent=2)),
              "payloadType": "InlineBase64"}]

    code_dir = os.path.join(dbt_folder, "Code")
    if os.path.isdir(code_dir):
        for root, _, files in os.walk(code_dir):
            for name in files:
                filepath = os.path.join(root, name)
                rel = os.path.relpath(filepath, dbt_folder).replace("\\", "/")
                with open(filepath, "rb") as f:
                    parts.append({"path": rel, "payload": _b64(f.read()),
                                  "payloadType": "InlineBase64"})
    return parts


def _wait_for_endpoint(token: str, ws_id: str, dwh_id: str) -> str:
    """Poll until the warehouse endpoint is available."""
    for _ in range(12):
        try:
            resp = http.get(f"{FABRIC_API}/workspaces/{ws_id}/warehouses/{dwh_id}",
                            headers=_headers(token))
            resp.raise_for_status()
            endpoint = resp.json().get("properties", {}).get("connectionString")
            if endpoint:
                return endpoint
        except Exception:
            pass
        time.sleep(5)
    raise SystemExit("Warehouse did not become ready within 60 seconds.")


def deploy(workspace_name: str):
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Discover items from .platform files
    discovered = _discover_items(script_dir)
    warehouses = discovered.get("Warehouse", [])
    dbt_jobs = discovered.get("DataBuildToolJob", [])
    if not warehouses or not dbt_jobs:
        raise SystemExit(f"Expected at least 1 Warehouse and 1 DataBuildToolJob, "
                         f"found {len(warehouses)} and {len(dbt_jobs)}.")

    # Authenticate
    token = AzureCliCredential().get_token("https://api.fabric.microsoft.com/.default").token
    ws_id = _find_workspace(token, workspace_name)
    print(f"Deploying to workspace '{workspace_name}' ({ws_id})")

    # Deploy all warehouses and record runtime IDs/endpoints by name
    deployed_warehouses = {}
    for wh in warehouses:
        print(f"\nDeploying Warehouse '{wh['displayName']}'...")
        item = _ensure_item(token, ws_id, wh["displayName"], "Warehouse")
        print("   Waiting for warehouse provisioning...")
        endpoint = _wait_for_endpoint(token, ws_id, item["id"])
        print(f"   Endpoint: {endpoint}")
        deployed_warehouses[wh["displayName"]] = {"id": item["id"], "endpoint": endpoint}

    # Deploy each dbt job, resolving its warehouse by connection name
    for dbt_info in dbt_jobs:
        with open(os.path.join(dbt_info["folder"], "dbt-content.json"), encoding="utf-8") as f:
            dbt_content = json.load(f)
        dwh_name = dbt_content["profile"]["connectionSettings"]["name"]
        if dwh_name not in deployed_warehouses:
            raise SystemExit(
                f"dbt job '{dbt_info['displayName']}' references warehouse "
                f"'{dwh_name}' which was not found.")
        dwh = deployed_warehouses[dwh_name]

        print(f"\nDeploying dbt job '{dbt_info['displayName']}'...")
        item = _ensure_item(token, ws_id, dbt_info["displayName"],
                            "DataBuildToolJob", creation_type="DbtItem")

        parts = _collect_parts(dbt_info["folder"], ws_id, dwh["id"], dwh["endpoint"])
        print(f"   Uploading dbt-content.json + {len(parts) - 1} code file(s)...")
        resp = http.post(
            f"{FABRIC_API}/workspaces/{ws_id}/items/{item['id']}/updateDefinition",
            headers=_headers(token), json={"definition": {"parts": parts}})
        resp.raise_for_status()
        _wait_lro(token, resp)

    print("\nDeployment complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy Fabric dbt job and DWH.")
    parser.add_argument("--workspace", default="testAgenticAIdeployment",
                        help="Target Fabric workspace name")
    deploy(parser.parse_args().workspace)
