# test-cicdfabric-dwh

CI/CD for Microsoft Fabric Warehouse (and related items) using
[`fabric-cicd`](https://microsoft.github.io/fabric-cicd/) and Azure DevOps,
authenticating with a **Workspace Identity** via Workload Identity Federation.

The pipeline replaces the manual *"Update from Git"* click in the Fabric
Source Control pane with a fully automated deployment that handles Warehouse
conflicts (`allow_override = True`).

## Get started

End-to-end checklist to get your first automated Warehouse promotion running.
Each step links to the detailed instructions further down.

### In Microsoft Fabric

1. **Create three workspaces**: `fabric-dev`, `fabric-test`, `fabric-prod`.
   Capture their workspace IDs (Workspace settings → About → *Workspace ID*).
2. **Connect `fabric-dev` to this repo**: Workspace settings → Git
   integration → Azure DevOps → this repo → branch `main` → directory
   `/fabric` → *Connect and sync*. Item folders appear under `fabric/`.
3. **Do NOT connect `fabric-test` or `fabric-prod` to Git** — that's what
   creates the manual "accept changes" prompt. The pipeline writes to them
   directly via the Fabric item APIs.
4. **Grant the Workspace Identity access**: in *both* `fabric-test` and
   `fabric-prod`, add the service principal that backs your DevOps service
   connection as **Member** or **Admin** (Contributor is not enough).

### In Azure DevOps

5. **Service connection** → see [§ 1 below](#1-create-the-workspace-identity-service-connection-in-azure-devops).
   Name it exactly `fabric-workspace-identity`.
6. **Variable group `fabric-cicd`** → see [§ 2](#2-configure-pipeline-variables).
   Populate `TEST_WORKSPACE_ID` and `PROD_WORKSPACE_ID` from step 1.
7. **Environments**: Pipelines → Environments → create `fabric-test` and
   `fabric-prod`. Optionally add *Approvals and checks* on `fabric-prod`.
   (The pipeline also enforces an explicit `ManualValidation@0` gate in
   YAML — see the `ApproveProd` stage — so environment approvals are
   defence-in-depth rather than the only stop.)
8. **Create the pipeline**: Pipelines → New pipeline → Azure Repos Git →
   this repo → *Existing Azure Pipelines YAML file* → `/azure-pipelines.yml`.

### Author and promote your first change

9. In `fabric-dev`, create or edit a Warehouse / pipeline / notebook.
10. Open the Source Control pane in `fabric-dev` → commit to `main`.
    Fabric writes the item definitions into `/fabric/` in this repo.
11. The pipeline runs automatically: **Validate (dry-run) → Deploy Test →
    Approve → Deploy Prod**. The `ApproveProd` stage pauses the run and
    waits for an authorized user to click *Resume* before Prod starts.
    No clicks in Fabric. No `Update from Git` button. No hand-editing of
    `parameter.yml` — it is generated fresh on every run from the item
    folders (see § 3).

## Repository layout

```
.
├── azure-pipelines.yml               # Multi-stage pipeline (Validate -> Test -> Approve -> Prod)
├── requirements.txt                  # Python deps (fabric-cicd, azure-identity, pyyaml)
├── pipelines/
│   └── steps-setup.yml               # Shared Python + pip install steps
├── scripts/
│   ├── deploy.py                     # Thin wrapper around fabric-cicd (item definitions)
│   ├── deploy_warehouse_schemas.py   # Builds *.sqlproj -> .dacpac and publishes via SqlPackage
│   └── generate_parameters.py        # Emits fabric/parameter.yml from folder+content scan
├── fabric/                           # Items exported from the Dev workspace via Git sync
│   ├── parameter.overrides.yml       # OPTIONAL: per-env values the scanner can't derive
│   └── <name>.Warehouse/*.sqlproj    # Warehouse DDL, built as DACPAC (see § below)
└── .gitignore                        # Ignores fabric/parameter.yml (generated per build)
```

`fabric/` is populated by **Fabric → Source control → Connect** against the
Dev workspace. Commit those item folders to this repo; the pipeline then
promotes them to Test and Prod without ever touching the Fabric UI.

## One-time setup

### 1. Create the Workspace Identity service connection in Azure DevOps

1. **Project settings → Service connections → New → Azure Resource Manager → Workload Identity Federation (automatic)**.
2. Name it `fabric-workspace-identity` (matches `azureSubscription:` in
   [azure-pipelines.yml](azure-pipelines.yml)).
3. In each target Fabric workspace, add the service connection's identity
   as **Member** or **Admin** (Contributor is not sufficient for
   `updateFromGit` on Warehouses).

### 2. Configure pipeline variables

In Azure DevOps, create a **variable group** named `fabric-cicd` with:

| Variable                | Example                                 | Notes                                |
| ----------------------- | --------------------------------------- | ------------------------------------ |
| `TEST_WORKSPACE_ID`     | `11111111-1111-1111-1111-111111111111`  | Target Fabric workspace (Test)       |
| `PROD_WORKSPACE_ID`     | `22222222-2222-2222-2222-222222222222`  | Target Fabric workspace (Prod)       |
| `FABRIC_ENVIRONMENT`    | overridden per stage                    | Matches keys in `parameter.yml`      |

### 3. `fabric/parameter.yml` is generated, not authored

Every CI run invokes [scripts/generate_parameters.py](scripts/generate_parameters.py),
which scans `fabric/` for item folders and content files (`dbt-content.json`,
`notebook-content.py`, `pipeline-content.json`) and emits `find_replace`
rules that rewrite Dev-side IDs to fabric-cicd
[dynamic variables](https://microsoft.github.io/fabric-cicd/latest/how_to/parameterization/#dynamic-replacement)
(`$items.<Type>.<Name>.$id`, `$workspace.$id`, `$items.Warehouse.<Name>.$sqlendpoint`,
…) at deploy time.

Add a new Warehouse `dwh2` in Fabric Dev → Git sync commits
`fabric/dwh2.Warehouse/` → the next pipeline run regenerates the file with
a rule for `dwh2`. No repo edits, no `parameter.yml` merge conflicts.

The generated file is `.gitignore`d and published as the `fabric-params`
pipeline artifact, so Test and Prod both deploy exactly what Validate
signed off on.

**When you *do* need to hand-author something**

Values that no scanner can derive — currently only per-environment Fabric
connection GUIDs referenced by Data Pipelines — go in
`fabric/parameter.overrides.yml`:

```yaml
overrides:
  "<dev-connection-guid>":
    description: "SQL Server connection used by LoadDimCustomer pipeline"
    replace_value:
      test: "<test-connection-guid>"
      prod: "<prod-connection-guid>"
```

The generator fails the build with copy-pasteable YAML if such a ref
appears and no override is defined. Until you introduce a pipeline with a
connection, this file does not need to exist.

## Local dry-run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

az login
$env:FABRIC_WORKSPACE_ID = "<dev-or-test-ws-id>"
$env:FABRIC_ENVIRONMENT  = "test"
python scripts/deploy.py
```

`deploy.py` honours a `DRY_RUN=1` env var which logs what would be deployed
without calling Fabric — useful for PR validation.

## What the pipeline does on each run

1. Checks out this repo.
2. Acquires a Workspace Identity token via `AzureCLI@2`
   (`addSpnToEnvironment: true` exposes the federated credentials so
   `DefaultAzureCredential` picks them up automatically).
3. Runs `scripts/deploy.py`, which calls
   `fabric_cicd.publish_all_items(...)` with `allow_override = True` and the
   Warehouse item type enabled — equivalent to clicking *Update all* in the
   Source Control pane, but unattended. This creates/updates the item
   *shells* (Warehouses, Data Pipelines, Notebooks, Semantic Models, …).
4. Runs `scripts/deploy_warehouse_schemas.py` to publish the Warehouse
   **DDL** (see next section) — a step that `fabric-cicd` does not perform
   for Warehouses today.
5. Pauses in the `ApproveProd` stage until a reviewer clicks *Resume*,
   then repeats steps 3–4 against the Prod workspace.
6. Optionally runs `unpublish_all_orphan_items` (set
   `UNPUBLISH_ORPHANS=1`) to remove items deleted from Git.

## Item types that need extra deployment steps

`fabric-cicd` treats several item types as *definition-only*: it creates
the container in the target workspace but does not deploy the code or
schema inside it. Below are the gaps this repo fills — and the ones you
would need to fill yourself if you added those item types.

### Warehouse DDL — handled here via DACPAC (`deploy_warehouse_schemas.py`)

`publish_all_items` creates the empty Warehouse item; it does **not**
publish tables, views, stored procedures, or schemas. This repo covers
that gap with a standard SQL project workflow:

1. Author DDL under `fabric/<name>.Warehouse/**/*.sql` inside a
   `Microsoft.Build.Sql` SDK-style `*.sqlproj` (see
   [fabric/rbr3.Warehouse/rbr3.sqlproj](fabric/rbr3.Warehouse/rbr3.sqlproj)).
2. The Validate stage runs `dotnet build` on every `*.sqlproj` — this is
   a free T-SQL syntax check that fails the PR on invalid DDL.
3. The Deploy stages run [scripts/deploy_warehouse_schemas.py](scripts/deploy_warehouse_schemas.py),
   which:
   * builds each `*.sqlproj` into a `.dacpac`,
   * queries the Fabric REST API for the target Warehouse's SQL
     connection string (matched by `sqlproj <Name>` == Warehouse
     `displayName`),
   * publishes with `sqlpackage /Action:Publish` and
     `/p:DropObjectsNotInSource=false` +
     `/p:BlockOnPossibleDataLoss=true` (safe by default — no drops, no
     data-loss).

**Only DDL is deployed.** No `INSERT` / `UPDATE` / `MERGE` runs. If you
need seed or reference data, add a `Script.PostDeployment.sql` and a
`<PostDeploy Include="…" />` to the `.sqlproj` — `sqlpackage` will run it
idempotently after the schema publish.

### Lakehouse materialized views / SQL objects — would need custom code

`fabric-cicd` deploys the Lakehouse *item* but not the SQL analytics
endpoint objects layered on top of it (materialized views, T-SQL views,
stored procs on the SQL endpoint). If this repo ever adds a Lakehouse
with materialized views you would need an equivalent to
`deploy_warehouse_schemas.py`, roughly:

1. Store the `CREATE MATERIALIZED VIEW …` statements under
   `fabric/<name>.Lakehouse/sql/`.
2. Add a Python step that resolves the Lakehouse's SQL analytics endpoint
   via `GET /workspaces/{id}/lakehouses/{lakehouseId}` (the
   `sqlEndpointProperties.connectionString`).
3. Acquire an AAD token for `https://database.windows.net/.default` and
   execute the DDL with `pyodbc` / `struct`-packed access token (same
   pattern the Warehouse script uses, minus DACPAC — Lakehouse SQL
   endpoints do not accept DACPACs today).

Notebook `%%sql` cells and Spark-defined tables are deployed as part of
the notebook definition and do not need this treatment.

### Manual approval before Prod — handled by the `ApproveProd` stage

Between `DeployTest` and `DeployProd` the pipeline runs an agentless
`ManualValidation@0` job. It pauses the run and emails
`notifyUsers` (set this in [azure-pipelines.yml](azure-pipelines.yml));
Prod starts only after an authorized user clicks *Resume* in the
pipeline graph. If nobody responds within `timeoutInMinutes` (default 3
days) the stage rejects and Prod is skipped. This is enforced in YAML
and is independent of any *Approvals and checks* configured on the
`fabric-prod` environment — you can use both.
