import base64
import json
import sys
from pathlib import Path

from update_mirror import FABRIC_API_ROOT, fabric_post, get_fabric_token

# ============================================================
# CONFIGURATION
# ============================================================

WORKSPACE_ID = "YOUR-FABRIC-WORKSPACE-ID" # can be looked up the browser, first GUID when you select a workspace

# Item ID of the EXISTING Fabric Databricks UC mirror
ITEM_ID = "<<Item ID of the EXISTING Fabric Databricks UC mirror>>"

# Optional: also write the decoded definition parts to this folder.
OUTPUT_DIR = None


def get_mirror_definition(token):
    url = (
        f"{FABRIC_API_ROOT}/workspaces/"
        f"{WORKSPACE_ID}/mirroredAzureDatabricksCatalogs/"
        f"{MIRROR_ID}/getDefinition"
    )

    print("Retrieving mirror definition...")

    return fabric_post(token, url, expect_result=True)


def decode_part(part):
    if part.get("payloadType") != "InlineBase64":
        return part.get("payload")

    text = base64.b64decode(part["payload"]).decode("utf-8")

    try:
        return json.dumps(json.loads(text), indent=2, ensure_ascii=False)
    except ValueError:
        return text


def main():
    token = get_fabric_token()

    response = get_mirror_definition(token)

    for part in response["definition"]["parts"]:
        print()
        print(f"--- {part['path']} ---")
        print(decode_part(part))

        if OUTPUT_DIR:
            target = Path(OUTPUT_DIR) / part["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(decode_part(part), encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ERROR: {error}")
        sys.exit(1)
