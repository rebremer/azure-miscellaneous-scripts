# Fabric Managed Private Endpoint to a Private Link Service

Scripts to create a Fabric **Managed Private Endpoint (MPE)** that targets an
Azure **Private Link Service (PLS)** via the Fabric REST API, and to verify
private DNS resolution from inside the Fabric managed VNet.

Creating an MPE to a PLS via the Fabric portal returns:

```
ManagedVNet_InvalidPrivateEndpointFqdns
```

A PLS has no built-in DNS name (unlike Azure Storage, SQL, etc.), so Fabric
requires one or more `targetFqdns` — the hostnames your workloads will use to
reach the service. The REST API lets you set this field explicitly.

## Files

| File | Purpose |
| --- | --- |
| `new_fabric_managed_private_endpoint.py` | Calls `POST /v1/workspaces/{workspaceId}/managedPrivateEndpoints` with both `targetPrivateLinkResourceId` and `targetFqdns`. |
| `verify_mpe_resolution.py` | Run from a Fabric notebook to confirm the FQDN resolves to a private IP and the TCP port is reachable. |

## Usage

1. Edit the constants at the top of `new_fabric_managed_private_endpoint.py`:
   - `WORKSPACE_ID` – Fabric workspace GUID (you must be workspace admin).
   - `PRIVATE_LINK_RESOURCE_ID` – full resource ID of your PLS.
   - `TARGET_FQDNS` – list of hostnames workloads will use (does not need to
     resolve in public DNS; Fabric maps it to the PLS private IP inside the
     managed VNet).
   - `NAME` – name for the MPE (<= 64 chars, unique in the workspace).

2. Install deps and sign in:

   ```bash
   pip install requests
   az login
   ```

3. Run it:

   ```bash
   python new_fabric_managed_private_endpoint.py
   ```

4. Approve the pending request in the Azure portal under
   **Private Link Service → Private endpoint connections**.

5. From a Fabric notebook, run `verify_mpe_resolution.py` to confirm the FQDN
   resolves to a private (RFC1918) IP and the TCP port is reachable.

## Reference

- [Connect on-premises data sources to Fabric using managed private endpoints](https://learn.microsoft.com/en-us/fabric/security/connect-to-on-premise-sources-using-managed-private-endpoints)
