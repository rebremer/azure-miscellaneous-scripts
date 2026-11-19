"""Create/update Fabric Data Pipelines in your workspace that call the consumption procedures:
  pl_load_consumption     -> ops.usp_load_consumption   (param max_drop_pct)
  pl_restore_consumption  -> ops.usp_restore_table      (params table_name, as_of_utc)

Usage:
  python deploy_pipeline.py                                   # deploy both
  python deploy_pipeline.py run pl_load_consumption           # deploy, then run and wait
  python deploy_pipeline.py run pl_restore_consumption table_name=ALL as_of_utc=2026-11-17T13:38:55
Requires: az login --tenant <tenant>
Required env: AZURE_TENANT_ID, FABRIC_WORKSPACE_ID, FABRIC_WAREHOUSE_ID, FABRIC_SQL_SERVER
"""
import base64, json, os, subprocess, sys, time
import urllib.request, urllib.error

TENANT = os.getenv("AZURE_TENANT_ID") or sys.exit("Set AZURE_TENANT_ID to your tenant ID.")
WS = os.getenv("FABRIC_WORKSPACE_ID") or sys.exit("Set FABRIC_WORKSPACE_ID to your workspace ID.")
WH = os.getenv("FABRIC_WAREHOUSE_ID") or sys.exit("Set FABRIC_WAREHOUSE_ID to your warehouse item ID.")
ENDPOINT = os.getenv("FABRIC_SQL_SERVER") or sys.exit("Set FABRIC_SQL_SERVER to your warehouse SQL endpoint.")
API = "https://api.fabric.microsoft.com/v1"


def sp_pipeline(activity_name, proc, params):
    """params: {name: (pipeline param type, default, stored procedure param type)}"""
    return {"properties": {
        "parameters": {n: {"type": t, "defaultValue": d} for n, (t, d, _) in params.items()},
        "activities": [{
            "name": activity_name,
            "type": "SqlServerStoredProcedure",
            "dependsOn": [],
            "policy": {"timeout": "0.01:00:00", "retry": 0, "retryIntervalInSeconds": 30,
                       "secureInput": False, "secureOutput": False},
            "typeProperties": {
                "storedProcedureName": proc,
                "storedProcedureParameters": {
                    n: {"value": {"value": f"@pipeline().parameters.{n}", "type": "Expression"}, "type": st}
                    for n, (_, _, st) in params.items()},
            },
            "linkedService": {
                "name": "dwh_consumption",
                "properties": {
                    "type": "DataWarehouse",
                    "typeProperties": {"endpoint": ENDPOINT, "artifactId": WH, "workspaceId": WS},
                    "annotations": [],
                },
            },
        }],
    }}


PIPELINES = {
    "pl_load_consumption": (
        "Runs ops.usp_load_consumption in dwh_consumption",
        sp_pipeline("usp_load_consumption", "[ops].[usp_load_consumption]",
                    {"max_drop_pct": ("int", 50, "Int32")})),
    "pl_restore_consumption": (
        "Restores consumption tables to a previous point in time (ops.usp_restore_table). "
        "table_name = table in schema consumption or ALL; as_of_utc = UTC timestamp, e.g. 2026-11-17T13:38:55",
        sp_pipeline("usp_restore_table", "[ops].[usp_restore_table]",
                    {"table_name": ("string", "ALL", "String"),
                     "as_of_utc": ("string", "", "String")})),
}


def token():
    return subprocess.check_output(
        f"az account get-access-token --tenant {TENANT} --resource https://api.fabric.microsoft.com --query accessToken -o tsv",
        shell=True, text=True).strip()


def call(method, url, body=None):
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {token()}", "Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req)
    except urllib.error.HTTPError as e:
        sys.exit(f"{e.code} {e.read().decode()}")
    raw = r.read()
    return r.status, r.headers, (json.loads(raw) if raw else None)


def wait_lro(headers):
    url = headers.get("Location")
    while True:
        time.sleep(int(headers.get("Retry-After", 3)))
        _, headers, b = call("GET", url)
        if b and b.get("status") in ("Succeeded", "Failed"):
            if b["status"] == "Failed":
                sys.exit(json.dumps(b))
            return


def b64(o):
    return base64.b64encode(json.dumps(o, indent=2).encode()).decode()


def deploy(name, description, content):
    parts = [{"path": "pipeline-content.json", "payload": b64(content), "payloadType": "InlineBase64"}]
    _, _, items = call("GET", f"{API}/workspaces/{WS}/dataPipelines")
    existing = next((i for i in items["value"] if i["displayName"] == name), None)
    if existing:
        s, h, _ = call("POST", f"{API}/workspaces/{WS}/dataPipelines/{existing['id']}/updateDefinition",
                       {"definition": {"parts": parts}})
    else:
        s, h, _ = call("POST", f"{API}/workspaces/{WS}/dataPipelines",
                       {"displayName": name, "description": description, "definition": {"parts": parts}})
    if s == 202:
        wait_lro(h)
    _, _, items = call("GET", f"{API}/workspaces/{WS}/dataPipelines")
    return next(i["id"] for i in items["value"] if i["displayName"] == name)


def run(pid, parameters):
    body = {"executionData": {"parameters": parameters}} if parameters else {}
    _, h, _ = call("POST", f"{API}/workspaces/{WS}/items/{pid}/jobs/instances?jobType=Pipeline", body)
    while True:
        time.sleep(10)
        _, _, b = call("GET", h["Location"])
        print(b["status"])
        if b["status"] not in ("NotStarted", "InProgress"):
            print(json.dumps(b.get("failureReason"), indent=2))
            break


ids = {n: deploy(n, d, c) for n, (d, c) in PIPELINES.items()}
print(ids)

if len(sys.argv) > 2 and sys.argv[1] == "run":
    run(ids[sys.argv[2]], dict(a.split("=", 1) for a in sys.argv[3:]))
