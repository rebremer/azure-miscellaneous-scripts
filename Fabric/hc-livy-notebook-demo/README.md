# Fabric high-concurrency notebook demo

Runs two notebooks against **one shared high-concurrency Spark session** on
Microsoft Fabric, using the Livy session API.

Sequence:

1. `POST /workspaces/{ws}/lakehouses/{lh}/livyapi/.../sessions` with
   `spark.synapse.session.isHighConcurrencyEnabled=true`. Wait for `idle`.
2. Upload `nb1_one_plus_one.ipynb` as a workspace notebook item, then submit
   its code as a Livy statement on the session above.
3. Upload `nb2_read_delta.ipynb` and submit its code as a second statement on
   the **same** session id — same Spark application, no cold start.
4. `DELETE` the session.

Layout:

```
fabric_hc_demo.py            # orchestrator
requirements.txt
notebooks/
  nb1_one_plus_one.ipynb     # prints 1 + 1
  nb2_read_delta.ipynb       # reads Delta table from OneLake
```

Edit the notebooks under `notebooks/` directly; the script reads them at
runtime, both for the upload (full ipynb) and for execution (concatenated code
cells submitted as one Livy statement).

## Pre-reqs

- Python 3.10+
- `az login` (or a service principal via `AZURE_*` env vars) with
  `Contributor` on the Fabric workspace — gives the required
  `Lakehouse.Execute.All` / `Lakehouse.Read.All` delegated permissions.
- Workspace `d645b0ed-b64d-4fa4-bcf2-4b34f75ff55e` and lakehouse
  `ce87ddcd-3454-4b31-a8f6-c0f07c47c672` exist.

## Run

```powershell
python -m pip install -r requirements.txt
python fabric_hc_demo.py
```

You'll see:

- one `session id: <guid>` line (the HC session, visible in the Monitoring hub
  as `HC_Lakehouse_<sessionId>`)
- two `statement state: available` lines on that same session id
- the printed output of each statement
- a single `Deleting Livy session ...` line at the end

If the second notebook starts in seconds (no Spark cold-start), the session
sharing is working.
