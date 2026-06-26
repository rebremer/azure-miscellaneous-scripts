"""Deploy Fabric items to a workspace using fabric-cicd.

Drives `fabric_cicd.FabricWorkspace` from environment variables so the same
script runs locally (after `az login`) and in Azure DevOps (after the
`AzureCLI@2` task with `addSpnToEnvironment: true`).

Required env vars:
    FABRIC_WORKSPACE_ID   Target Fabric workspace GUID.
    FABRIC_ENVIRONMENT    Logical environment name (must match a key under
                          `find_replace`/`key_value_replace` in parameter.yml).

Optional env vars:
    REPOSITORY_DIRECTORY  Path to the folder holding Fabric items.
                          Defaults to `<repo>/fabric`.
    UNPUBLISH_ORPHANS     If "1"/"true", delete workspace items that no longer
                          exist in Git. Off by default to keep first runs safe.
    DRY_RUN               If "1"/"true", log the plan and exit without calling
                          Fabric APIs.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from azure.identity import DefaultAzureCredential
from fabric_cicd import (
    FabricWorkspace,
    publish_all_items,
    unpublish_all_orphan_items,
)

# Item types we want fabric-cicd to manage. Add/remove as the repo grows.
# Full list: https://microsoft.github.io/fabric-cicd/latest/items/
ITEM_TYPES_IN_SCOPE = [
    "Warehouse",
    "DataPipeline",
    "Notebook",
    "Lakehouse",
    "SemanticModel",
    "Report",
]


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes"}


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log = logging.getLogger("deploy")

    workspace_id = _require("FABRIC_WORKSPACE_ID")
    environment = _require("FABRIC_ENVIRONMENT")
    repo_dir = Path(
        os.getenv("REPOSITORY_DIRECTORY")
        or Path(__file__).resolve().parent.parent / "fabric"
    ).resolve()

    if not repo_dir.is_dir():
        raise SystemExit(f"Repository directory not found: {repo_dir}")

    log.info("Workspace : %s", workspace_id)
    log.info("Env       : %s", environment)
    log.info("Source    : %s", repo_dir)
    log.info("Item types: %s", ", ".join(ITEM_TYPES_IN_SCOPE))

    if _env_flag("DRY_RUN"):
        log.warning("DRY_RUN=1 — skipping all Fabric API calls.")
        return 0

    # DefaultAzureCredential resolves, in order:
    #   - EnvironmentCredential  (AZURE_CLIENT_ID/TENANT_ID/FEDERATED_TOKEN
    #                             populated by AzureCLI@2 in DevOps)
    #   - WorkloadIdentityCredential
    #   - AzureCliCredential     (local dev: `az login`)
    credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)

    workspace = FabricWorkspace(
        workspace_id=workspace_id,
        repository_directory=str(repo_dir),
        item_type_in_scope=ITEM_TYPES_IN_SCOPE,
        environment=environment,
        token_credential=credential,
    )

    # `allow_override` is the key flag for Warehouses: it tells the Fabric
    # service to overwrite items even when the workspace has diverged from
    # Git — the same outcome as clicking "Update all" with "Prefer remote"
    # in the Source Control pane.
    publish_all_items(workspace, items_to_include=None)

    if _env_flag("UNPUBLISH_ORPHANS"):
        log.info("UNPUBLISH_ORPHANS=1 — removing workspace items not in Git.")
        unpublish_all_orphan_items(workspace)

    log.info("Deployment complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
