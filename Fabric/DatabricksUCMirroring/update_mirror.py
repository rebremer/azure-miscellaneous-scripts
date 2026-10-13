import subprocess
import requests
import json
import base64
import sys


# ============================================================
# CONFIGURATION
# ============================================================

WORKSPACE_ID = "YOUR-FABRIC-WORKSPACE-ID" # can be looked up the browser, first GUID when you select a workspace

# Item ID of the EXISTING Fabric Databricks UC mirror
ITEM_ID = "<<Item ID of the EXISTING Fabric Databricks UC mirror>>"

# Table to add
CATALOG_NAME = "catalog_1"
TABLE_NAME = "New table 2"


# ============================================================
# Get Fabric token from Azure CLI
#
# First run:
#   az login
# ============================================================

def get_fabric_token():

    # When I was testing this, I created a token using the following command from my own user:
    #
    # az account get-access-token --resource https://api.fabric.microsoft.com when using the Azure CLI
    #
    # And pasted this in the return statement below.

    return "<<Your-Fabric-Token-Here>>"


# ============================================================
# Get the EXISTING mirror definition
# ============================================================

def get_definition(token):

    url = (
        f"https://api.fabric.microsoft.com/v1/"
        f"workspaces/{WORKSPACE_ID}/"
        f"items/{ITEM_ID}/getDefinition"
    )

    headers = {
        "Authorization": f"Bearer {token}"
    }

    print()
    print("Getting existing mirror definition...")

    response = requests.post(
        url,
        headers=headers
    )

    print(f"HTTP status: {response.status_code}")

    if response.status_code == 202:
        print()
        print("Fabric returned 202 Accepted.")
        print("Getting the definition is running as a long-running operation.")
        print("Operation URL:", response.headers.get("Location"))
        sys.exit(0)

    if response.status_code != 200:
        print()
        print("ERROR retrieving definition:")
        print(response.text)
        response.raise_for_status()

    return response.json()


# ============================================================
# Decode definition.json
# ============================================================

def decode_definition(response_json):

    parts = response_json["definition"]["parts"]

    for part in parts:

        if part["path"] == "definition.json":

            encoded = part["payload"]

            decoded = base64.b64decode(
                encoded
            ).decode("utf-8")

            return json.loads(decoded)

    raise Exception(
        "definition.json was not found in the Fabric item definition."
    )


# ============================================================
# Add table
# ============================================================

def add_table(definition, schema_name, table_name):

    print()
    print(f"Adding table: {schema_name}.{table_name}")

    mirror_configuration = definition.get(
        "mirrorConfiguration"
    )

    if not mirror_configuration:
        raise Exception(
            "Existing definition does not contain mirrorConfiguration."
        )

    schemas = mirror_configuration.get(
        "schemas",
        []
    )

    # Find existing schema
    schema = next(
        (
            s for s in schemas
            if s.get("name") == schema_name
        ),
        None
    )

    if schema is None:
        raise Exception(
            f"Schema '{schema_name}' is not currently "
            f"present in mirrorConfiguration."
        )

    # This script is intended for a Partial schema,
    # where explicitly selected tables are listed.
    if schema.get("mirroringMode") != "Partial":
        raise Exception(
            f"Schema '{schema_name}' has mirroringMode "
            f"'{schema.get('mirroringMode')}', not 'Partial'. "
            f"No explicit table addition was performed."
        )

    tables = schema.setdefault(
        "tables",
        []
    )

    # Check whether table already exists
    existing_table = next(
        (
            t for t in tables
            if t.get("name") == table_name
        ),
        None
    )

    if existing_table:

        print(
            f"Table '{schema_name}.{table_name}' "
            f"is already in the mirror configuration."
        )

        return False

    # Add new table
    tables.append(
        {
            "name": table_name,
            "mirroringMode": "Full"
        }
    )

    print(
        f"Added '{schema_name}.{table_name}' "
        f"to the definition."
    )

    return True


# ============================================================
# Encode updated definition
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
# Update existing Fabric item definition
# ============================================================

def update_definition(token, encoded_definition):

    url = (
        f"https://api.fabric.microsoft.com/v1/"
        f"workspaces/{WORKSPACE_ID}/"
        f"items/{ITEM_ID}/updateDefinition"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
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

    print()
    print("Updating existing mirror definition...")

    response = requests.post(
        url,
        headers=headers,
        json=payload
    )

    print(f"HTTP status: {response.status_code}")

    if response.status_code == 200:

        print()
        print("Mirror definition updated successfully.")

        return

    if response.status_code == 202:

        print()
        print("Update accepted by Fabric.")
        print("The update is running as a long-running operation.")

        operation_id = response.headers.get(
            "x-ms-operation-id"
        )

        operation_url = response.headers.get(
            "Location"
        )

        if operation_id:
            print("Operation ID:", operation_id)

        if operation_url:
            print("Operation URL:", operation_url)

        return

    print()
    print("ERROR updating mirror definition:")
    print(response.text)

    response.raise_for_status()


# ============================================================
# Main
# ============================================================

def main():

    token = get_fabric_token()

    # 1. Get current definition
    response_json = get_definition(token)

    # 2. Decode definition.json
    definition = decode_definition(
        response_json
    )

    print()
    print("Current definition:")
    print(
        json.dumps(
            definition,
            indent=2
        )
    )

    # 3. Add employee while preserving existing tables
    changed = add_table(
        definition,
        SCHEMA_NAME,
        TABLE_NAME
    )

    if not changed:
        print("Nothing to update.")
        return

    print()
    print("New definition:")
    print(
        json.dumps(
            definition,
            indent=2
        )
    )

    # 4. Base64 encode updated definition
    encoded_definition = encode_definition(
        definition
    )

    # 5. Update EXISTING Fabric item
    update_definition(
        token,
        encoded_definition
    )


if __name__ == "__main__":
    main()
