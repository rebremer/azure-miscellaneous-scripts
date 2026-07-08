"""Generate fabric/parameter.yml from the items in fabric/.

Scans dbt-content.json / notebook-content.py / pipeline-content.json for
Dev-side GUIDs and endpoints, then emits fabric-cicd `find_replace` rules
that rewrite them to `$items` / `$workspace` dynamic variables at deploy
time.

The output is a fully generated parameter file — nothing in this repo is
hand-authored for parameterization. Add a new Warehouse or Lakehouse in
Fabric Dev, let Git sync commit the item folder, and the next CI run
picks it up automatically.

Values the scanner cannot derive (e.g. per-env Fabric connection GUIDs
for Data Pipelines) go in `fabric/parameter.overrides.yml`:

    overrides:
      "<dev-connection-guid>":
        description: "Optional human note"
        replace_value:
          test: "<test-connection-guid>"
          prod: "<prod-connection-guid>"

The generator fails loudly if a discovered ref requires a value that
neither the scanner nor the overrides file can supply.

Usage:
    python scripts/generate_parameters.py --output PATH
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any, NamedTuple

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
FABRIC_DIR = REPO_ROOT / "fabric"
OVERRIDES_FILE = FABRIC_DIR / "parameter.overrides.yml"

# Strict GUID match — used to filter pipeline JSON noise.
_GUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

# Map fabric-cicd linkedService.type -> $items.<Type> token used in parameter.yml.
_LINKED_SERVICE_ITEM_TYPE = {
    "Lakehouse": "Lakehouse",
    "DataWarehouse": "Warehouse",
    "Warehouse": "Warehouse",
}


class Ref(NamedTuple):
    """One Dev-side value the scanner discovered.

    `replacement` is either a fabric-cicd variable string
    (`$items.Warehouse.dwh1.$id`, `$workspace.$id`, …) that resolves at
    deploy time, or `None` if the scanner cannot derive it (e.g. a
    connection objectId that only a human knows per environment).
    """

    file: Path
    description: str
    value: str
    replacement: str | None


# ---------------------------------------------------------------------------
# Scanners — each one yields Refs for a specific file format.
# ---------------------------------------------------------------------------


def _discover_dbt_refs(fabric_dir: Path) -> Iterator[Ref]:
    """Warehouse refs inside dbt jobs' dbt-content.json."""
    for path in fabric_dir.glob("**/dbt-content.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"WARN: could not parse {path}: {exc}", file=sys.stderr)
            continue

        cs = data.get("profile", {}).get("connectionSettings", {})
        if cs.get("properties", {}).get("type") != "DataWarehouse":
            continue

        name = cs.get("name") or "<unknown>"
        tp = cs.get("properties", {}).get("typeProperties", {})

        if ws := tp.get("workspaceId"):
            yield Ref(path, "Dev workspace ID", ws, "$workspace.$id")
        if art := tp.get("artifactId"):
            yield Ref(
                path,
                f"Warehouse '{name}' artifactId",
                art,
                f"$items.Warehouse.{name}.$id",
            )
        if ep := tp.get("endPoint"):
            yield Ref(
                path,
                f"Warehouse '{name}' SQL endpoint",
                ep,
                f"$items.Warehouse.{name}.$sqlendpoint",
            )


def _parse_meta_blocks(text: str) -> Iterator[dict[str, Any]]:
    """Yield each contiguous `# META ...` block in a notebook-content.py."""
    buf: list[str] = []
    for line in text.splitlines():
        if line.startswith("# META "):
            buf.append(line[len("# META ") :])
        elif line.rstrip() == "# META":
            buf.append("")
        else:
            if buf:
                try:
                    yield json.loads("\n".join(buf))
                except json.JSONDecodeError:
                    pass
                buf = []
    if buf:
        try:
            yield json.loads("\n".join(buf))
        except json.JSONDecodeError:
            pass


def _parse_configure_blocks(text: str) -> Iterator[dict[str, Any]]:
    """Yield the JSON body of each `%%configure` magic cell."""
    cells = re.split(r"^# CELL .*$", text, flags=re.MULTILINE)
    for cell in cells[1:]:
        cell = re.split(r"^# (?:METADATA|CELL) .*$", cell, flags=re.MULTILINE)[0]
        magic = [
            line[len("# MAGIC ") :]
            for line in cell.splitlines()
            if line.startswith("# MAGIC ")
        ]
        if not magic or "%%configure" not in magic[0]:
            continue
        body = "\n".join(magic[1:])
        try:
            start = body.index("{")
            end = body.rindex("}") + 1
            yield json.loads(body[start:end])
        except (ValueError, json.JSONDecodeError):
            continue


def _discover_notebook_refs(fabric_dir: Path) -> Iterator[Ref]:
    """Lakehouse refs inside notebook-content.py (METADATA + %%configure)."""
    for path in fabric_dir.glob("**/notebook-content.py"):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"WARN: could not read {path}: {exc}", file=sys.stderr)
            continue

        for meta in _parse_meta_blocks(text):
            lh = meta.get("dependencies", {}).get("lakehouse", {})
            if not isinstance(lh, dict):
                continue
            name = lh.get("default_lakehouse_name") or "<unknown>"
            if lh_id := lh.get("default_lakehouse"):
                yield Ref(
                    path,
                    f"Notebook METADATA default_lakehouse '{name}'",
                    lh_id,
                    f"$items.Lakehouse.{name}.$id",
                )
            if ws := lh.get("default_lakehouse_workspace_id"):
                yield Ref(
                    path,
                    "Notebook METADATA default_lakehouse_workspace_id",
                    ws,
                    "$workspace.$id",
                )

        for cfg in _parse_configure_blocks(text):
            dl = cfg.get("defaultLakehouse", {})
            if not isinstance(dl, dict):
                continue
            name = dl.get("name") or "<unknown>"
            if lh_id := dl.get("id"):
                yield Ref(
                    path,
                    f"%%configure defaultLakehouse '{name}' id",
                    lh_id,
                    f"$items.Lakehouse.{name}.$id",
                )
            if ws := dl.get("workspaceId"):
                yield Ref(
                    path,
                    "%%configure defaultLakehouse workspaceId",
                    ws,
                    "$workspace.$id",
                )


def _walk_pipeline(node: Any, path: Path) -> Iterator[Ref]:
    """Yield Refs from a pipeline-content.json tree.

    Detects two patterns:
      1. `linkedService` blocks: `{type: Lakehouse|DataWarehouse,
         typeProperties: {workspaceId, artifactId}}` -> workspace + item.
      2. Connection refs: `{objectId: <guid>, ...}` -> per-env GUID that
         must be supplied by fabric/parameter.overrides.yml.
    """
    if isinstance(node, dict):
        tp = node.get("typeProperties")
        ls_type = node.get("type")
        if (
            isinstance(tp, dict)
            and isinstance(tp.get("workspaceId"), str)
            and isinstance(tp.get("artifactId"), str)
        ):
            item_type = _LINKED_SERVICE_ITEM_TYPE.get(str(ls_type))
            yield Ref(
                path,
                f"Pipeline {item_type or ls_type} workspaceId",
                tp["workspaceId"],
                "$workspace.$id",
            )
            if item_type:
                # Pipeline linkedServices don't include the item name;
                # only the artifactId. We can't derive the target-env
                # $items.<Type>.<Name>.$id without a name -> require override.
                yield Ref(
                    path,
                    f"Pipeline {item_type} artifactId (unknown item name)",
                    tp["artifactId"],
                    None,
                )
            else:
                yield Ref(
                    path,
                    f"Pipeline artifactId for unknown linkedService type '{ls_type}'",
                    tp["artifactId"],
                    None,
                )

        obj_id = node.get("objectId")
        if isinstance(obj_id, str) and _GUID_RE.match(obj_id):
            yield Ref(path, "Pipeline connection objectId", obj_id, None)

        for v in node.values():
            yield from _walk_pipeline(v, path)
    elif isinstance(node, list):
        for v in node:
            yield from _walk_pipeline(v, path)


def _discover_pipeline_refs(fabric_dir: Path) -> Iterator[Ref]:
    """Lakehouse/Warehouse linkedServices and connection refs inside pipelines."""
    for path in fabric_dir.glob("**/pipeline-content.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"WARN: could not parse {path}: {exc}", file=sys.stderr)
            continue
        yield from _walk_pipeline(data, path)


def _discover_all(fabric_dir: Path) -> list[Ref]:
    scanners: Iterable[Iterator[Ref]] = (
        _discover_dbt_refs(fabric_dir),
        _discover_notebook_refs(fabric_dir),
        _discover_pipeline_refs(fabric_dir),
    )
    return [ref for scanner in scanners for ref in scanner]


# ---------------------------------------------------------------------------
# Overrides + emit
# ---------------------------------------------------------------------------


def _load_overrides(path: Path) -> dict[str, dict[str, Any]]:
    """Load `parameter.overrides.yml` if present."""
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    overrides = data.get("overrides", {}) or {}
    if not isinstance(overrides, dict):
        raise SystemExit(f"{path}: `overrides` must be a mapping")
    return {str(k): v for k, v in overrides.items()}


def _emit_rule_derived(ref: Ref) -> list[str]:
    """Rule where scanner derived a single replacement value for all envs."""
    assert ref.replacement is not None
    return [
        f'  - find_value: "{ref.value}"   # {ref.description}',
        "    replace_value:",
        f'      _ALL_: "{ref.replacement}"',
    ]


def _emit_rule_override(ref: Ref, override: dict[str, Any]) -> list[str]:
    """Rule where the human supplied per-env values via overrides.yml."""
    replace_value = override.get("replace_value")
    if not isinstance(replace_value, dict) or not replace_value:
        raise SystemExit(
            f"Override for {ref.value} must include a `replace_value` mapping "
            f"with at least one environment key."
        )
    note = override.get("description") or ref.description
    lines = [f'  - find_value: "{ref.value}"   # {note} (override)']
    lines.append("    replace_value:")
    for env, val in replace_value.items():
        lines.append(f'      {env}: "{val}"')
    return lines


def _build_yaml(refs: list[Ref], overrides: dict[str, dict[str, Any]]) -> str:
    """Return the full parameter.yml text, or raise on unresolved refs."""
    # Dedup on value; keep first Ref for each unique value.
    unique: dict[str, Ref] = {}
    for ref in refs:
        unique.setdefault(ref.value, ref)

    resolved: list[list[str]] = []
    unresolved: list[Ref] = []
    for ref in unique.values():
        if ref.replacement is not None:
            resolved.append(_emit_rule_derived(ref))
        elif ref.value in overrides:
            resolved.append(_emit_rule_override(ref, overrides[ref.value]))
        else:
            unresolved.append(ref)

    if unresolved:
        msg = [
            "ERROR: the following refs cannot be resolved automatically.",
            "Add them to fabric/parameter.overrides.yml under `overrides:`:",
            "",
        ]
        for ref in unresolved:
            rel = ref.file.relative_to(REPO_ROOT).as_posix()
            msg.append(f'  "{ref.value}":')
            msg.append(f"    description: {ref.description}   # from {rel}")
            msg.append("    replace_value:")
            msg.append('      test: "<test-value>"')
            msg.append('      prod: "<prod-value>"')
            msg.append("")
        raise SystemExit("\n".join(msg))

    build = os.getenv("BUILD_BUILDNUMBER", "local")
    header = [
        "# AUTO-GENERATED by scripts/generate_parameters.py — do not edit.",
        f"# Build: {build}",
        "#",
        "# Values discovered by scanning fabric/ item folders and their",
        "# content files. `$items.<Type>.<Name>.$id` and `$workspace.$id`",
        "# are fabric-cicd dynamic variables resolved against the target",
        "# workspace at deploy time.",
        "#",
        "# To override an entry or supply a per-env value the scanner can't",
        "# derive (e.g. connection GUIDs), edit fabric/parameter.overrides.yml.",
        "",
    ]

    if not resolved:
        # fabric-cicd rejects a bare `find_replace:` key (YAML None).
        # Emit an explicit empty list so validation passes for repos with
        # no cross-item GUID references (e.g. a Warehouse-only workspace).
        header.append("find_replace: []")
        header.append("")
        return "\n".join(header)

    header.append("find_replace:")
    header.append("")

    body: list[str] = []
    for block in resolved:
        body.extend(block)
        body.append("")

    return "\n".join(header + body)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        metavar="PATH",
        help="Where to write the generated parameter.yml.",
    )
    args = parser.parse_args()

    if not FABRIC_DIR.is_dir():
        print(f"ERROR: {FABRIC_DIR} not found.", file=sys.stderr)
        return 1

    overrides = _load_overrides(OVERRIDES_FILE)
    refs = _discover_all(FABRIC_DIR)
    text = _build_yaml(refs, overrides)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")

    rel_out = args.output.resolve()
    print(f"Wrote {rel_out}")
    for ref in {r.value: r for r in refs}.values():
        rel_src = ref.file.relative_to(REPO_ROOT).as_posix()
        source = "override" if ref.replacement is None else "derived"
        print(f"  {source:9} {ref.value}  <- {rel_src}: {ref.description}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
