import subprocess
import json
import base64
import requests
import sys


# ============================================================
# CONFIGURATION - change these values
# ============================================================

WORKSPACE_ID = "YOUR-FABRIC-WORKSPACE-ID" # can be looked up the browser, first GUID when you select a workspace

DATABRICKS_CONNECTION_ID = "YOUR-DATABRICKS-WORKSPACE-CONNECTION-ID" # Go to "mangage and create connections, select connection that you want to connect to Databricks and copy ID

DISPLAY_NAME = "test_Databricks_UC_Mirror"

CATALOG_NAME = "catalog_1"
SCHEMA_NAME = "schema_3"
TABLE_NAME = "table_1"


# ============================================================
# Get Fabric token from Azure CLI
# Assumes you have already run:
#
#     az login
#
# ============================================================

def get_fabric_token():

    # When I was testing this, I created a token using the following command from my own user:
    #
    # az account get-access-token --resource https://api.fabric.microsoft.com when using the Azure CLI
    #
    # And pasted this in the return statement below.

    return "<<Your-Fabric-Token-Here>>"
    
 

# ============================================================
# Build Mirrored Azure Databricks Catalog definition
#
# Catalog -> Partial
#   Schema -> Partial
#       Table -> Full
#
# This selects the particular table for mirroring.
# ============================================================

def build_definition():

    return {
        "$schema": (
            "https://developer.microsoft.com/json-schemas/fabric/item/"
            "mirroredAzureDatabricksCatalog/definition/"
            "mirroredAzureDatabricksCatalogDefinition/1.0.0/schema.json"
        ),

        "catalogName": CATALOG_NAME,

        "databricksWorkspaceConnectionId":
            DATABRICKS_CONNECTION_ID,

        "autoSync": "Enabled",

        "mirroringMode": "Partial",

        "mirrorConfiguration": {
            "schemas": [
                {
                    "name": SCHEMA_NAME,

                    "mirroringMode": "Partial",

                    "tables": [
                        {
                            "name": TABLE_NAME,
                            "mirroringMode": "Full"
                        }
                    ]
                }
            ]
        }
    }


# ============================================================
# Convert JSON definition to Base64
# ============================================================

def encode_definition(definition):

    definition_json = json.dumps(
        definition,
        separators=(",", ":")
    )

    return base64.b64encode(
        definition_json.encode("utf-8")
    ).decode("utf-8")


# ============================================================
# Create the Fabric Mirrored Azure Databricks Catalog
# ============================================================

def create_mirror():

    token = get_fabric_token()

    definition = build_definition()

    encoded_definition = encode_definition(definition)

    payload = {

        "displayName": DISPLAY_NAME,

        "description": (
            f"Mirror of "
            f"{CATALOG_NAME}.{SCHEMA_NAME}.{TABLE_NAME}"
        ),

        "definition": {

            "parts": [

                {
                    "path": "definition.json",
                    "payload": encoded_definition,
                    "payloadType": "InlineBase64"
                }

            ]
        }
    }

    url = (
        f"https://api.fabric.microsoft.com/v1/"
        f"workspaces/{WORKSPACE_ID}/"
        f"mirroredAzureDatabricksCatalogs"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    print()
    print("Creating mirrored Databricks catalog...")
    print()
    print(f"Catalog : {CATALOG_NAME}")
    print(f"Schema  : {SCHEMA_NAME}")
    print(f"Table   : {TABLE_NAME}")
    print()

    response = requests.post(
        url,
        headers=headers,
        json=payload
    )

    print(f"HTTP status: {response.status_code}")

    # --------------------------------------------------------
    # Successful synchronous creation
    # --------------------------------------------------------

    if response.status_code == 201:

        print()
        print("Mirror created successfully.")

        try:
            print(
                json.dumps(
                    response.json(),
                    indent=2
                )
            )
        except ValueError:
            print(response.text)

        return

    # --------------------------------------------------------
    # Long-running Fabric operation
    # --------------------------------------------------------

    if response.status_code == 202:

        print()
        print("Mirror creation accepted.")
        print("Fabric is provisioning the item.")

        operation_url = response.headers.get("Location")
        operation_id = response.headers.get(
            "x-ms-operation-id"
        )

        if operation_id:
            print(f"Operation ID: {operation_id}")

        if operation_url:
            print(f"Operation URL: {operation_url}")

        return

    # --------------------------------------------------------
    # Error
    # --------------------------------------------------------

    print()
    print("ERROR creating mirror.")
    print()

    try:
        print(
            json.dumps(
                response.json(),
                indent=2
            )
        )
    except ValueError:
        print(response.text)

    response.raise_for_status()


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":

    create_mirror()
