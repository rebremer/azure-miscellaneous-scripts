import base64
import json
import shutil
import subprocess
import sys
import time

import requests

FABRIC_API_ROOT = "https://api.fabric.microsoft.com/v1"
MAX_POLL_ATTEMPTS = 120

# ============================================================
# CONFIGURATION
# ============================================================

WORKSPACE_ID = "YOUR-FABRIC-WORKSPACE-ID" # can be looked up the browser, first GUID when you select a workspace

DATABRICKS_CONNECTION_ID = "YOUR-DATABRICKS-WORKSPACE-CONNECTION-ID" # Go to "mangage and create connections, select connection that you want to connect to Databricks and copy ID

DISPLAY_NAME = "test_Databricks_UC_Mirror"

CATALOG_NAME = "catalog_1"
SCHEMA_NAME = "schema_3"
TABLE_NAME = ["table_1", "table_2"]

# ============================================================
# Authentication (run 'az login' first)
# ============================================================

def get_fabric_token():
    azure_cli = (
        shutil.which("az")
        or r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"
    )

    try:
        result = subprocess.run(
            [
                azure_cli,
                "account",
                "get-access-token",
                "--resource",
                "https://api.fabric.microsoft.com",
                "--query",
                "accessToken",
                "--output",
                "tsv",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        detail = getattr(error, "stderr", None) or error
        raise RuntimeError(
            f"Could not get a token from Azure CLI ({detail}). "
            "Run 'az login' and try again."
        ) from error

    return result.stdout.strip()


# ============================================================
# Fabric HTTP helper with long-running-operation (LRO) support
# ============================================================

def get_with_retry(url, headers, attempts=5):
    # Transient network errors should not abort an operation that
    # Fabric has already accepted.
    for attempt in range(1, attempts + 1):
        try:
            return requests.get(url, headers=headers, timeout=60)
        except (requests.ConnectionError, requests.Timeout) as error:
            if attempt == attempts:
                raise
            print(f"Network error ({type(error).__name__}); retrying...")
            time.sleep(5 * attempt)


def fabric_post(token, url, payload=None, expect_result=False):
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=60,
    )

    if response.status_code in {200, 201}:
        return response.json() if response.content else None

    if response.status_code != 202:
        raise RuntimeError(
            f"Fabric request failed (HTTP {response.status_code}): "
            f"{response.text}"
        )

    operation_url = (
        f"{FABRIC_API_ROOT}/operations/"
        f"{response.headers['x-ms-operation-id']}"
    )

    for _ in range(MAX_POLL_ATTEMPTS):
        state_response = get_with_retry(operation_url, headers)
        state_response.raise_for_status()

        state = state_response.json()
        status = state.get("status", "Unknown")
        print(f"Operation status: {status}")

        if status == "Succeeded":
            break

        if status in {"Failed", "Cancelled", "Canceled"}:
            raise RuntimeError(
                f"Fabric operation {status}: {json.dumps(state)}"
            )

        retry_after = state_response.headers.get("Retry-After", "5")
        time.sleep(max(1, int(retry_after)) if retry_after.isdigit() else 5)
    else:
        raise TimeoutError(
            f"Fabric operation did not finish after "
            f"{MAX_POLL_ATTEMPTS} status checks."
        )

    if not expect_result:
        return None

    result_response = get_with_retry(f"{operation_url}/result", headers)
    result_response.raise_for_status()

    return result_response.json()


def build_definition():
    # Catalog (Partial) -> Schema (Partial) -> Tables (Full)
    return {
        "$schema": (
            "https://developer.microsoft.com/json-schemas/fabric/item/"
            "mirroredAzureDatabricksCatalog/definition/"
            "mirroredAzureDatabricksCatalogDefinition/1.0.0/schema.json"
        ),
        "catalogName": CATALOG_NAME,
        "databricksWorkspaceConnectionId": DATABRICKS_CONNECTION_ID,
        "autoSync": "Enabled",
        "mirroringMode": "Partial",
        "mirrorConfiguration": {
            "schemas": [
                {
                    "name": SCHEMA_NAME,
                    "mirroringMode": "Partial",
                    "tables": [
                        {"name": name, "mirroringMode": "Full"}
                        for name in TABLE_NAMES
                    ],
                }
            ]
        },
    }


def create_mirror():
    token = get_fabric_token()

    encoded_definition = base64.b64encode(
        json.dumps(build_definition(), separators=(",", ":")).encode("utf-8")
    ).decode("ascii")

    payload = {
        "displayName": DISPLAY_NAME,
        "description": (
            f"Mirror of {CATALOG_NAME}.{SCHEMA_NAME} "
            f"({', '.join(TABLE_NAMES)})"
        ),
        "definition": {
            "parts": [
                {
                    "path": "definition.json",
                    "payload": encoded_definition,
                    "payloadType": "InlineBase64",
                }
            ]
        },
    }

    print(f"Creating mirror '{DISPLAY_NAME}' for {CATALOG_NAME}.{SCHEMA_NAME}")
    print(f"Tables: {', '.join(TABLE_NAMES)}")

    item = fabric_post(
        token,
        f"{FABRIC_API_ROOT}/workspaces/{WORKSPACE_ID}"
        "/mirroredAzureDatabricksCatalogs",
        payload=payload,
        expect_result=True,
    )

    print("Mirror created successfully.")
    print(json.dumps(item, indent=2))


if __name__ == "__main__":
    try:
        create_mirror()
    except Exception as error:
        print(f"ERROR: {error}")
        sys.exit(1)
