# Databricks notebook source
# MAGIC %md
# MAGIC # Purview: Create separate scans for each container 
# MAGIC 
# MAGIC **Description**
# MAGIC - This notebook lists all containers in storage account and creates a scan for each different container. Scope (filter) of that container is only that container (all other URLs are excluded)
# MAGIC - By limiting to scope of a scan to a single container, a single scan can be run faster ("prevent days of running for 1 scan")
# MAGIC - Notebook runs on Databricks, no need to setup op Python or venv locally

# COMMAND ----------

# ENVIRONMENT VARIABLES

# 1. Update PURVIEW_NAME with your Purview account name. DON'T USE QUOTATIONS!!!
%env PURVIEW_NAME=<<your purview name without quotations>>
# 2. Uncomment and set the variables below if you plan to use a Service Principal. DON'T USE QUOTATIONS!!!
# Make sure that Service Principal is data curator in Purview minimally
%env AZURE_CLIENT_ID=<<your client id without quotations>>
%env AZURE_TENANT_ID=<<your tenant id without quotations>>
%env AZURE_CLIENT_SECRET=<<your client secreat without quotations>>

# 3. Update the path to your local entities_to_term.csv file path
PATH_TO_JSON ="/dbfs/testpurview" # quotations
STORAGE_ACCOUNT_NAME = "<<your storage account name>>" # quotations
PURVIEW_DATA_SOURCE = "<<Purview data source name of storage account>>" # quotations

# COMMAND ----------

# MAGIC %sh
# MAGIC pip install purviewcli
# MAGIC pip install azure-storage-blob
# MAGIC pip install azure-identity

# COMMAND ----------

# MAGIC %sh
# MAGIC cd /dbfs
# MAGIC rm -r purview
# MAGIC mkdir purview
# MAGIC cd purview
# MAGIC rm -r scan
# MAGIC mkdir scan
# MAGIC rm -r filter
# MAGIC mkdir filter

# COMMAND ----------

from azure.identity import DefaultAzureCredential
# In case no MI is used, add AZURE_TENANT_ID, AZURE_CLIENT_ID and AZURE_CLIENT_SECRET to environment variables
token_credential = DefaultAzureCredential()
from azure.storage.blob import (
    BlobServiceClient
)
import purviewcli as pv
import json
import copy


# Create handlers
root_blob_url = "{}://{}.blob.core.windows.net".format("https", STORAGE_ACCOUNT_NAME)
root_dfs_url = "{}://{}.dfs.core.windows.net".format("https", STORAGE_ACCOUNT_NAME)
blob_service_client = BlobServiceClient(root_blob_url, credential=token_credential)
containers = blob_service_client.list_containers() 

# 1. Create list of URLs
url_list=[]
for container in containers: 
    #print(container.name)
    url_list.append(str(root_dfs_url) + "/" + container.name)

containers_scan = blob_service_client.list_containers() 
# 2. Create scan per container, in which each scan has a filter on the container 
for index, container in enumerate(containers_scan):
    # 2.1 Create scan
    scan={}
    scan['kind'] = 'AdlsGen2Msi'
    scan['name'] = 'scan' + container.name
    json_scan = json.dumps(scan, indent=4)
    file_path = "/dbfs/purview/scan/" + scan['name'] + ".json"
    with open(file_path, "w") as text_file:
        text_file.write(json_scan)    

    # 2.2 Add scan to Purview using CLI
    !pv scan putScan --dataSourceName {PURVIEW_DATA_SOURCE} --scanName {scan['name']} --payloadFile {file_path}
    
    # 2.3 Create filter
    filter = {}
    filter['name'] = 'filter' + container.name
    include_url_list = []
    include_url_list.append(root_dfs_url + "/")
    include_url_list.append(url_list[index])
    #
    exclude_url_list = []
    exclude_url_list = copy.deepcopy(url_list)
    exclude_url_list.remove(url_list[index])
    #
    properties = {}
    properties['excludeRegexes'] = None
    properties['excludeUriPrefixes'] = exclude_url_list
    properties['includeRegexes'] = None
    properties['includeUriPrefixes'] = include_url_list
    #
    filter['properties'] = properties
    json_filter = json.dumps(filter, indent = 4)
    
    file_path = "/dbfs/purview/filter/" + filter['name'] + ".json"
   
    with open(file_path, "w") as text_file:
        text_file.write(json_filter)
      
    # 2.4 Add filter to scan using CLI
    !pv scan putFilter --dataSourceName {PURVIEW_DATA_SOURCE} --scanName {scan['name']} --payloadFile {file_path}
    #if index == 0:
    #    break

# COMMAND ----------

# MAGIC %sh
# MAGIC ls -l /dbfs/purview/scan
# MAGIC ls -l /dbfs/purview/filter
# MAGIC #cat /dbfs/purview/scan/scanbigdata.json
# MAGIC #cat /dbfs/purview/filter/filterbigdata.json

# COMMAND ----------


