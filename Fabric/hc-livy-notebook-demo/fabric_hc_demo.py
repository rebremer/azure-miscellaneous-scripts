"""
fabric_hc_demo.py

Explicit high-concurrency Spark session sharing across two notebooks, using the
Fabric Livy API.

Steps:
  1. Create one Livy session against the lakehouse (HC mode enabled). This is
     the "HC cluster" - one Spark application that will host both runs.
  2. Upload notebook 1 to the workspace, then submit its code cells as a Livy
     statement on the session. Wait for completion.
  3. Upload notebook 2 to the workspace, then submit its code cells as another
     statement on the SAME session.
  4. Delete the session.

The notebooks themselves are uploaded so they're visible in the workspace, but
execution is done deterministically via Livy statements - so we can prove the
same Spark session/application is reused.

Authentication
--------------
DefaultAzureCredential, scope https://api.fabric.microsoft.com/.default.
Easiest: `az login` first.

Required Fabric permissions on the lakehouse: Lakehouse.Execute.All +
Lakehouse.Read.All (delegated). Contributor on the workspace covers this.

Run
---
  python -m pip install -r requirements.txt
  python fabric_hc_demo.py
"""

from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path
from typing import Any

import requests
from azure.identity import DefaultAzureCredential

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
WORKSPACE_ID = "d645b0ed-b64d-4fa4-bcf2-4b34f75ff55e"
LAKEHOUSE_ID = "ce87ddcd-3454-4b31-a8f6-c0f07c47c672"
LAKEHOUSE_NAME = "Lakehouse"  # metadata only

NOTEBOOKS_DIR = Path(__file__).parent / "notebooks"

# (local file, display name in Fabric) - executed in this order.
NOTEBOOKS = [
    (NOTEBOOKS_DIR / "nb1_one_plus_one.ipynb", "hc-demo-onePlusOne"),
    (NOTEBOOKS_DIR / "nb2_read_delta.ipynb", "hc-demo-readDelta"),
]

FABRIC_BASE = "https://api.fabric.microsoft.com/v1"
LIVY_BASE = (
    f"{FABRIC_BASE}/workspaces/{WORKSPACE_ID}"
    f"/lakehouses/{LAKEHOUSE_ID}/livyapi/versions/2023-12-01/sessions"
)
SCOPE = "https://api.fabric.microsoft.com/.default"

POLL_INTERVAL_SECONDS = 10
MAX_WAIT_SECONDS = 30 * 60

# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------
_credential = DefaultAzureCredential()


def _headers() -> dict[str, str]:
    token = _credential.get_token(SCOPE).token
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# Fabric long-running operation helper (used by notebook create)
# ---------------------------------------------------------------------------
def _wait_for_lro(response: requests.Response) -> dict[str, Any] | None:
    if response.status_code != 202:
        return None

    op_url = response.headers.get("Location")
    if not op_url:
        raise RuntimeError("202 response without Location header")

    deadline = time.time() + MAX_WAIT_SECONDS
    while time.time() < deadline:
        time.sleep(POLL_INTERVAL_SECONDS)
        r = requests.get(op_url, headers=_headers(), timeout=60)
        r.raise_for_status()
        body = r.json()
        status = body.get("status")
        print(f"  LRO status: {status}")
        if status in ("Succeeded", "Completed"):
            result_url = r.headers.get("Location")
            if result_url:
                rr = requests.get(result_url, headers=_headers(), timeout=60)
                if rr.ok and rr.text:
                    try:
                        return rr.json()
                    except ValueError:
                        return {}
            return body
        if status in ("Failed", "Cancelled"):
            raise RuntimeError(f"LRO failed: {json.dumps(body, indent=2)}")
    raise TimeoutError(f"LRO did not finish within {MAX_WAIT_SECONDS} seconds")


# ---------------------------------------------------------------------------
# Notebook helpers
# ---------------------------------------------------------------------------
def upload_notebook(ipynb_path: Path, display_name: str) -> str:
    """Upload a local .ipynb as a Fabric notebook item; return item id."""
    if not ipynb_path.is_file():
        raise FileNotFoundError(ipynb_path)

    payload_b64 = base64.b64encode(ipynb_path.read_bytes()).decode("ascii")
    url = f"{FABRIC_BASE}/workspaces/{WORKSPACE_ID}/notebooks"
    body = {
        "displayName": display_name,
        "definition": {
            "format": "ipynb",
            "parts": [
                {
                    "path": "notebook-content.ipynb",
                    "payload": payload_b64,
                    "payloadType": "InlineBase64",
                }
            ],
        },
    }
    print(f"Uploading '{ipynb_path.name}' as notebook '{display_name}'...")
    r = requests.post(url, headers=_headers(), json=body, timeout=60)

    if r.status_code == 201:
        item = r.json()
    elif r.status_code == 202:
        item = _wait_for_lro(r) or {}
        if "id" not in item:
            item = _find_notebook_by_name(display_name)
    elif r.status_code == 409:
        # Already exists with this display name - reuse it.
        print("  (notebook already exists, reusing)")
        item = _find_notebook_by_name(display_name)
    else:
        r.raise_for_status()
        item = r.json()

    item_id = item.get("id")
    if not item_id:
        raise RuntimeError(f"Notebook create returned no id: {item}")
    print(f"  -> notebook id: {item_id}")
    return item_id


def _find_notebook_by_name(display_name: str) -> dict[str, Any]:
    url = f"{FABRIC_BASE}/workspaces/{WORKSPACE_ID}/notebooks"
    r = requests.get(url, headers=_headers(), timeout=60)
    r.raise_for_status()
    for nb in r.json().get("value", []):
        if nb.get("displayName") == display_name:
            return nb
    raise RuntimeError(f"Notebook '{display_name}' not found")


def extract_code(ipynb_path: Path) -> str:
    """Concatenate all `code` cells of an ipynb into one Python block."""
    nb = json.loads(ipynb_path.read_text(encoding="utf-8"))
    blocks: list[str] = []
    for cell in nb.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        src = cell.get("source", "")
        if isinstance(src, list):
            src = "".join(src)
        blocks.append(src.rstrip())
    return "\n\n".join(blocks)


# ---------------------------------------------------------------------------
# Livy session API
# ---------------------------------------------------------------------------
def create_livy_session() -> str:
    """Create one HC-enabled Livy session. Return session url."""
    body = {
        "name": "hc-demo-session",
        "conf": {
            # Enable high-concurrency mode on the underlying Spark session.
            "spark.synapse.session.isHighConcurrencyEnabled": "true",
        },
    }
    print("Creating Livy session (HC enabled)...")
    r = requests.post(LIVY_BASE, headers=_headers(), json=body, timeout=60)
    if r.status_code not in (200, 201, 202):
        r.raise_for_status()
    info = r.json()
    session_id = info["id"]
    session_url = f"{LIVY_BASE}/{session_id}"
    print(f"  session id: {session_id}")

    # Poll until idle.
    deadline = time.time() + MAX_WAIT_SECONDS
    last_state = ""
    while time.time() < deadline:
        s = requests.get(session_url, headers=_headers(), timeout=60)
        s.raise_for_status()
        state = s.json().get("state", "")
        if state != last_state:
            print(f"  session state: {state}")
            last_state = state
        if state == "idle":
            return session_url
        if state in ("error", "dead", "killed", "shutting_down"):
            raise RuntimeError(f"Livy session entered terminal state: {state}")
        time.sleep(POLL_INTERVAL_SECONDS)
    raise TimeoutError("Livy session did not become idle in time")


def run_statement(session_url: str, code: str, label: str) -> None:
    """Submit a pyspark statement and stream its output once available."""
    print(f"Submitting statement: {label}")
    r = requests.post(
        f"{session_url}/statements",
        headers=_headers(),
        json={"code": code, "kind": "pyspark"},
        timeout=60,
    )
    r.raise_for_status()
    statement_id = r.json()["id"]
    stmt_url = f"{session_url}/statements/{statement_id}"
    print(f"  statement id: {statement_id}")

    deadline = time.time() + MAX_WAIT_SECONDS
    last_state = ""
    while time.time() < deadline:
        s = requests.get(stmt_url, headers=_headers(), timeout=60)
        s.raise_for_status()
        body = s.json()
        state = body.get("state", "")
        if state != last_state:
            print(f"  statement state: {state}")
            last_state = state
        if state == "available":
            _print_statement_output(body)
            return
        if state in ("error", "cancelled", "cancelling"):
            raise RuntimeError(f"Statement ended in state {state}: {body}")
        time.sleep(POLL_INTERVAL_SECONDS)
    raise TimeoutError(f"Statement '{label}' did not complete in time")


def _print_statement_output(body: dict[str, Any]) -> None:
    out = body.get("output") or {}
    status = out.get("status")
    if status == "error":
        print("  --- error ---")
        print(out.get("ename"), out.get("evalue"))
        for line in out.get("traceback", []) or []:
            print(line)
        raise RuntimeError("Statement returned error status")
    data = out.get("data") or {}
    text = data.get("text/plain")
    if text:
        print("  --- output ---")
        print(text)
    else:
        print("  (no text output)")


def delete_livy_session(session_url: str) -> None:
    print(f"Deleting Livy session: {session_url}")
    r = requests.delete(session_url, headers=_headers(), timeout=60)
    if r.status_code not in (200, 202, 204, 404):
        print(f"  warn: delete returned {r.status_code} {r.text}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    print(f"Workspace : {WORKSPACE_ID}")
    print(f"Lakehouse : {LAKEHOUSE_ID}")
    print()

    # 1. Create the HC Spark session (the "cluster").
    session_url = create_livy_session()
    print()

    try:
        for path, name in NOTEBOOKS:
            # Upload notebook item to workspace.
            upload_notebook(path, name)
            # Pull its code and execute against the SAME Livy session.
            code = extract_code(path)
            run_statement(session_url, code, label=name)
            print()
    finally:
        # 4. Always tear down the session.
        delete_livy_session(session_url)

    print("All done.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except requests.HTTPError as e:
        print(
            f"HTTP error: {e.response.status_code} {e.response.text}",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as e:  # noqa: BLE001 - top-level reporter
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
