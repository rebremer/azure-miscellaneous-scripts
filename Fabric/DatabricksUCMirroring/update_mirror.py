import base64
import json
import shutil
import subprocess
import sys
import time

import requests

# ============================================================
# CONFIGURATION
# ============================================================

WORKSPACE_ID = "YOUR-FABRIC-WORKSPACE-ID" # can be looked up the browser, first GUID when you select a workspace

# Item ID of the EXISTING Fabric Databricks UC mirror
ITEM_ID = "<<Item ID of the EXISTING Fabric Databricks UC mirror>>"

TABLE_OPERATION = "add"
# Table to add
CATALOG_NAME = "catalog_1"
TABLE_NAME = "New table 2"

MAX_POLL_ATTEMPTS = 120
FABRIC_API_ROOT = "https://api.fabric.microsoft.com/v1"
ITEM_URL = f"{FABRIC_API_ROOT}/workspaces/{WORKSPACE_ID}/items/{ITEM_ID}"


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


# ============================================================
# Definition helpers
# ============================================================

def get_definition(token):
    """Return (all definition parts, parsed definition.json, its part)."""
    print("Retrieving current mirror definition...")

    response = fabric_post(
        token,
        f"{ITEM_URL}/getDefinition",
        expect_result=True,
    )

    parts = response["definition"]["parts"]
    part = next(p for p in parts if p["path"] == "definition.json")

    if part.get("payloadType") != "InlineBase64":
        raise RuntimeError("definition.json does not use InlineBase64.")

    definition = json.loads(base64.b64decode(part["payload"]))

    return parts, definition, part


def find_schema(definition, schema_name):
    schemas = definition["mirrorConfiguration"]["schemas"]

    return next(
        (s for s in schemas if s.get("name") == schema_name),
        None,
    )


def table_is_selected(definition, schema_name, table_name):
    schema = find_schema(definition, schema_name)

    if schema is None:
        return False

    mode = next(
        (
            t.get("mirroringMode")
            for t in schema.get("tables", [])
            if t.get("name") == table_name
        ),
        None,
    )

    if schema.get("mirroringMode") == "Full":
        return mode != "Exclude"

    return schema.get("mirroringMode") == "Partial" and mode == "Full"


def set_table_selected(definition, schema_name, table_name, selected):
    """Select or deselect a table. Returns True if the definition changed.

    Partial schema: a table is selected by an explicit 'Full' entry.
    Full schema:    a table is selected unless it has an 'Exclude' entry.
    """
    if definition.get("mirroringMode") != "Partial":
        raise RuntimeError(
            f"The catalog mirroringMode is "
            f"'{definition.get('mirroringMode')}', not 'Partial'. "
            "This script only modifies an explicit Partial selection."
        )

    schema = find_schema(definition, schema_name)

    if schema is None:
        raise RuntimeError(
            f"Schema '{schema_name}' was not found in the current "
            "mirrorConfiguration."
        )

    schema_mode = schema.get("mirroringMode")

    if schema_mode not in {"Full", "Partial"}:
        raise RuntimeError(
            f"Schema '{schema_name}' has mirroringMode "
            f"'{schema_mode}', not 'Full' or 'Partial'."
        )

    if table_is_selected(definition, schema_name, table_name) == selected:
        print(
            f"'{schema_name}.{table_name}' is already "
            f"{'selected' if selected else 'not selected'}."
        )
        return False

    tables = schema.setdefault("tables", [])
    entry = next((t for t in tables if t.get("name") == table_name), None)

    # The entry that represents the desired state, or None if the
    # desired state is expressed by having no entry at all.
    wanted_mode = "Full" if schema_mode == "Partial" else "Exclude"
    needs_entry = selected == (schema_mode == "Partial")

    if not needs_entry:
        if entry is not None:
            tables.remove(entry)
    elif entry is not None:
        entry["mirroringMode"] = wanted_mode
    else:
        tables.append({"name": table_name, "mirroringMode": wanted_mode})

    return True


def update_definition(token, parts, definition, part):
    part["payload"] = base64.b64encode(
        json.dumps(
            definition,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).decode("ascii")
    part["payloadType"] = "InlineBase64"

    print("Submitting updated definition...")

    # All returned parts are sent back, not only definition.json.
    fabric_post(
        token,
        f"{ITEM_URL}/updateDefinition",
        payload={"definition": {"parts": parts}},
    )


# ============================================================
# Main
# ============================================================

def main():
    operation = TABLE_OPERATION.strip().lower()

    if operation not in {"add", "delete"}:
        raise RuntimeError(
            f"TABLE_OPERATION is '{TABLE_OPERATION}'. Use 'add' or 'delete'."
        )

    selected = operation == "add"
    full_name = f"{SCHEMA_NAME}.{TABLE_NAME}"

    token = get_fabric_token()

    parts, definition, part = get_definition(token)

    if not set_table_selected(
        definition,
        SCHEMA_NAME,
        TABLE_NAME,
        selected,
    ):
        print("No definition update is required.")
        return

    print(json.dumps(definition, indent=2, ensure_ascii=False))

    update_definition(token, parts, definition, part)

    # Verify the persisted definition.
    _, verified, _ = get_definition(token)

    if table_is_selected(verified, SCHEMA_NAME, TABLE_NAME) != selected:
        raise RuntimeError(
            f"The update succeeded, but '{full_name}' is not "
            f"{'selected' if selected else 'deselected'} in the "
            "retrieved definition."
        )

    print(
        f"Verification succeeded: '{full_name}' is "
        f"{'selected' if selected else 'not selected'}."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ERROR: {error}")
        sys.exit(1)
