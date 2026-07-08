# `fabric/` directory

This directory mirrors the contents of your **Dev** Fabric workspace, populated
by Fabric's built-in Git integration:

> *Workspace settings → Git integration → Connect → Azure DevOps → this repo,
> branch `main`, directory `/fabric`*

After the initial sync, each managed item shows up here as its own folder, e.g.:

```
fabric/
├── parameter.overrides.yml   # optional; only per-env values the scanner can't derive
├── DimCustomer.Warehouse/
│   ├── item.metadata.json
│   └── ...
├── LoadDimCustomer.DataPipeline/
│   └── ...
└── Bronze.Lakehouse/
    └── ...
```

**Nothing in this directory is hand-authored for parameterization.**
`parameter.yml` is generated fresh on every CI run by
`scripts/generate_parameters.py`, which scans the item folders and their
content files. The generated file is `.gitignore`d — never commit it.

The only file you may need to author by hand is
`fabric/parameter.overrides.yml`, and only when the generator cannot derive
a value on its own (e.g. per-environment Fabric connection GUIDs for Data
Pipelines). The generator fails with clear instructions if that happens.

**Do not hand-edit the item folders** — let Fabric write them via Git sync,
then commit.

The CI/CD pipeline reads this directory and publishes its contents to the
Test and Prod workspaces via `fabric-cicd`, with no manual *Update from Git*
click required.
