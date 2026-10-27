# Power BI / Fabric field-level lineage

A single self-contained [Fabric notebook](./fabric_field_lineage_demo.ipynb)
that traces upstream fields in Lakehouses / Warehouses / KQL Databases and
other indexed items to downstream semantic-model columns and measures,
using the Power BI Admin Scanner APIs.

Report/visual-level field lineage is **not included**. Reports are available
only as a lightweight report-to-semantic-model reference index; the notebook
does not call report-definition APIs or require additional workspace access
to retrieve report or folder details.

## What it does

1. Calls the [Fabric Scanner APIs](https://learn.microsoft.com/en-us/fabric/governance/metadata-scanning-overview)
   (`GetModifiedWorkspaces` → `PostWorkspaceInfo` → `GetScanStatus` →
   `GetScanResult` with `lineage`, `datasourceDetails`, `datasetSchema`,
   `datasetExpressions`) to perform a tenant-wide metadata scan, in batches
   of up to 100 workspaces.
2. Indexes upstream artifacts (Lakehouse, Warehouse, SQL Analytics Endpoint,
   KQL Database, Eventhouse, Mirrored DB, Datamart).
3. Resolves each semantic-model table to its upstream artifact via five
   fallback strategies:
   - `M-parse` — Power Query M navigation steps
     (`Lakehouse.Contents`, `Sql.Database`, `AzureDataExplorer.Contents`,
     `Kusto.Contents`)
   - `upstreamArtifacts` — dataset's explicit upstream link
   - `datasourceUsage` — dataset's `datasourceUsages` matched against the
     workspace's `datasourceInstances` (server name → artifact name)
   - `guid-in-dataset` — any known artifact GUID found anywhere in the
     dataset JSON (catches Direct Lake models that store the source ID
     deep inside sub-artifact metadata)
   - `same-workspace guess` — highest-priority Lakehouse/Warehouse in the
     same workspace as the semantic model
4. Extracts direct, table-qualified DAX column references from measures and
   checks them against the scanned model columns.
5. Builds `lineage`, with one row per upstream field to downstream
   semantic-model column/measure, including workspace, best-effort folder,
   and the `resolution` method.
6. Builds `reports_index` (also available as `reports_df`) from the same
   scan, with report workspace/folder, semantic-model name, and
   semantic-model workspace. This is a reference table, not proof that a
   report uses a particular field.

## How to use

1. Upload [fabric_field_lineage_demo.ipynb](./fabric_field_lineage_demo.ipynb)
   to a Microsoft Fabric workspace.
2. Attach any Spark or Python runtime.
3. Configure authentication in section 2 (signed-in user by default, or
   service principal as described below).
4. Run all cells top to bottom through the six numbered sections:
   helper functions, authentication, scan/indexing, M-query resolution,
   lineage join, and lookup.

After section 6, use `lookup` for a compact impact view, or `apply_filters`
for the full lineage columns, including folders and resolution method:

```python
lookup(item="Kaggle", table="betfront", fields="COUNTRY")
# → semantic-model columns / measures that depend on that Lakehouse field

apply_filters(lineage, item="Kaggle", fields="COUNTRY")
# → matching lineage rows, including workspace/folder and resolution details

reports_df.head(20)
# → report-to-semantic-model reference index (no field/visual bindings)
```

All four filter arguments (`item`, `schema`, `table`, `fields`) are optional
case-insensitive substring matches; `fields` accepts a single name or a list.

## Prerequisites

- Run inside a Microsoft Fabric workspace using either:
  - a signed-in user with the tenant-wide **Fabric Administrator** role
    (`USE_SPN = False`), authenticated with
    `notebookutils.credentials.getToken("pbi")`; or
  - a service principal (`USE_SPN = True`) with its tenant/client IDs and
    secret configured in section 2. Install `msal` if needed and retrieve
    the secret securely, for example from Key Vault, rather than saving it
    in the notebook.
- For service-principal access, a Fabric admin must enable *Allow service
  principals to use read-only Admin APIs*, scoped to a dedicated Microsoft
  Entra security group containing the app. The service principal does not
  need a tenant-wide admin role at run time. Follow
  [Enable service principal authentication for admin APIs](https://learn.microsoft.com/en-us/fabric/admin/enable-service-principal-admin-apis)
  for app and tenant configuration.
- A Fabric admin must enable both *Enhance admin APIs responses with
  detailed metadata* and *Enhance admin APIs responses with DAX and mashup
  expressions*, with the appropriate scope for the scanning identity. See
  [Set up metadata scanning](https://learn.microsoft.com/en-us/fabric/admin/metadata-scanning-setup).
- Existing datasets are only enriched with tables/columns/M/DAX after they
  are next modified. Datasets created **before** the tenant setting was
  enabled stay as skeletons until they are touched (edit + save, refresh,
  or republish). Check the indexed field count in section 3 and the resolved
  table count in section 4 when results are missing.

## Known limitations

- Folder metadata is **best-effort**: the documented Scanner API schema
  does not include folders. The notebook only reads `folderId`/`folders`
  if returned by the scan; otherwise folder values are `None`. It makes no
  extra REST calls to fill them in.
- Upstream fields are inferred from semantic-model metadata, not obtained
  by enumerating every source table's schema. Unused source fields are not
  listed, and missing scan metadata can leave tables unresolved.
- Fallback resolution is heuristic, especially `same-workspace guess`.
  Inspect `resolution` in `lineage` before treating a match as authoritative.
- M-query parsing is regex-based and covers the common connectors. Bespoke
  or heavily custom M won't always resolve.
- Column renames inside M (`Table.RenameColumns`) are not tracked; matching
  is by name.
- DAX parsing is regex-based and does not provide complete dependency
  analysis, such as transitive measure-to-measure dependencies.
- Report/visual field bindings are not inspected, so this notebook cannot
  identify exactly which reports or visuals use an upstream field.

## References

- [Scanner APIs overview](https://learn.microsoft.com/en-us/fabric/governance/metadata-scanning-overview)
- [Set up metadata scanning](https://learn.microsoft.com/en-us/fabric/admin/metadata-scanning-setup)
- [Enable service principal authentication for admin APIs](https://learn.microsoft.com/en-us/fabric/admin/enable-service-principal-admin-apis)
- [Fabric lineage view (UI)](https://learn.microsoft.com/en-us/fabric/governance/lineage)
- [Impact analysis (UI)](https://learn.microsoft.com/en-us/fabric/governance/impact-analysis)
