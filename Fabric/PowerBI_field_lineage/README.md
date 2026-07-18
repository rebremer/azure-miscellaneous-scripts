# Power BI / Fabric field-level lineage

A single self-contained Fabric notebook that shows, for every column in a
Lakehouse / Warehouse / KQL Database (Eventhouse), where that field ends up
downstream — semantic models and Power BI reports — using only Microsoft
Fabric APIs (no third-party tools).

## What it does

1. Calls the [Fabric Scanner APIs](https://learn.microsoft.com/en-us/fabric/governance/metadata-scanning-overview)
   (`GetModifiedWorkspaces` → `PostWorkspaceInfo` → `GetScanResult` with
   `lineage`, `datasetSchema`, `datasetExpressions`) to pull metadata for
   every workspace the caller can see.
2. Indexes upstream artifacts (Lakehouse, Warehouse, SQL Analytics Endpoint,
   KQL Database, Eventhouse, Mirrored DB, Datamart).
3. Resolves each semantic-model table to its upstream artifact via five
   fallback strategies:
   - `M-parse` — Power Query M navigation steps
     (`Lakehouse.Contents`, `Sql.Database`, `AzureDataExplorer.Contents`)
   - `upstreamArtifacts` — dataset's explicit upstream link
   - `datasourceUsage` — dataset's `datasourceUsages` matched against the
     workspace's `datasourceInstances` (server name → artifact name)
   - `guid-in-dataset` — any known artifact GUID found anywhere in the
     dataset JSON (catches Direct Lake models that store the source ID
     deep inside sub-artifact metadata)
   - `same-workspace guess` — highest-priority Lakehouse/Warehouse in the
     same workspace as the semantic model
4. Extracts DAX column references from measures.
5. Calls the Fabric REST API `Reports - Get Definition` (PBIR format) for
   every report and parses the JSON payloads to find which columns and
   measures each report binds to.
6. Joins upstream-→-model with model-→-report to answer:
   *"if I change this column in the Lakehouse, which reports break?"*

## How to use

1. Upload `fabric_field_lineage_demo.ipynb` to a Microsoft Fabric workspace.
2. Attach any Spark or Python runtime.
3. Run cells 1 → 8 top to bottom.

Two helper functions are available after cell 5:

```python
lookup(item="Kaggle", table="betfront", fields="COUNTRY")
# → semantic-model columns / measures that depend on that Lakehouse field

full_lineage(item="Kaggle", fields="COUNTRY")
# → same, but joined with report usage so you also see which reports bind it
```

All four filter arguments (`item`, `schema`, `table`, `fields`) are optional
case-insensitive substring matches; `fields` accepts a single name or a list.

## Prerequisites

- The user running the notebook must be a **Fabric Administrator** — the
  Scanner APIs are admin-only.
- Tenant setting *Admin API settings → Enhance admin APIs responses with
  detailed metadata* must be **on**, applied to the security group that owns
  the workspaces you want to scan. See
  [Set up metadata scanning](https://learn.microsoft.com/en-us/fabric/admin/metadata-scanning-setup).
- Existing datasets are only enriched with tables/columns/M/DAX after they
  are next modified. Datasets created **before** the tenant setting was
  enabled stay as skeletons until they are touched (edit + save, refresh,
  or republish). Cell 5b diagnostic flags this case.

## Known limitations

- **Reports with a Microsoft Information Protection sensitivity label** that
  restricts export return HTTP 403 (`ItemHasProtectedLabel`) on
  `getDefinition`. Remove the label or have the compliance admin grant
  *Export* rights on the label.
- **Legacy PBIX-format reports** are not exportable via the API and return
  `Report_Report_FailedToExportReport`. Open the report in Power BI Service
  → *File → Save as* to create a PBIR-format copy, or republish from Power
  BI Desktop.
- **Admin monitoring / system workspaces** return
  `WorkspaceTypeNotSupported` on `getDefinition`. Expected — ignore.
- M-query parsing is regex-based and covers the common connectors. Bespoke
  or heavily custom M won't always resolve; cell 5b prints an unresolved
  sample so you can extend the parser.
- Column renames inside M (`Table.RenameColumns`) are not tracked; matching
  is by name.

## References

- [Scanner APIs overview](https://learn.microsoft.com/en-us/fabric/governance/metadata-scanning-overview)
- [Reports - Get Definition (Fabric REST)](https://learn.microsoft.com/en-us/rest/api/fabric/report/items/get-report-definition)
- [Fabric lineage view (UI)](https://learn.microsoft.com/en-us/fabric/governance/lineage)
- [Impact analysis (UI)](https://learn.microsoft.com/en-us/fabric/governance/impact-analysis)
