import base64
import json
import sys

from update_mirror import FABRIC_API_ROOT, fabric_post, get_fabric_token

# ============================================================
# CONFIGURATION
# ============================================================

WORKSPACE_ID = "YOUR-FABRIC-WORKSPACE-ID" # can be looked up the browser, first GUID when you select a workspace

DATABRICKS_CONNECTION_ID = "YOUR-DATABRICKS-WORKSPACE-CONNECTION-ID" # Go to "mangage and create connections, select connection that you want to connect to Databricks and copy ID

DISPLAY_NAME = "test_Databricks_UC_Mirror"

CATALOG_NAME = "catalog_1"
SCHEMA_NAME = "schema_3"
TABLE_NAME = ["table_1", "table_2"]

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
