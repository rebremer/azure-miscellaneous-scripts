"""Deploy Fabric Warehouse schemas (T-SQL DDL) via DACPAC + SqlPackage.

Complements `scripts/deploy.py`, which creates/updates the Warehouse items
themselves but does NOT publish their schema (fabric-cicd currently treats
Warehouse as a shell item). This script:

    1. Discovers every fabric/**/*.sqlproj in the repo.
    2. Builds each with `dotnet build -c Release` -> .dacpac.
    3. Queries the Fabric REST API to look up each warehouse's SQL
       connection string in the target workspace (matched by displayName
       == sqlproj <Name>).
    4. Publishes the .dacpac with `sqlpackage /Action:Publish`, authenticating
       via an AAD access token from DefaultAzureCredential.

Required env vars:
    FABRIC_WORKSPACE_ID   Target Fabric workspace GUID.

Optional env vars:
    REPOSITORY_DIRECTORY  Path to the folder holding *.sqlproj files.
                          Defaults to `<repo>/fabric`.
    DRY_RUN               If "1"/"true", build DACPACs and log the plan
                          but skip SqlPackage publish. Useful in the
                          Validate stage to catch T-SQL syntax errors.

Prereqs on the agent:
    * .NET SDK 8+ (preinstalled on ubuntu-latest).
    * SqlPackage on PATH; the script installs it via
      `dotnet tool install -g microsoft.sqlpackage` if missing.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from shutil import which

from azure.identity import DefaultAzureCredential

FABRIC_API = "https://api.fabric.microsoft.com/v1"
SQL_SCOPE = "https://database.windows.net/.default"
FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes"}


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def _run(cmd: list[str]) -> None:
    logging.info("$ %s", " ".join(cmd))
    subprocess.run(cmd, check=True)


def _sqlproj_name(sqlproj: Path) -> str:
    """Return the <Name> element from the sqlproj; fall back to file stem.

    The <Name> is the Fabric Warehouse displayName we match against the
    workspace inventory to find the target SQL endpoint.
    """
    try:
        root = ET.fromstring(sqlproj.read_text(encoding="utf-8"))
    except (OSError, ET.ParseError):
        return sqlproj.stem
    for node in root.iter():
        tag = node.tag.split("}", 1)[-1]  # strip XML namespace, if any
        if tag == "Name" and node.text:
            return node.text.strip()
    return sqlproj.stem


def _list_warehouses(workspace_id: str, api_token: str) -> dict[str, str]:
    """Return {displayName: sqlConnectionString} for all warehouses in workspace."""
    req = urllib.request.Request(
        f"{FABRIC_API}/workspaces/{workspace_id}/warehouses",
        headers={"Authorization": f"Bearer {api_token}"},
    )
    with urllib.request.urlopen(req) as resp:  # noqa: S310 (trusted URL)
        body = json.load(resp)
    result: dict[str, str] = {}
    for wh in body.get("value", []):
        name = wh.get("displayName")
        conn = (wh.get("properties") or {}).get("connectionString")
        if name and conn:
            result[name] = conn
    return result


def _ensure_sqlpackage() -> str:
    """Return path to SqlPackage, installing it via `dotnet tool` if missing."""
    if path := (which("sqlpackage") or which("SqlPackage")):
        return path
    logging.info("SqlPackage not found on PATH; installing via dotnet tool...")
    _run(["dotnet", "tool", "install", "-g", "microsoft.sqlpackage"])
    # `dotnet tool install -g` drops binaries in ~/.dotnet/tools which
    # is not always on PATH inside a fresh CI shell.
    candidate = Path(os.environ.get("HOME", "")) / ".dotnet" / "tools" / "sqlpackage"
    if candidate.exists():
        return str(candidate)
    return "sqlpackage"


def _build_dacpac(sqlproj: Path) -> Path:
    _run(["dotnet", "build", str(sqlproj), "-c", "Release", "--nologo"])
    expected = sqlproj.parent / "bin" / "Release" / f"{sqlproj.stem}.dacpac"
    if expected.exists():
        return expected
    matches = list((sqlproj.parent / "bin" / "Release").rglob("*.dacpac"))
    if not matches:
        raise SystemExit(f"No .dacpac produced under {sqlproj.parent / 'bin' / 'Release'}")
    return matches[0]


def _publish(
    sqlpackage: str,
    dacpac: Path,
    server: str,
    database: str,
    sql_token: str,
) -> None:
    _run([
        sqlpackage,
        "/Action:Publish",
        f"/SourceFile:{dacpac}",
        f"/TargetServerName:{server}",
        f"/TargetDatabaseName:{database}",
        f"/AccessToken:{sql_token}",
        # Fabric Warehouse safety: never drop objects present in the target
        # but missing from source. Flip intentionally if you want drift removal.
        "/p:DropObjectsNotInSource=false",
        "/p:BlockOnPossibleDataLoss=true",
    ])


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log = logging.getLogger("deploy-wh-schemas")

    workspace_id = _require("FABRIC_WORKSPACE_ID")
    repo_dir = Path(
        os.getenv("REPOSITORY_DIRECTORY")
        or Path(__file__).resolve().parent.parent / "fabric"
    ).resolve()

    if not repo_dir.is_dir():
        raise SystemExit(f"Repository directory not found: {repo_dir}")

    sqlprojs = sorted(repo_dir.glob("**/*.sqlproj"))
    if not sqlprojs:
        log.info("No *.sqlproj found under %s; nothing to publish.", repo_dir)
        return 0

    log.info("Workspace: %s", workspace_id)
    log.info("Source   : %s", repo_dir)
    log.info("Projects : %s", ", ".join(p.name for p in sqlprojs))

    # Build DACPACs first — cheap T-SQL validation even in DRY_RUN.
    built: list[tuple[Path, Path, str]] = []
    for sqlproj in sqlprojs:
        db_name = _sqlproj_name(sqlproj)
        dacpac = _build_dacpac(sqlproj)
        built.append((sqlproj, dacpac, db_name))

    if _env_flag("DRY_RUN"):
        log.warning("DRY_RUN=1 — built DACPACs but skipping publish.")
        for _, dacpac, db in built:
            log.info("  would publish %s -> warehouse '%s'", dacpac.name, db)
        return 0

    # Same credential chain as scripts/deploy.py:
    #   EnvironmentCredential -> WorkloadIdentity -> AzureCliCredential
    credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
    api_token = credential.get_token(FABRIC_SCOPE).token
    sql_token = credential.get_token(SQL_SCOPE).token

    warehouses = _list_warehouses(workspace_id, api_token)
    log.info(
        "Warehouses discovered in workspace: %s",
        ", ".join(sorted(warehouses)) or "(none)",
    )

    sqlpackage = _ensure_sqlpackage()

    for sqlproj, dacpac, db in built:
        server = warehouses.get(db)
        if not server:
            raise SystemExit(
                f"Warehouse '{db}' (from {sqlproj}) not found in workspace "
                f"{workspace_id}. Run scripts/deploy.py first so fabric-cicd "
                "creates the shell."
            )
        log.info("Publishing %s -> %s / %s", dacpac.name, server, db)
        _publish(sqlpackage, dacpac, server, db, sql_token)

    log.info("Warehouse schema deployment complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
