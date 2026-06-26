# `fabric/` directory

This directory mirrors the contents of your **Dev** Fabric workspace, populated
by Fabric's built-in Git integration:

> *Workspace settings → Git integration → Connect → Azure DevOps → this repo,
> branch `main`, directory `/fabric`*

After the initial sync, each managed item shows up here as its own folder, e.g.:

```
fabric/
├── parameter.yml
├── DimCustomer.Warehouse/
│   ├── item.metadata.json
│   └── ...
├── LoadDimCustomer.DataPipeline/
│   └── ...
└── Bronze.Lakehouse/
    └── ...
```

**Do not hand-edit the item folders** — let Fabric write them via Git sync,
then commit. Only [`parameter.yml`](parameter.yml) is authored by hand.

The CI/CD pipeline reads this directory and publishes its contents to the
Test and Prod workspaces via `fabric-cicd`, with no manual *Update from Git*
click required.
