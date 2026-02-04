Todo, already really description what stepts to take:

1. Create PostgreSQL database on Azure and install the following extensions:
   - DROP SCHEMA public CASCASE
   - CREATE SCHEMA public;

   - CREATE EXTENSION IF NOT EXISTS postgis;
   - CREATE EXTENSION IF NOT EXISTS hstore;

3. Create User Assigned MI (UAMI)

3. Create storage account and put a sample pbf file on it (e.g. Aachen.osm.pbf). Make the UAMI Storage Blob data contributor.

4. Create Azure Container Registry and grant UAMI pull rights to ACR

5. Create a key vault and add the postgres sql password to as secret. Make the UAMI Secret User via RBAC.

6. Rename osm2pgsql_dockerfile.txt to dockerfile and un az acr build --registry testacracr --image osm2pgsql-azcopy:latest .

7. Rename azcopy_sidecar_dockerfile.txt to dockerfile and un az acr build --registry testacracr --image azcopy-sidecar:latest .

8. Replace all the <<YOUR>> variables in deploy_aci.yaml with your own variables

9. az container create --resource-group <<Your RG NAME>> --file deploy_aci.yaml

10. Verify that the pbf file is loaded in your PostgreSQL tables
