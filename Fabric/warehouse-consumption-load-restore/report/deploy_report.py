"""Deploy a DirectQuery semantic model (sm_invoice) on dwh_consumption view consumption.v_invoice and the report rpt_invoices.

DirectQuery + single sign-on means the viewer's own identity queries the warehouse, so the row-level
security policy on dim_customer (members of role_invoice_ltd only see LTD customers) applies through the view.

Usage: python deploy_report.py
Requires: az login --tenant <tenant>
Required env: AZURE_TENANT_ID, FABRIC_WORKSPACE_ID, FABRIC_SQL_SERVER
Optional env: FABRIC_SQL_DB (default: dwh_consumption)
"""
import base64, json, os, subprocess, sys, time
import urllib.request, urllib.error

TENANT = os.getenv("AZURE_TENANT_ID") or sys.exit("Set AZURE_TENANT_ID to your tenant ID.")
WS = os.getenv("FABRIC_WORKSPACE_ID") or sys.exit("Set FABRIC_WORKSPACE_ID to your workspace ID.")
ENDPOINT = os.getenv("FABRIC_SQL_SERVER") or sys.exit("Set FABRIC_SQL_SERVER to your warehouse SQL endpoint.")
DATABASE = os.getenv("FABRIC_SQL_DB", "dwh_consumption")
MODEL_NAME = "sm_invoice"
REPORT_NAME = "rpt_invoices"
API = "https://api.fabric.microsoft.com/v1"

COLUMNS = [  # name, TMDL type, format, summarize
    ("invoice_id", "int64", None, "none"), ("customer_id", "int64", None, "none"),
    ("customer_code", "string", None, "none"), ("customer_name", "string", None, "none"),
    ("country", "string", None, "none"),
    ("invoice_date", "dateTime", "yyyy-mm-dd", "none"), ("due_date", "dateTime", "yyyy-mm-dd", "none"),
    ("net_amount", "decimal", "#,##0.00", "sum"), ("vat_amount", "decimal", "#,##0.00", "sum"),
    ("total_amount", "decimal", "#,##0.00", "sum"), ("paid_amount", "decimal", "#,##0.00", "sum"),
    ("open_amount", "decimal", "#,##0.00", "sum"),
    ("last_payment_date", "dateTime", "yyyy-mm-dd", "none"), ("payment_status", "string", None, "none"),
]

TABLE_TMDL = "table Invoice\n\n" \
    "\tmeasure 'Total Invoiced' = SUM(Invoice[total_amount])\n\t\tformatString: #,##0.00\n\n" \
    "\tmeasure 'Open Amount' = SUM(Invoice[open_amount])\n\t\tformatString: #,##0.00\n\n" \
    "\tmeasure 'Invoice Count' = COUNTROWS(Invoice)\n\t\tformatString: #,##0\n\n"
for n, t, f, s in COLUMNS:
    TABLE_TMDL += f"\tcolumn {n}\n\t\tdataType: {t}\n" + (f"\t\tformatString: {f}\n" if f else "") + \
                  f"\t\tsummarizeBy: {s}\n\t\tsourceColumn: {n}\n\n"
TABLE_TMDL += f"""\tpartition Invoice = m
\t\tmode: directQuery
\t\tsource =
\t\t\t\tlet
\t\t\t\t    Source = Sql.Database("{ENDPOINT}", "{DATABASE}"),
\t\t\t\t    v = Source{{[Schema="consumption", Item="v_invoice"]}}[Data]
\t\t\t\tin
\t\t\t\t    v
"""

MODEL_PARTS = {
    "definition.pbism": json.dumps({"version": "4.2", "settings": {}}),
    "definition/database.tmdl": "database\n\tcompatibilityLevel: 1702\n",
    "definition/model.tmdl": "model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n\tdiscourageImplicitMeasures\n\nref table Invoice\n",
    "definition/tables/Invoice.tmdl": TABLE_TMDL,
}

SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"


def field(kind, prop):
    return {kind: {"Expression": {"SourceRef": {"Entity": "Invoice"}}, "Property": prop}}


def proj(kind, prop, active=None):
    p = {"field": field(kind, prop), "queryRef": f"Invoice.{prop}"}
    if kind == "Column":
        p["nativeQueryRef"] = prop
    return p


def visual(name, vtype, x, y, w, h, query_state, title=None):
    v = {"$schema": f"{SCHEMA}/visualContainer/2.0.0/schema.json", "name": name,
         "position": {"x": x, "y": y, "z": 1000, "height": h, "width": w, "tabOrder": 1000},
         "visual": {"visualType": vtype, "query": {"queryState": query_state}, "drillFilterOtherVisuals": True}}
    if title:
        v["visual"]["visualContainerObjects"] = {"title": [{"properties": {
            "show": {"expr": {"Literal": {"Value": "true"}}},
            "text": {"expr": {"Literal": {"Value": f"'{title}'"}}}}}]}
    return v


PAGE = "page_invoices"
REPORT_PARTS = {
    "definition/version.json": {"$schema": f"{SCHEMA}/versionMetadata/1.0.0/schema.json", "version": "2.0.0"},
    "definition/report.json": {
        "$schema": f"{SCHEMA}/report/3.1.0/schema.json",
        "themeCollection": {"baseTheme": {"name": "CY25SU12", "reportVersionAtImport": {"visual": "2.5.0", "report": "3.1.0", "page": "2.3.0"}, "type": "SharedResources"}},
        "resourcePackages": [{"name": "SharedResources", "type": "SharedResources",
                              "items": [{"name": "CY25SU12", "path": "BaseThemes/CY25SU12.json", "type": "BaseTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True, "defaultFilterActionIsDataFilter": True,
                     "defaultDrillFilterOtherVisuals": True, "allowChangeFilterTypes": True,
                     "allowInlineExploration": True, "useEnhancedTooltips": True}},
    "definition/pages/pages.json": {"$schema": f"{SCHEMA}/pagesMetadata/1.0.0/schema.json",
                                    "pageOrder": [PAGE], "activePageName": PAGE},
    f"definition/pages/{PAGE}/page.json": {"$schema": f"{SCHEMA}/page/2.0.0/schema.json", "name": PAGE,
                                           "displayName": "Invoices", "displayOption": "FitToPage",
                                           "height": 720, "width": 1280},
    f"definition/pages/{PAGE}/visuals/v_total/visual.json": visual(
        "v_total", "card", 20, 20, 300, 110, {"Values": {"projections": [proj("Measure", "Total Invoiced")]}}, "Total invoiced"),
    f"definition/pages/{PAGE}/visuals/v_open/visual.json": visual(
        "v_open", "card", 340, 20, 300, 110, {"Values": {"projections": [proj("Measure", "Open Amount")]}}, "Open amount"),
    f"definition/pages/{PAGE}/visuals/v_count/visual.json": visual(
        "v_count", "card", 660, 20, 300, 110, {"Values": {"projections": [proj("Measure", "Invoice Count")]}}, "Invoices"),
    f"definition/pages/{PAGE}/visuals/v_bar/visual.json": visual(
        "v_bar", "barChart", 20, 150, 620, 540,
        {"Category": {"projections": [proj("Column", "customer_name")]},
         "Y": {"projections": [proj("Measure", "Total Invoiced")]}}, "Total invoiced per customer"),
    f"definition/pages/{PAGE}/visuals/v_table/visual.json": visual(
        "v_table", "tableEx", 660, 150, 600, 540,
        {"Values": {"projections": [proj("Column", c) for c in
                                    ("invoice_id", "customer_name", "invoice_date", "total_amount", "payment_status")]}},
        "Invoices"),
}


def token(resource):
    return subprocess.check_output(
        f"az account get-access-token --tenant {TENANT} --resource {resource} --query accessToken -o tsv",
        shell=True, text=True).strip()


def call(method, url, body=None, resource="https://api.fabric.microsoft.com"):
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {token(resource)}", "Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req)
    except urllib.error.HTTPError as e:
        sys.exit(f"{method} {url} -> {e.code} {e.read().decode()}")
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


def part(path, content):
    text = content if isinstance(content, str) else json.dumps(content, indent=2)
    return {"path": path, "payload": base64.b64encode(text.encode()).decode(), "payloadType": "InlineBase64"}


def upsert(kind, name, definition):
    _, _, items = call("GET", f"{API}/workspaces/{WS}/{kind}")
    existing = next((i for i in items["value"] if i["displayName"] == name), None)
    if existing:
        s, h, _ = call("POST", f"{API}/workspaces/{WS}/{kind}/{existing['id']}/updateDefinition", {"definition": definition})
    else:
        s, h, _ = call("POST", f"{API}/workspaces/{WS}/{kind}", {"displayName": name, "definition": definition})
    if s == 202:
        wait_lro(h)
    _, _, items = call("GET", f"{API}/workspaces/{WS}/{kind}")
    return next(i["id"] for i in items["value"] if i["displayName"] == name)


model_id = upsert("semanticModels", MODEL_NAME,
                  {"format": "TMDL", "parts": [part(p, c) for p, c in MODEL_PARTS.items()]})
print("semantic model:", model_id)

pbir = {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byConnection": {"connectionString": f"semanticmodelid={model_id}"}}}
report_id = upsert("reports", REPORT_NAME,
                   {"parts": [part("definition.pbir", pbir)] + [part(p, c) for p, c in REPORT_PARTS.items()]})
print("report:", report_id)
