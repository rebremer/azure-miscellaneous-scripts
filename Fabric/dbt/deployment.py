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


def _b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("utf-8")


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


def _list_items(token: str, ws_id: str) -> list:
    resp = http.get(f"{FABRIC_API}/workspaces/{ws_id}/items", headers=_headers(token))
    resp.raise_for_status()
    return resp.json().get("value", [])


def _ensure_item(token: str, ws_id: str, name: str, item_type: str,
                 creation_type: str | None = None) -> dict:
    """Return existing item or create it. creation_type overrides type for the POST."""
    items = _list_items(token, ws_id)
    for item in items:
        if item["displayName"] == name and item["type"] == item_type:
            print(f"   {name} already exists: {item['id']}")
            return item
    resp = http.post(f"{FABRIC_API}/workspaces/{ws_id}/items", headers=_headers(token),
                     json={"displayName": name, "type": creation_type or item_type})
    resp.raise_for_status()
    _wait_lro(token, resp)
    # Fetch the created item
    items = _list_items(token, ws_id)
    for item in items:
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
                with open(filepath, "r", encoding="utf-8") as f:
                    parts.append({"path": rel, "payload": _b64(f.read()),
                                  "payloadType": "InlineBase64"})
    return parts


def deploy(workspace_name: str):
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Discover items
    discovered = _discover_items(script_dir)
    warehouses = discovered.get("Warehouse", [])
    dbt_jobs = discovered.get("DataBuildToolJob", [])
    if len(warehouses) != 1 or len(dbt_jobs) != 1:
        raise SystemExit(f"Expected 1 Warehouse and 1 DataBuildToolJob, "
                         f"found {len(warehouses)} and {len(dbt_jobs)}.")
    dwh_info, dbt_info = warehouses[0], dbt_jobs[0]
    print(f"Deploying to workspace '{workspace_name}'")
    print(f"  Warehouse: {dwh_info['displayName']}, dbt job: {dbt_info['displayName']}")

    # Authenticate
    token = AzureCliCredential().get_token("https://api.fabric.microsoft.com/.default").token
    ws_id = _find_workspace(token, workspace_name)

    # Deploy warehouse
    print(f"\nDeploying Warehouse '{dwh_info['displayName']}'...")
    dwh = _ensure_item(token, ws_id, dwh_info["displayName"], "Warehouse")
    dwh_id = dwh["id"]

    # Wait for warehouse endpoint
    print("   Waiting for warehouse provisioning...")
    for _ in range(12):
        try:
            resp = http.get(f"{FABRIC_API}/workspaces/{ws_id}/warehouses/{dwh_id}",
                            headers=_headers(token))
            resp.raise_for_status()
            endpoint = resp.json().get("properties", {}).get("connectionString")
            if endpoint:
                break
        except Exception:
            pass
        time.sleep(5)
    else:
        raise SystemExit("Warehouse did not become ready within 60 seconds.")
    print(f"   Endpoint: {endpoint}")

    # Deploy dbt job
    dbt_name = dbt_info["displayName"]
    print(f"\nDeploying dbt job '{dbt_name}'...")
    dbt = _ensure_item(token, ws_id, dbt_name, "DataBuildToolJob", creation_type="DbtItem")

    # Upload definition
    parts = _collect_parts(dbt_info["folder"], ws_id, dwh_id, endpoint)
    print(f"   Uploading dbt-content.json + {len(parts) - 1} code file(s)...")
    body = {"definition": {"parts": parts}}
    resp = http.post(f"{FABRIC_API}/workspaces/{ws_id}/items/{dbt['id']}/updateDefinition",
                     headers=_headers(token), json=body)
    resp.raise_for_status()
    _wait_lro(token, resp)

    print("\nDeployment complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy Fabric dbt job and DWH.")
    parser.add_argument("--workspace", default="testAgenticAIdeployment",
                        help="Target Fabric workspace name")
    deploy(parser.parse_args().workspace)
