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
   `fabric-prod`. Add a manual *Approvals and checks* on `fabric-prod`.
8. **Create the pipeline**: Pipelines → New pipeline → Azure Repos Git →
   this repo → *Existing Azure Pipelines YAML file* → `/azure-pipelines.yml`.

### Author and promote your first change

9. In `fabric-dev`, create or edit a Warehouse / pipeline / notebook.
10. Open the Source Control pane in `fabric-dev` → commit to `main`.
    Fabric writes the item definitions into `/fabric/` in this repo.
11. (Optional but recommended) author or update [`fabric/parameter.yml`](fabric/parameter.yml)
    so any Dev-specific values (SQL endpoints, lakehouse IDs) get rewritten
    per environment.
12. The pipeline runs automatically: **Validate (dry-run) → Deploy Test →
    Deploy Prod** (Prod gated by the approval from step 7). No clicks in
    Fabric. No `Update from Git` button.

## Repository layout

```
.
├── azure-pipelines.yml      # Multi-stage pipeline (Dev -> Test -> Prod)
├── requirements.txt         # Python deps (fabric-cicd, azure-identity)
├── scripts/
│   └── deploy.py            # Thin wrapper around fabric-cicd
├── fabric/                  # Items exported from the Dev workspace via Git sync
│   └── parameter.yml        # Per-environment find/replace + variable values
└── .gitignore
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

### 3. Author `fabric/parameter.yml`

Use it to swap connection strings, lakehouse IDs, etc. between environments.
A starter file is included; see the
[parameterization docs](https://microsoft.github.io/fabric-cicd/latest/parameter/)
for the full schema.

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
   Source Control pane, but unattended.
4. Optionally runs `unpublish_all_orphan_items` to remove items deleted
   from Git.
